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
