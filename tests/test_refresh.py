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
