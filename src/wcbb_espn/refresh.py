"""Fetch, qualify, snapshot and rebuild the two versioned ESPN WCBB DuckDB families."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .pipeline import PipelineValidationError, build_frames, load_cohort

TEAM_FAMILY = "wcbb_espn_team_netpoints"
PLAYER_FAMILY = "wcbb_espn_player_fingerprints"
FAMILY_TABLES = {
    TEAM_FAMILY: ("team_season", "four_factors", "bpi", "unkeyed_team_stats"),
    PLAYER_FAMILY: ("player_season", "skill_impacts", "team_id_discrepancies"),
}
API = "https://espnanalytics.com/api"


def parse_response(value: Mapping[str, object]) -> dict[str, list]:
    """Normalize ESPN's column-indexed tables or row records into row records."""
    needed = ("team4f", "team_stats", "bpi_stats", "plyr_stats")
    missing = set(needed).difference(value)
    if missing:
        raise PipelineValidationError(f"missing ESPN JSON family {sorted(missing)}")
    result = {}
    for key in needed:
        rows = value[key]
        if isinstance(rows, str):
            try:
                rows=json.loads(rows)
            except json.JSONDecodeError as exc:
                raise PipelineValidationError(f"invalid JSON in {key}") from exc
        if isinstance(rows, dict) and rows:
            if not all(isinstance(column, dict) for column in rows.values()):
                raise PipelineValidationError(f"invalid {key} column-indexed JSON")
            indices = list(next(iter(rows.values())))
            if any(set(column) != set(indices) for column in rows.values()):
                raise PipelineValidationError(f"{key} column row indices differ")
            # Align by the provider's index, not each column's insertion order.
            rows = [{name: column[index] for name, column in rows.items()} for index in indices]
        if not isinstance(rows,list) or not rows or not all(isinstance(r,dict) for r in rows):
            raise PipelineValidationError(f"invalid or empty {key} JSON rows")
        result[key]=rows
    return result


def compare_snapshot_ids(previous: set[int], current: set[int]) -> dict[str, list[int]]:
    return {"added": sorted(current-previous), "removed": sorted(previous-current)}


def summarize_qa(frames: Mapping[str, pd.DataFrame], cohort:pd.DataFrame, api_season:int) -> dict:
    teams=frames["team_season"]
    players=frames["player_season"]
    skills=frames["skill_impacts"]
    f4=frames["four_factors"]
    bp=frames["bpi"]
    expected=set(cohort.espn_team_id.astype(int))
    for name,frame,key in (("team_season",teams,["team_id"]), ("player_season",players,["player_id"]),
                           ("skill_impacts",skills,["player_id","skill"]), ("four_factors",f4,["team_id","Side"]),
                           ("bpi",bp,["team_id"])):
        if frame.duplicated(key).any():
            raise PipelineValidationError(f"duplicate {name} keys")
    if set(teams.team_id.astype(int))!=expected:
        raise PipelineValidationError("45-team cohort team count / IDs missing in summary")
    if set(bp.team_id.astype(int))!=expected:
        raise PipelineValidationError("45-team cohort BPI missing")
    if len(f4)!=3*len(expected):
        raise PipelineValidationError("45-team four factor side coverage incomplete")
    if not set(players.team_id.astype(int))<=expected:
        raise PipelineValidationError("player team IDs outside cohort")
    if not set(players.player_id.astype(int))==set(skills.player_id.astype(int)):
        raise PipelineValidationError("fingerprint skill coverage differs from players")
    if teams["bpi_bpi"].isna().any() or teams["team_stat_efg"].isna().any():
        raise PipelineValidationError("cohort team BPI / eFG values missing")
    if (teams["netpoints_additivity_delta"].abs()>0.15).any():
        raise PipelineValidationError("team Net Points arithmetic quality gate")
    missing_fingerprint=int(players.fingerprint_player_name.isna().sum())
    if missing_fingerprint:
        raise PipelineValidationError("missing source fingerprint for cohort players")
    n_discrepancies=len(frames["team_id_discrepancies"])
    return {"api_season":api_season,"academic_season":f"{api_season}-{str(api_season+1)[-2:]}",
            "status":"PASS_WITH_REVIEW" if n_discrepancies else "PASS",
            "team_count":len(teams), "player_count":len(players), "fingerprint_player_count":int(players.fingerprint_player_name.notna().sum()),
            "skill_impact_rows":len(skills),"four_factor_rows":len(f4),"bpi_rows":len(bp),
            "team_id_discrepancies":n_discrepancies,
            "unkeyed_source_team_stats_rows":len(frames["unkeyed_team_stats"]),
            "max_team_netpoints_component_delta":round(float(teams.netpoints_additivity_delta.abs().max()),6),
            "percentile_universe":"FULL SOURCE SEASON, NOT SELECTED 45 TEAMS",
            "independent_roster_verification":"NOT_PERFORMED"}


def get_public_json(url: str) -> tuple[dict,bytes]:
    sess=requests.Session()
    retry=Retry(total=3,backoff_factor=2,status_forcelist=(429,500,502,503,504),allowed_methods=("GET",))
    sess.mount("https://",HTTPAdapter(max_retries=retry))
    try:
        response=sess.get(url,timeout=(15,90),headers={"User-Agent":"Mozilla/5.0 (research data QA; GitHub Actions Python requests)"})
        response.raise_for_status()
        raw=response.content
        payload=response.json()
    except (requests.RequestException,ValueError) as exc:
        raise PipelineValidationError(f"HTTP/JSON fetch failed for {url}: {type(exc).__name__}") from exc
    if not isinstance(payload,dict) or len(raw)<100:
        raise PipelineValidationError(f"empty / invalid JSON from {url}")
    return payload,raw


def fetch_one_season(api_season:int,cohort:pd.DataFrame,staging:Path) -> tuple[dict[str,pd.DataFrame],dict]:
    urls={"team_data":f"{API}/team-data?league=wcbb&season={api_season}",
          "fingerprint_data":f"{API}/fingerprint-data?league=wcbb&season={api_season}"}
    payloads={}
    sources={}
    raw_dir=staging/"raw"
    raw_dir.mkdir(parents=True,exist_ok=True)
    for name,url in urls.items():
        obj,raw=get_public_json(url)
        (raw_dir/f"{name}_{api_season}.json").write_bytes(raw)
        payloads[name]=obj
        sources[name]={"url":url,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}
    team_data=parse_response(payloads["team_data"])
    fingerprints=payloads["fingerprint_data"]
    at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result=build_frames(team_data,fingerprints,cohort,api_season,at)
    qa=summarize_qa(result,cohort,api_season)
    qa["sources"]=sources
    qa["retrieved_utc"]=at
    return result,qa


def _duckdb():
    import duckdb
    return duckdb


def write_parquet(frame:pd.DataFrame,destination:Path) -> None:
    destination.parent.mkdir(parents=True,exist_ok=True)
    con=_duckdb().connect(database=":memory:")
    try:
        con.register("data_for_export",frame)
        con.execute("COPY (SELECT * FROM data_for_export) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",[str(destination)])
    finally:
        con.close()


def read_parquet(path:Path) -> pd.DataFrame:
    con=_duckdb().connect(database=":memory:")
    try:
        return con.execute("SELECT * FROM read_parquet(?, hive_partitioning=false)",[str(path)]).df()
    finally:
        con.close()


def save_family_tables(frames:dict[str,pd.DataFrame],dest:Path) -> None:
    for family,tables in FAMILY_TABLES.items():
        for table in tables:
            frame=frames[table]
            if frame.empty:
                # DuckDB needs column dtypes to create an empty Parquet table.
                frame=frame.copy().astype({x:"string" for x in frame.columns})
            write_parquet(frame,dest/family/f"{table}.parquet")


def load_family_tables(folder:Path) -> dict[str,pd.DataFrame]:
    return {name:read_parquet(folder/family/f"{name}.parquet") for family,names in FAMILY_TABLES.items() for name in names}


def write_combined_duckdb(frames_by_season:dict[int,dict[str,pd.DataFrame]],cohort:pd.DataFrame,output:Path,qa:list[dict]) -> None:
    output.parent.mkdir(parents=True,exist_ok=True)
    db=_duckdb().connect(str(output))
    try:
        for family,table_names in FAMILY_TABLES.items():
            db.execute(f"CREATE SCHEMA IF NOT EXISTS {family}")
            for table in table_names:
                combined=pd.concat([frames_by_season[y][table] for y in sorted(frames_by_season)],ignore_index=True)
                if combined.empty:
                    combined=combined.astype({x:"string" for x in combined.columns})
                db.register("to_insert",combined)
                db.execute(f"CREATE OR REPLACE TABLE {family}.{table} AS SELECT * FROM to_insert")
                db.unregister("to_insert")
        db.register("cohort_for_db",cohort)
        db.execute("CREATE OR REPLACE TABLE main.cohort_45 AS SELECT * FROM cohort_for_db")
        db.unregister("cohort_for_db")
        q=pd.DataFrame(qa)
        # Nested source dicts become JSON text for portable DuckDB storage.
        q["sources"]=q.sources.map(json.dumps)
        db.register("qa_for_db",q)
        db.execute("CREATE OR REPLACE TABLE main.qa_summary AS SELECT * FROM qa_for_db")
        db.unregister("qa_for_db")
    finally:
        db.close()


def baseline_qa(root: Path, frames: dict[str, pd.DataFrame], cohort: pd.DataFrame) -> dict:
    """Recover original provenance only when it matches the frozen retrieval timestamp."""
    qa = summarize_qa(frames, cohort, 2025)
    timestamps = set(frames['team_season'].retrieval_utc.dropna().astype(str))
    sidecar = root / 'data/frozen/season=2025/provenance.json'
    candidates = [sidecar, *sorted((root / 'data/snapshots').glob('*/manifest.json')),
                  root / 'reports/manifest_latest.json']
    for path in candidates:
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
            records = [document] if path == sidecar else document.get('qa', [])
            for original in records:
                if not isinstance(original, dict) or original.get('api_season') != 2025:
                    continue
                sources = original.get('sources', {})
                if not isinstance(sources, dict) or set(sources) != {'team_data', 'fingerprint_data'}:
                    continue
                valid = True
                for name, route in [('team_data', 'team-data'), ('fingerprint_data', 'fingerprint-data')]:
                    source = sources[name]
                    if not isinstance(source, dict):
                        valid = False
                        break
                    digest = source.get('sha256', '')
                    valid = valid and isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
                    valid = valid and source.get('url') == f'{API}/{route}?league=wcbb&season=2025' and source.get('bytes', 0) > 0
                if not valid or timestamps != {original.get('retrieved_utc')}:
                    continue
                qa.update(sources=sources, retrieved_utc=original['retrieved_utc'])
                return qa
        except (ValueError, TypeError, AttributeError):
            continue
    raise PipelineValidationError('Frozen baseline provenance unavailable or mismatched; restore its original snapshot manifest')


def refresh_repository(root:Path,current_season:int=2026) -> dict:
    """Qualify all required sources before any published file is overwritten."""
    if current_season!=2026:
        raise PipelineValidationError("2026 (academic 2026-27) is the current-season refresh setting")
    cohort=load_cohort(root/"data/reference/cohort_45.csv")
    stage=Path(tempfile.mkdtemp(prefix="wcbb-",dir=root/".staging")) if (root/".staging").is_dir() else None
    if stage is None:
        (root/".staging").mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix="wcbb-",dir=root/".staging"))
    frozen_folder=root/"data/frozen/season=2025"
    baseline_needed=not (frozen_folder/TEAM_FAMILY/"team_season.parquet").exists()
    combined={}
    qa=[]
    try:
        if baseline_needed:
            old,oldqa=fetch_one_season(2025,cohort,stage)
            save_family_tables(old,stage/"frozen/season=2025")
            combined[2025]=old
            qa.append(oldqa)
        else:
            combined[2025]=load_family_tables(frozen_folder)
            qa.append(baseline_qa(root,combined[2025],cohort))
        provenance = stage / 'frozen/season=2025/provenance.json'
        provenance.parent.mkdir(parents=True, exist_ok=True)
        provenance.write_text(json.dumps(qa[0], indent=2), encoding='utf-8')
        current,currentqa=fetch_one_season(current_season,cohort,stage)
        combined[current_season]=current
        qa.append(currentqa)
        prev_player=root/f"data/latest/season={current_season}/{PLAYER_FAMILY}/player_season.parquet"
        if prev_player.is_file():
            old_ids=set(read_parquet(prev_player).player_id.astype(int))
            new_ids=set(current["player_season"].player_id.astype(int))
            changes=compare_snapshot_ids(old_ids,new_ids)
            currentqa["player_identity_changes"]=changes
            if len(changes["removed"])>max(5,int(len(old_ids)*0.1)):
                raise PipelineValidationError("More than 10% of previously known players disappeared; quarantining refresh")
        else:
            currentqa["player_identity_changes"]={"added":[],"removed":[]}
        save_family_tables(current,stage/f"season={current_season}")
        for family,names in FAMILY_TABLES.items():
            for name in names:
                tmp_frames=pd.concat([combined[y][name] for y in sorted(combined)],ignore_index=True)
                write_parquet(tmp_frames,stage/"latest"/family/f"{name}.parquet")
        write_combined_duckdb(combined,cohort,stage/"latest/wcbb_espn_data_families.duckdb",qa)
        run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        manifest={"run_id":run_id,"status":"PASS_WITH_REVIEW" if any(q["status"]=="PASS_WITH_REVIEW" for q in qa) else "PASS",
                  "source_api_seasons":[2025,2026],"current_season":2026,"academic_season":"2026-27",
                  "cohort_count":45,"qa":qa,"snapshot_path":f"data/snapshots/{run_id}",
                  "hex_reference_player_counts_2026_11_23":{"2025":564,"2026":548},
                  "player_count_deltas_from_reference":{"2025":int(len(combined[2025]["player_season"])-564),
                                                        "2026":int(len(combined[2026]["player_season"])-548)},
                  "source_lineage":"ESPN Analytics public /api/team-data and /api/fingerprint-data",
                  "snapshot_policy":"frozen 2025-26, rolling 2026-27; prior files preserved on failed QA",
                  "published_espn_percentiles":False}
        from .features import write_feature_bundle
        players = pd.concat([combined[y]['player_season'] for y in sorted(combined)], ignore_index=True)
        skills = pd.concat([combined[y]['skill_impacts'] for y in sorted(combined)], ignore_index=True)
        feature_qa = write_feature_bundle(players, skills, root, stage/'processed', manifest)
        manifest['processed_features'] = feature_qa
        if feature_qa['status'] == 'PASS_WITH_REVIEW':
            manifest['status'] = 'PASS_WITH_REVIEW'
        manifest['processed_snapshot_path'] = f'data/processed/snapshots/{run_id}'
        from .peers import prepare_peer_bundle
        manifest['peer_benchmarks'] = prepare_peer_bundle(root, stage, manifest)
        from .catalog import write_catalog
        manifest['dataset_catalog'] = write_catalog([
            (stage/'benchmark_publication/latest', 'data/benchmarks/latest'),
            (stage/'processed', 'data/processed'),
            (stage/'latest', 'data/latest'),
            (stage/f'season={current_season}', f'data/latest/season={current_season}'),
            (stage/'frozen/season=2025' if baseline_needed else frozen_folder, 'data/frozen/season=2025'),
        ], stage/'latest/catalog', run_id)
        from .publication import publication_transaction
        targets = [root/'reports/manifest_latest.json', root/manifest['snapshot_path']/'manifest.json']
        mappings = [(stage/'benchmark_publication', root/'data/benchmarks'),
                    (stage/'processed', root/'data/processed'),
                    (stage/'processed', root/manifest['processed_snapshot_path']),
                    (stage/'latest', root/'data/latest'),
                    (stage/f'season={current_season}', root/f'data/latest/season={current_season}'),
                    (stage/f'season={current_season}', root/manifest['snapshot_path']/'season=2026')]
        if baseline_needed:
            mappings.append((stage/'frozen/season=2025', frozen_folder))
        elif not (frozen_folder/'provenance.json').exists():
            targets.append(frozen_folder/'provenance.json')
        for source,destination in mappings:
            targets.extend(destination/p.relative_to(source) for p in source.rglob('*') if p.is_file())
        with publication_transaction(stage, targets):
            # Files are promoted only AFTER complete source collection, QA, exports and DB build.
            if baseline_needed:
                shutil.copytree(stage/"frozen/season=2025",frozen_folder,dirs_exist_ok=False)
            elif not (frozen_folder / 'provenance.json').exists():
                shutil.copy2(provenance, frozen_folder / 'provenance.json')
            for child in (stage/'benchmark_publication').iterdir():
                shutil.copytree(child, root/'data/benchmarks'/child.name, dirs_exist_ok=True)
            processed = root/'data/processed'
            processed.mkdir(parents=True, exist_ok=True)
            shutil.copytree(stage/'processed', root/manifest['processed_snapshot_path'])
            for child in (stage/'processed').iterdir():
                if child.is_dir():
                    shutil.copytree(child, processed/child.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, processed/child.name)
            latest=root/"data/latest"
            latest.mkdir(parents=True,exist_ok=True)
            for child in (stage/"latest").iterdir():
                if child.is_dir():
                    shutil.copytree(child,latest/child.name,dirs_exist_ok=True)
                else:
                    shutil.copy2(child,latest/child.name)
            current_latest=root/f"data/latest/season={current_season}"
            shutil.copytree(stage/f"season={current_season}",current_latest,dirs_exist_ok=True)
            snapshots=root/manifest["snapshot_path"]
            shutil.copytree(stage/f"season={current_season}",snapshots/"season=2026")
            (snapshots/"manifest.json").write_text(json.dumps(manifest,indent=2,default=str),encoding="utf-8")
            (root/"reports").mkdir(parents=True,exist_ok=True)
            (root/"reports/manifest_latest.json").write_text(json.dumps(manifest,indent=2,default=str),encoding="utf-8")
            return manifest
    finally:
        # No raw bytes in the git commit. Workflow separately uploads raw captures as artifact if desired.
        shutil.rmtree(stage,ignore_errors=True)
