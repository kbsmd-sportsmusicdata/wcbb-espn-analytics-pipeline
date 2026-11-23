from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from wcbb_espn.features import build_features, load_feature_rules
from wcbb_espn.pipeline import PipelineValidationError
ROOT=Path(__file__).resolve().parents[1]

def inputs():
    p=pd.DataFrame([dict(api_season=2026,player_id=501,team_id=152,source_team_id=152,DISPLAY_NAME='Ana García',fingerprint_player_name='Ana Garcia',fingerprint_team_id=152,
        fingerprint_possessions=200.,fingerprint_off_raw=10.,fingerprint_def_raw=5.,fingerprint_total_raw=15.,fingerprint_minutes=210.,fingerprint_games=10,
        fingerprint_usage=.2,fingerprint_assisted_rate=.75,MIN_PLAYED=21.,GAMES_PLAYED=10,POSITION='G',AVG_POSITION=2.,**{'TOV%':.12},ONETPTS=1.,DNETPTS=.5,TNETPTS=1.5,retrieval_utc='2026-11-23T20:54:48Z')])
    s=pd.DataFrame([dict(api_season=2026,player_id=501,team_id=152,skill='assist',source_possessions=200.,impact_off_raw=2.,impact_def_raw=-1.,impact_total_raw=1.,computed_total_league_pctile=75.,league_total_n=5000,percentile_method='COMPUTED_FULL_FEED_API_SEASON_BY_SKILL_NOT_PUBLISHED_ESPN',retrieval_utc='2026-11-23T20:54:48Z')])
    return p,s

def build(p=None,s=None):
    a,b=inputs(); rules,taxonomy=load_feature_rules(ROOT)
    return build_features(a if p is None else p,b if s is None else s,rules,taxonomy)

def test_formulas_and_source_preservation():
    p,s=inputs();a,b,q=build(p,s)
    pd.testing.assert_frame_equal(a[p.columns],p);pd.testing.assert_frame_equal(b[s.columns],s)
    assert a.fingerprint_impact_total_per100.iloc[0]==7.5
    assert a.fingerprint_impact_off_per100.iloc[0]==5.
    assert a.minutes_total_est.iloc[0]==210.
    assert a.minutes_share_est.iloc[0]==.525
    assert a.usage_pct.iloc[0]==20.
    assert a.assisted_rate_pct.iloc[0]==75.
    assert a.turnover_pct_display.iloc[0]==12.
    assert b.skill_impact_total_per100.iloc[0]==.5
    assert b.functional_skill_group.iloc[0]=='Creation / playmaking'
    assert a.identity_consistency_status.iloc[0]=='Agreement'
    assert a.evidence_status.iloc[0]=='Ready'
    assert a.season_status.iloc[0]=='Partial season'
    assert b.league_total_n.iloc[0]==5000

@pytest.mark.parametrize('poss',[0,-1,np.nan,np.inf])
def test_invalid_denominator_propagates_null(poss):
    p,s=inputs();p['fingerprint_possessions']=poss;s['source_possessions']=poss
    a,b,q=build(p,s)
    assert a.fingerprint_impact_total_per100.isna().all()
    assert b.skill_impact_total_per100.isna().all()
    assert a.evidence_status.iloc[0]=='Missing key metric'
    assert not np.isinf(a.loc[:,~a.columns.isin(p.columns)].select_dtypes('number').to_numpy(dtype=float)).any()

@pytest.mark.parametrize('field',['fingerprint_usage','fingerprint_assisted_rate','TOV%'])
def test_invalid_fractions_not_clipped(field):
    p,s=inputs();p[field]=1.2
    a,b,q=build(p,s)
    dest={'fingerprint_usage':'usage_pct','fingerprint_assisted_rate':'assisted_rate_pct','TOV%':'turnover_pct_display'}[field]
    assert pd.isna(a[dest].iloc[0]);assert a[field].iloc[0]==1.2
    assert a.evidence_status.iloc[0]=='Missing key metric'

def test_inadequate_sample_and_identity_review():
    p,s=inputs();p['fingerprint_minutes']=10.;p['MIN_PLAYED']=5.;p['GAMES_PLAYED']=2;p['fingerprint_games']=2
    a,_,_=build(p,s);assert a.evidence_status.iloc[0]=='Small sample';assert a.creation_context.iloc[0]=='Unknown'
    p['fingerprint_team_id']=153
    a,_,_=build(p,s);assert a.evidence_status.iloc[0]=='Identity review'
    p['fingerprint_team_id']=152;p['fingerprint_player_name']='Different Player'
    a,_,_=build(p,s);assert a.identity_consistency_status.iloc[0]=='Review required'

def test_duplicates_unknown_skills_orphans_block():
    p,s=inputs()
    with pytest.raises(PipelineValidationError):build(pd.concat([p,p]),s)
    with pytest.raises(PipelineValidationError):build(p,pd.concat([s,s]))
    s['skill']='new_unknown_skill'
    with pytest.raises(PipelineValidationError):build(p,s)
    s['skill']='assist';s['team_id']=153
    with pytest.raises(PipelineValidationError):build(p,s)

def test_boundaries_and_missing_position():
    p,s=inputs();p['MIN_PLAYED']=28.;p['fingerprint_assisted_rate']=.4
    a,_,_=build(p,s);assert a.playing_time_tier.iloc[0]=='Rotation anchor';assert a.creation_context.iloc[0]=='More self-created'
    p['MIN_PLAYED']=16.;p['POSITION']=None;p['fingerprint_off_raw']=-3.;p['fingerprint_def_raw']=2.;p['fingerprint_total_raw']=-1.
    a,_,_=build(p,s);assert a.position_group.iloc[0]=='Unknown';assert a.impact_balance.iloc[0]=='Mixed-sign'


def test_export_bundle_round_trip_and_lineage(tmp_path):
    from wcbb_espn.features import write_feature_bundle
    from wcbb_espn.refresh import read_parquet
    import json,hashlib
    p,s=inputs()
    qa=write_feature_bundle(p,s,ROOT,tmp_path,{'run_id':'test-source','qa':[{'api_season':2026,'sources':{'team_data':{'sha256':'a'*64}}}]})
    actual=read_parquet(tmp_path/'player_features.parquet')
    pd.testing.assert_frame_equal(actual[p.columns],p)
    assert len(pd.read_csv(tmp_path/'player_skill_features.csv'))==1
    assert qa['source_run_id']=='test-source'
    assert qa['source_qa'][0]['sources']['team_data']['sha256']=='a'*64
    assert (tmp_path/'season=2026/player_features.parquet').is_file()
    for path,digest in qa['output_sha256'].items():
        assert hashlib.sha256((tmp_path/path).read_bytes()).hexdigest()==digest


def test_missing_inputs_and_historical_labels():
    p,s=inputs();p['api_season']=2025;s['api_season']=2025
    p['fingerprint_assisted_rate']=np.nan;p['fingerprint_minutes']=np.nan
    a,_,_=build(p,s)
    assert a.season_status.iloc[0]=='Frozen historical baseline'
    assert a.evidence_status.iloc[0]=='Missing key metric'
    assert a.minutes_sample_tier.iloc[0]=='Unknown'
    assert a.creation_context.iloc[0]=='Unknown'
