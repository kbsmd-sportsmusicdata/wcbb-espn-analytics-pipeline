"""Normalize public WCBB team/fingerprint feed data without inventing missing values."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pandas as pd


class PipelineValidationError(ValueError):
    """A source or join failed a critical quality gate."""


REQUIRED_TEAM_FAMILIES = ("team4f", "team_stats", "bpi_stats", "plyr_stats")
FACTOR_COLS = ("Total", "FB", "FG2", "FG3", "FT", "Putback", "REB", "TOV")


def load_cohort(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    needed = {"espn_team_id", "team_requested", "cohort", "ap_rank"}
    if not needed <= set(frame.columns):
        raise PipelineValidationError("cohort missing required columns")
    frame["espn_team_id"] = pd.to_numeric(frame.espn_team_id, errors="raise").astype("int64")
    if frame.espn_team_id.duplicated().any():
        raise PipelineValidationError("duplicate cohort ESPN team ID")
    if len(frame) != 45 or frame.cohort.value_counts().to_dict() != {"AP_TOP25": 25, "WATCHLIST": 20}:
        raise PipelineValidationError("expected fixed 25 ranked + 20 watchlist schools")
    if 152 not in set(frame.espn_team_id) or 153 not in set(frame.espn_team_id):
        raise PipelineValidationError("both NC State (152) and North Carolina (153) required")
    nc = frame.set_index("espn_team_id")
    if nc.loc[153, "cohort"] != "AP_TOP25" or int(nc.loc[153, "ap_rank"]) != 24 or nc.loc[152, "cohort"] != "WATCHLIST":
        raise PipelineValidationError("NC State / North Carolina cohort classifications changed")
    return frame


def _frame(value: object, name: str) -> pd.DataFrame:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise PipelineValidationError(f"{name} invalid nested JSON") from exc
    if not isinstance(value, list):
        raise PipelineValidationError(f"{name} expected list of row dictionaries")
    return pd.DataFrame(value)


def _assert_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise PipelineValidationError(f"{name} missing required columns: {sorted(missing)}")


def _ids(frame: pd.DataFrame, src: str, dest: str, *, permit_null: bool = False) -> pd.DataFrame:
    frame = frame.copy()
    frame[dest] = pd.to_numeric(frame[src], errors="coerce").astype("Int64")
    if not permit_null and frame[dest].isna().any():
        raise PipelineValidationError(f"{src} has NULL or nonnumeric source ID")
    return frame


def _unique(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    if frame.duplicated(columns).any():
        raise PipelineValidationError(f"duplicate {name} keys: {columns}")


def build_frames(team_data: Mapping[str, object], fingerprints: Mapping[str, object],
                 cohort: pd.DataFrame, api_season: int, retrieved_utc: str) -> dict[str, pd.DataFrame]:
    """Return cohort-filtered source-preserving tables; rank skills across the FULL feed."""
    if api_season not in (2025, 2026):
        raise PipelineValidationError("Supported API seasons: 2025 / 2026")
    missing = set(REQUIRED_TEAM_FAMILIES) - set(team_data)
    if missing:
        raise PipelineValidationError(f"missing team-data families: {sorted(missing)}")
    if not isinstance(fingerprints, Mapping) or not fingerprints:
        raise PipelineValidationError("fingerprint feed must be keyed player dictionary")
    teams = set(pd.to_numeric(cohort.espn_team_id, errors="raise").astype(int))
    academic_season = f"{api_season}-{str(api_season + 1)[-2:]}"
    t4, ts, bpi, ps = (_frame(team_data[k], k) for k in REQUIRED_TEAM_FAMILIES)
    _assert_columns(t4, {"digital_team_id", "Side", *FACTOR_COLS}, "team4f")
    _assert_columns(ts, {"digital_team_id", "GAMES_PLAYED", "EFG"}, "team_stats")
    _assert_columns(bpi, {"TEAM_ID", "BPI", "BPI_OFF", "BPI_DEF"}, "bpi_stats")
    _assert_columns(ps, {"PLYR_ID", "TEAM_ID", "TEAM_NAME", "DISPLAY_NAME", "ONETPTS", "DNETPTS", "TNETPTS"}, "plyr_stats")

    t4 = _ids(t4, "digital_team_id", "team_id")
    ts = _ids(ts, "digital_team_id", "team_id", permit_null=True)
    bpi = _ids(bpi, "TEAM_ID", "team_id")
    ps = _ids(_ids(ps, "PLYR_ID", "player_id"), "TEAM_ID", "team_id")
    unkeyed_team_stats = ts[ts.team_id.isna()].copy()
    unkeyed_team_stats["rejection_reason"] = "MISSING_ESPN_DIGITAL_TEAM_ID"
    _unique(t4, ["team_id", "Side"], "four factor team-side")
    _unique(ts.dropna(subset=["team_id"]), ["team_id"], "team stats")
    _unique(bpi, ["team_id"], "BPI team")
    _unique(ps, ["player_id"], "player")
    f4 = t4[t4.team_id.isin(teams)].copy()
    tv = ts[ts.team_id.isin(teams)].copy()
    bp = bpi[bpi.team_id.isin(teams)].copy()
    p = ps[ps.team_id.isin(teams)].copy()
    if set(f4.team_id.astype(int)) != teams:
        raise PipelineValidationError("four factor: missing cohort team IDs")
    if set(tv.team_id.astype(int)) != teams:
        raise PipelineValidationError("missing cohort team stats")
    if set(bp.team_id.astype(int)) != teams:
        raise PipelineValidationError("missing cohort BPI")
    if set(p.team_id.astype(int)) != teams:
        raise PipelineValidationError("missing cohort player records")
    n_sides = f4.groupby("team_id").Side.agg(lambda x: set(x.astype(str)))
    if any(s != {"Offense", "Defense", "Total"} for s in n_sides):
        raise PipelineValidationError("four factor: expected 3 Offense/Defense/Total sides per team")
    if f4[list(FACTOR_COLS)].isna().any().any():
        raise PipelineValidationError("four factor: cohort values unexpectedly NULL")

    # Site uses digital_team_id rather than its internal team_stat_tmid for ESPN team joins.
    pivot = f4.pivot(index="team_id", columns="Side", values=list(FACTOR_COLS)).reset_index()
    pivot.columns = ["team_id" if a == "team_id" else f"{str(b).lower()}_{str(a).lower()}" for a,b in pivot.columns]
    tcols = [x for x in tv.columns if x not in ("digital_team_id", "team_id")]
    tsjoin = tv[["team_id", *tcols]].rename(columns={x: "team_stat_" + x.lower() for x in tcols})
    bcols = [x for x in bp.columns if x not in ("TEAM_ID", "team_id")]
    bpjoin = bp[["team_id", *bcols]].rename(columns={x: "bpi_" + x.lower() for x in bcols})
    team_season = pivot.merge(tsjoin, on="team_id", how="left", validate="one_to_one")
    team_season = team_season.merge(bpjoin, on="team_id", how="left", validate="one_to_one")
    names = p.groupby("team_id", as_index=False).TEAM_NAME.first().rename(columns={"TEAM_NAME": "espn_team_name"})
    team_season = team_season.merge(names, on="team_id", how="left", validate="one_to_one")
    team_season["team_net_points_off"] = team_season.offense_total
    team_season["team_net_points_def"] = team_season.defense_total
    team_season["team_net_points_total"] = team_season.total_total
    team_season["netpoints_additivity_delta"] = team_season.total_total - team_season.offense_total - team_season.defense_total

    # Fingerprint provider IDs must match primary player IDs; keep TEAM_ID from both sources.
    records=[]
    skill_rows=[]
    for key, raw in fingerprints.items():
        if not isinstance(raw, dict):
            raise PipelineValidationError("fingerprint record must be dict")
        try:
            pid=int(key)
        except (TypeError,ValueError) as exc:
            raise PipelineValidationError("fingerprint player id not integer") from exc
        rec={"player_id":pid,"fingerprint_team_id":pd.to_numeric(raw.get("tm_id"),errors="coerce"),
             "fingerprint_player_name":raw.get("displayName"),"fingerprint_possessions":raw.get("tPoss"),
             "fingerprint_minutes":raw.get("minutes_played"),"fingerprint_games":raw.get("games_played"),
             "fingerprint_usage":raw.get("offensive_usage"),"fingerprint_assisted_rate":raw.get("assisted_rate"),
             "fingerprint_avg_position":raw.get("average_position"),
             "fingerprint_off_raw":raw.get("total_oNetPts"),"fingerprint_def_raw":raw.get("total_dNetPts"),
             "fingerprint_total_raw":raw.get("total_tNetPts")}
        records.append(rec)
        for name, value in raw.items():
            if name.endswith("_tNetPts") and name != "total_tNetPts":
                skill = name[:-len("_tNetPts")]
                skill_rows.append({"player_id":pid,"skill":skill,"impact_off_raw":raw.get(skill+"_oNetPts"),
                                   "impact_def_raw":raw.get(skill+"_dNetPts"),"impact_total_raw":value,
                                   "source_possessions":raw.get("tPoss")})
    meta = pd.DataFrame(records)
    _unique(meta,["player_id"],"fingerprint")
    fp_skills = pd.DataFrame(skill_rows)
    if fp_skills.empty:
        raise PipelineValidationError("fingerprint: no skill impact categories")
    _unique(fp_skills,["player_id","skill"],"skill impact")
    for part in ("off","def","total"):
        value=f"impact_{part}_raw"
        fp_skills[value]=pd.to_numeric(fp_skills[value],errors="coerce")
        fp_skills[f"computed_{part}_league_pctile"] = fp_skills.groupby("skill")[value].rank(pct=True,method="average") * 100
        fp_skills[f"league_{part}_n"] = fp_skills.groupby("skill")[value].transform("count")
    fp_skills["percentile_method"] = "COMPUTED_FULL_FEED_API_SEASON_BY_SKILL_NOT_PUBLISHED_ESPN"
    p = p.merge(meta,on="player_id",how="left",validate="one_to_one")
    if p.fingerprint_player_name.isna().any():
        raise PipelineValidationError("fingerprint missing for selected cohort player ID")
    p["fingerprint_team_id"] = pd.to_numeric(p.fingerprint_team_id,errors="coerce").astype("Int64")
    p["fingerprint_team_id_disagrees"] = p.team_id.ne(p.fingerprint_team_id).fillna(True)
    p["netpoints_additivity_delta"] = pd.to_numeric(p.TNETPTS,errors="coerce")-pd.to_numeric(p.ONETPTS,errors="coerce")-pd.to_numeric(p.DNETPTS,errors="coerce")
    selected = set(p.player_id.astype(int))
    skill_out = fp_skills[fp_skills.player_id.isin(selected)].copy()
    if set(skill_out.player_id.astype(int)) != selected:
        raise PipelineValidationError("fingerprint skill impacts missing for cohort player")
    diff = p[p.fingerprint_team_id_disagrees][["player_id","team_id","fingerprint_team_id","DISPLAY_NAME","fingerprint_player_name"]].copy()
    diff["reason"]="SOURCE_PLAYER_TEAM_ID_DIFFERS_FROM_FINGERPRINT_TEAM_ID"
    if (team_season.netpoints_additivity_delta.abs()>0.15).any():
        raise PipelineValidationError("team Net Points source component delta exceeds tolerance 0.15")
    if (p.netpoints_additivity_delta.abs()>0.15).any():
        raise PipelineValidationError("player Net Points source component delta exceeds tolerance 0.15")
    if (team_season.bpi_bpi.isna()).any() or (team_season.team_stat_efg.isna()).any():
        raise PipelineValidationError("BPI or eFG% NULL for selected cohort")
    cohort_meta = cohort[["espn_team_id","team_requested","cohort","ap_rank"]].rename(columns={"espn_team_id":"team_id"})
    def decorate(frame:pd.DataFrame, *, key="team_id") -> pd.DataFrame:
        if key=="team_id":
            frame=frame.merge(cohort_meta,on="team_id",how="left",validate="many_to_one")
        frame["api_season"]=int(api_season)
        frame["academic_season"]=academic_season
        frame["retrieval_utc"]=retrieved_utc
        frame["team_data_source_url"]=f"https://espnanalytics.com/api/team-data?league=wcbb&season={api_season}"
        frame["fingerprint_source_url"]=f"https://espnanalytics.com/api/fingerprint-data?league=wcbb&season={api_season}"
        return frame
    team_season=decorate(team_season)
    four=decorate(f4)
    # DuckDB treats TEAM_ID and team_id as the same identifier, even when quoted.
    # Preserve the original value under a distinct name before exporting.
    bpi_out=decorate(bp.rename(columns={"TEAM_ID":"source_team_id"}))
    unkeyed_team_stats=decorate(unkeyed_team_stats,key="unkeyed")
    players=decorate(p.rename(columns={"TEAM_ID":"source_team_id"}))
    skill_out=skill_out.merge(players[["player_id","team_id","team_requested","cohort","ap_rank"]],on="player_id",how="left",validate="many_to_one")
    skill_out=decorate(skill_out,key="player_id")
    diff=diff.merge(players[["player_id","team_requested","cohort"]],on="player_id",validate="one_to_one")
    diff=decorate(diff,key="player_id")
    # Empty frames can be safely materialized into DuckDB with supplied schema.
    if diff.empty:
        diff=pd.DataFrame(columns=list(diff.columns))
    return {"team_season":team_season,"four_factors":four,"bpi":bpi_out,
            "unkeyed_team_stats":unkeyed_team_stats,
            "player_season":players,"skill_impacts":skill_out,"team_id_discrepancies":diff}
