from pathlib import Path
import json
import pytest
from wcbb_espn.refresh import parse_response, summarize_qa, compare_snapshot_ids
from wcbb_espn.pipeline import PipelineValidationError
from test_pipeline import synthetic, small_cohort
from wcbb_espn.pipeline import build_frames


def test_team_response_parses_nested_strings_without_altering_source():
    team_data,_=synthetic()
    as_strings={key:json.dumps(rows) for key,rows in team_data.items()}
    result=parse_response(as_strings)
    assert result['team_stats'][0]['digital_team_id']==152
    assert result['plyr_stats'][0]['PLYR_ID']==501


def test_invalid_feed_json_blocks():
    with pytest.raises(PipelineValidationError,match='invalid JSON'):
        parse_response({**synthetic()[0], 'team4f':'broken'})


@pytest.mark.parametrize('encoded', [False, True])
def test_column_indexed_families_preserve_rows_and_align_by_source_index(encoded):
    expected, _ = synthetic()
    payload = {}
    for family, records in expected.items():
        columns = {}
        for column_number, column in enumerate(records[0]):
            cells = [(str(7 + row * 3), record[column]) for row, record in enumerate(records)]
            # A column's insertion order must never change which values belong together.
            columns[column] = dict(reversed(cells) if column_number % 2 else cells)
        payload[family] = json.dumps(columns) if encoded else columns
    actual = parse_response(payload)
    assert actual == expected
    assert actual['plyr_stats'][0]['PLYR_ID'] == 501
    assert actual['plyr_stats'][0]['TEAM_ID'] == 152


def test_column_indexed_family_with_different_row_indices_blocks():
    payload = synthetic()[0]
    payload['bpi_stats'] = {'TEAM_ID': {'0': 152, '1': 153}, 'BPI': {'0': 15.0}}
    with pytest.raises(PipelineValidationError, match='bpi_stats.*row indices'):
        parse_response(payload)


@pytest.mark.parametrize('invalid', [{}, {'TEAM_ID': {}}, {'TEAM_ID': {'0': 152}, 'BPI': []}])
def test_empty_or_malformed_column_families_still_block(invalid):
    with pytest.raises(PipelineValidationError, match='bpi_stats'):
        parse_response({**synthetic()[0], 'bpi_stats': invalid})


def test_saved_baseline_reloads_canonical_and_original_team_ids(tmp_path):
    from wcbb_espn.refresh import save_family_tables, load_family_tables

    td, fp = synthetic()
    expected = build_frames(td, fp, small_cohort(), 2025, '2026-11-23T18:00:00Z')
    folder = tmp_path / 'season=2025'
    save_family_tables(expected, folder)
    restored = load_family_tables(folder)
    for table in ('team_season', 'four_factors', 'bpi', 'player_season', 'skill_impacts'):
        assert list(restored[table].columns) == list(expected[table].columns)
        assert restored[table]['team_id'].tolist() == expected[table]['team_id'].tolist()
    for table in ('bpi', 'player_season'):
        assert restored[table]['source_team_id'].tolist() == [152, 153]
    assert summarize_qa(restored, small_cohort(), 2025)['status'] == 'PASS'


def test_qa_reports_same_provider_id_disagreements_as_review():
    td,fp=synthetic();fp['501']['tm_id']=153
    out=build_frames(td,fp,small_cohort(),2026,'2026-11-23T18:00:00Z')
    qa=summarize_qa(out,small_cohort(),2026)
    assert qa['status']=='PASS_WITH_REVIEW'
    assert qa['team_id_discrepancies']==1
    assert qa['team_count']==2
    assert qa['player_count']==2


def test_missing_team_ids_fail_qa():
    td,fp=synthetic()
    out=build_frames(td,fp,small_cohort(),2026,'2026-11-23T18:00:00Z')
    out['team_season']=out['team_season'][out['team_season'].team_id!=153]
    with pytest.raises(PipelineValidationError,match='45-team|team count'):
        summarize_qa(out,small_cohort(),2026)


def test_delta_reports_players_added_removed():
    old={501,502}
    new={502,503}
    changes=compare_snapshot_ids(old,new)
    assert changes=={'added':[503],'removed':[501]}


def test_refresh_recovers_and_retains_frozen_source_provenance(tmp_path, monkeypatch):
    import hashlib
    from datetime import datetime, timezone
    import wcbb_espn.refresh as refresh

    import shutil
    reference = tmp_path / 'data/reference'
    reference.mkdir(parents=True)
    for name in ['player_feature_rules_v1.json','skill_taxonomy_v1.csv']:
        shutil.copy2(Path(__file__).resolve().parents[1]/'data/reference'/name, reference/name)
    td, fp = synthetic()
    cohort = small_cohort()
    calls = []
    clock = [datetime(2026, 11, 23, 20, 0, 0, tzinfo=timezone.utc)]

    class Clock:
        @staticmethod
        def now(tz):
            return clock[0]

    def fetch(season, cohort, staging):
        calls.append(season)
        at = '2026-11-23T18:00:00Z' if season == 2025 else clock[0].strftime('%Y-%m-%dT%H:%M:%SZ')
        frames = build_frames(td, fp, cohort, season, at)
        frames['skill_impacts']['skill'] = frames['skill_impacts']['skill'].replace({'passing':'assist'})
        qa = summarize_qa(frames, cohort, season)
        qa.update(retrieved_utc=at, sources={name: {
            'url': f'{refresh.API}/{route}?league=wcbb&season={season}',
            'sha256': hashlib.sha256(name.encode()).hexdigest(), 'bytes': 1234
        } for name, route in [('team_data', 'team-data'), ('fingerprint_data', 'fingerprint-data')]})
        return frames, qa

    import wcbb_espn.peers as peers
    def peer_stub(root,stage,manifest):
        (stage/'benchmark_publication').mkdir()
        return {'status':'PASS'}
    monkeypatch.setattr(peers, 'prepare_peer_bundle', peer_stub)
    monkeypatch.setattr(refresh, 'load_cohort', lambda path: cohort)
    monkeypatch.setattr(refresh, 'fetch_one_season', fetch)
    monkeypatch.setattr(refresh, 'datetime', Clock)
    first = refresh.refresh_repository(tmp_path)
    sidecar = tmp_path / 'data/frozen/season=2025/provenance.json'
    assert json.loads(sidecar.read_text())['sources'] == first['qa'][0]['sources']
    frozen = {p: p.read_bytes() for p in sidecar.parent.rglob('*.parquet')}
    sidecar.unlink()  # Existing repositories have only the original snapshot manifest.
    for second in (1, 2):
        calls.clear()
        clock[0] = clock[0].replace(second=second)
        result = refresh.refresh_repository(tmp_path)
        assert calls == [2026]
        assert result['qa'][0]['sources'] == first['qa'][0]['sources']
        assert result['qa'][0]['retrieved_utc'] == '2026-11-23T18:00:00Z'
        assert all(p.read_bytes() == content for p, content in frozen.items())
        assert json.loads(sidecar.read_text())['sources'] == first['qa'][0]['sources']


    # A critical processed-data failure must leave every published source/feature file intact.
    import wcbb_espn.features as features
    previous = {p: p.read_bytes() for folder in ['data/latest','data/frozen','data/processed','reports']
                for p in (tmp_path/folder).rglob('*') if p.is_file()}
    def fail_features(*args, **kwargs):
        raise PipelineValidationError('critical feature QA failure')
    original_build = features.build_features
    monkeypatch.setattr(features, 'build_features', fail_features)
    clock[0] = clock[0].replace(second=3)
    with pytest.raises(PipelineValidationError, match='critical feature QA'):
        refresh.refresh_repository(tmp_path)
    assert all(p.read_bytes() == content for p,content in previous.items())
    assert {p for folder in ['data/latest','data/frozen','data/processed','reports']
            for p in (tmp_path/folder).rglob('*') if p.is_file()} == set(previous)


    monkeypatch.setattr(features, 'build_features', original_build)
    original_copy = shutil.copy2
    failed = [False]
    def fail_mid_copy(source, destination, *args, **kwargs):
        if Path(destination) == tmp_path/'data/processed/player_skill_features.parquet' and not failed[0]:
            failed[0] = True
            raise OSError('simulated publication copy failure')
        return original_copy(source, destination, *args, **kwargs)
    monkeypatch.setattr(shutil, 'copy2', fail_mid_copy)
    clock[0] = clock[0].replace(second=4)
    with pytest.raises(OSError, match='publication copy failure'):
        refresh.refresh_repository(tmp_path)
    assert failed[0]
    assert all(p.read_bytes() == content for p,content in previous.items())
    assert {p for folder in ['data/latest','data/frozen','data/processed','reports']
            for p in (tmp_path/folder).rglob('*') if p.is_file()} == set(previous)


    def phase2_failure(*args):
        raise PipelineValidationError('critical Phase 2 benchmark QA')
    monkeypatch.setattr(peers, 'prepare_peer_bundle', phase2_failure)
    clock[0] = clock[0].replace(second=5)
    with pytest.raises(PipelineValidationError, match='Phase 2 benchmark QA'):
        refresh.refresh_repository(tmp_path)
    assert all(p.read_bytes() == content for p,content in previous.items())


@pytest.mark.parametrize('record', [None, {'api_season': 2025, 'retrieved_utc': 'wrong'},
                                   {'api_season': 2025, 'retrieved_utc': '2026-11-23T18:00:00Z',
                                    'sources': {'team_data': {'sha256': 'bad'}}}])
def test_missing_or_mismatched_baseline_provenance_blocks(tmp_path, record):
    from wcbb_espn.refresh import baseline_qa
    td, fp = synthetic()
    frames = build_frames(td, fp, small_cohort(), 2025, '2026-11-23T18:00:00Z')
    if record is not None:
        sidecar = tmp_path / 'data/frozen/season=2025/provenance.json'
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text(json.dumps(record))
    with pytest.raises(PipelineValidationError, match='baseline provenance'):
        baseline_qa(tmp_path, frames, small_cohort())
