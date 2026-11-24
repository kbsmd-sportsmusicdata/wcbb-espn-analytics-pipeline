from pathlib import Path
import copy
import numpy as np
import pandas as pd
import pytest
from wcbb_espn.peers import build_peer_features, load_peer_rules
from wcbb_espn.pipeline import PipelineValidationError
ROOT=Path(__file__).resolve().parents[1]

def fixtures():
    config=load_peer_rules(ROOT); config['minimum_peer_n']=3; config['minimum_full_source_players']=0
    rows=[];skills=[]
    for year in [2025,2026]:
        for i in range(12):
            rows.append(dict(api_season=year,academic_season=f'{year}-{str(year+1)[-2:]}',player_id=year*100+i,team_id=i+1,position_group='Guard',usage_pct=float(i),EFG=40.+i,AST_40=float(i),REB_40=float(i),FTR=.2,turnover_pct_display=float(i),assisted_rate_pct=50.,fingerprint_impact_off_per100=float(i),fingerprint_impact_def_per100=float(i),fingerprint_impact_total_per100=float(i),fingerprint_possessions=1000.,fingerprint_minutes=500.,GAMES_PLAYED=20,fingerprint_games=20,identity_consistency_status='Agreement',feature_qa_flags='',evidence_status='Ready'))
            skills.append(dict(api_season=year,player_id=year*100+i,team_id=i+1,skill='assist',skill_impact_total_per100=float(i),skill_impact_off_per100=float(i),skill_impact_def_per100=0.,computed_total_league_pctile=99.,league_total_n=5000))
    p=pd.DataFrame(rows);s=pd.DataFrame(skills)
    meta={y:{'retrieved_utc':f'{y}-11-23T00:00:00Z','input_vintage':'Historical re-extraction' if y==2025 else 'Current ingestion response','sources':{'team_data':{'sha256':str(y)},'fingerprint_data':{'sha256':str(y)}}} for y in [2025,2026]}
    return p,s,config,meta

def build(p=None,s=None,selected=None):
    pp,ss,c,m=fixtures();p=pp if p is None else p;s=ss if s is None else s
    out=p[p.player_id.isin([202500,202511,202600,202611])].copy() if selected is None else selected
    sk=s.merge(out[['api_season','player_id']],on=['api_season','player_id'])
    return build_peer_features(out,sk,p,s,c,m,'test-run')

def test_full_population_not_selected_cohort_and_no_leakage():
    p,s,_,_=fixtures();a,b,r,q=build()
    assert a.usage_position_pctile.tolist()==[100/12,100.,100/12,100.]
    assert a.position_benchmark_n.tolist()==[12]*4
    assert a.usage_position_pctile.iloc[0]!=50.
    assert a.usage_role_band.tolist()==['Lower usage','Higher usage']*2
    assert a.role_peer_n.tolist()==[4]*4
    assert a.usage_position_pctile.iloc[0]==100/12 # not ranked inside usage band
    pd.testing.assert_frame_equal(a[p.columns],p[p.player_id.isin(a.player_id)].reset_index(drop=True))
    assert b.computed_total_league_pctile.eq(99.).all()
    assert b.league_total_n.eq(5000).all()
    assert r.reference_population.eq('Full ESPN WCBB provider player feed; not independently verified NCAA roster coverage').all()

def test_ties_null_denominators_and_direction():
    p,s,_,_=fixtures();p.loc[p.api_season.eq(2026),'usage_pct']=5.
    a,b,r,q=build(p,s)
    assert a.loc[a.api_season.eq(2026),'usage_position_pctile'].isna().all() # constant distribution suppressed
    assert a.loc[a.api_season.eq(2026),'usage_role_band'].eq('Typical usage').all()
    p.loc[p.player_id.eq(202611),'EFG']=np.nan
    a,_,_,_=build(p,s)
    assert a.loc[a.player_id.eq(202611),'efg_position_status'].iloc[0]=='Missing metric'
    assert a.loc[a.player_id.eq(202600),'efg_position_n'].iloc[0]==11
    assert a.loc[a.player_id.eq(202511),'tov_position_pctile'].iloc[0]==100 # statistical high means high turnover

def test_small_unknown_ineligible_and_historical_drift_suppress():
    p,s,_,_=fixtures();selected=p[p.player_id.isin([202500,202600])].copy()
    selected.loc[selected.api_season.eq(2025),'EFG']=149.
    p.loc[p.player_id.eq(202600),'fingerprint_minutes']=1.
    selected.loc[selected.api_season.eq(2026),'fingerprint_minutes']=1.
    a,_,_,_=build(p,s,selected)
    assert a.efg_position_pctile.isna().all()
    assert a.loc[a.api_season.eq(2025),'efg_position_status'].iloc[0]=='Source vintage mismatch'
    assert a.loc[a.api_season.eq(2026),'position_benchmark_eligible'].iloc[0]==False
    p['position_group']='Unknown'
    a,_,_,_=build(p,s)
    assert a.usage_position_pctile.isna().all()

def test_negative_contribution_never_strength():
    p,s,_,_=fixtures();s['skill_impact_off_per100']=-12.+(s.player_id%100);s['skill_impact_total_per100']=s.skill_impact_off_per100
    a,b,_,_=build(p,s)
    assert a.functional_strength_tags.eq('[]').all()
    assert b.functional_strength_tag.isna().all()
    assert b.loc[b.player_id.eq(202611),'skill_statistical_distinction'].iloc[0]=='Relative statistical distinction; not confirmed strength'

def test_identity_review_and_duplicate_or_orphan_block():
    p,s,_,_=fixtures();p.loc[p.player_id.eq(202600),'identity_consistency_status']='Review required'
    a,_,_,_=build(p,s);assert not a.loc[a.player_id.eq(202600),'position_benchmark_eligible'].iloc[0]
    with pytest.raises(PipelineValidationError):build(pd.concat([p,p]),s)
    s.loc[0,'team_id']=999
    with pytest.raises(PipelineValidationError):build(p,s)

def test_sparse_role_groups_do_not_pool_positions_and_positive_tags():
    p,s,c,m=fixtures();c['minimum_peer_n']=8
    chosen=p[p.player_id.isin([202511,202611])].copy();sk=s[s.player_id.isin(chosen.player_id)]
    a,b,r,q=build_peer_features(chosen,sk,p,s,c,m,'run')
    assert a.usage_position_pctile.eq(100.).all()
    assert a.role_peer_n.eq(4).all()
    assert a.efg_role_pctile.isna().all()
    assert a.role_benchmark_status.eq('Insufficient peers').all()
    assert a.functional_strength_tags.eq('["Creation / playmaking"]').all()
    assert b.functional_strength_status.str.contains('film review').all()


def test_exact_zero_denominator_not_eligible_and_source_season_mismatch():
    p,s,c,m=fixtures();p.loc[p.player_id.eq(202600),'fingerprint_possessions']=0
    a,_,_,_=build(p,s)
    assert a.loc[a.player_id.eq(202600),'usage_position_pctile'].isna().all()
    p.loc[p.player_id.eq(202500),'EFG']=999
    a,_,_,_=build(p,s)
    assert a.loc[a.player_id.eq(202500),'efg_position_pctile'].isna().all()
    assert a.loc[a.player_id.eq(202600),'usage_position_n'].iloc[0]==11


def test_full_source_extraction_covers_unselected_players_and_hashes(tmp_path,monkeypatch):
    import json,hashlib,shutil
    import wcbb_espn.refresh as refresh
    from wcbb_espn.full_source import capture_population,load_population
    from test_pipeline import synthetic
    td,fp=synthetic()
    for record in fp.values():
        for field in list(record):
            if field.startswith('passing_'):record[field.replace('passing_','assist_')]=record.pop(field)
    ref=tmp_path/'data/reference';ref.mkdir(parents=True)
    for name in ['player_feature_rules_v1.json','skill_taxonomy_v1.csv','peer_benchmark_rules_v1.json']:
        shutil.copy2(ROOT/'data/reference'/name,ref/name)
    c=json.loads((ref/'peer_benchmark_rules_v1.json').read_text());c['minimum_full_source_players']=0
    (ref/'peer_benchmark_rules_v1.json').write_text(json.dumps(c))
    taxonomy=pd.read_csv(ref/'skill_taxonomy_v1.csv');taxonomy[taxonomy.skill.eq('assist')].to_csv(ref/'skill_taxonomy_v1.csv',index=False)
    stage=tmp_path/'stage';rawdir=stage/'raw';rawdir.mkdir(parents=True)
    sources={}
    for name,payload in [('team_data',td),('fingerprint_data',fp)]:
        raw=json.dumps(payload).encode();(rawdir/f'{name}_2026.json').write_bytes(raw)
        sources[name]={'sha256':hashlib.sha256(raw).hexdigest()}
    p,s,meta,folder=capture_population(tmp_path,stage,2026,{'sources':sources,'retrieved_utc':'original-time'})
    assert len(p)==2 and len(s)==2
    assert meta['sources']['team_data']['sha256']==sources['team_data']['sha256']
    assert meta['retrieved_utc']=='original-time'
    assert meta['input_vintage']=='Current ingestion response'
    (folder/'players.parquet').write_bytes(b'corrupt')
    with pytest.raises(PipelineValidationError,match='cache hash'):
        load_population(folder)
    sources['team_data']['sha256']='bad'
    with pytest.raises(PipelineValidationError,match='hash mismatch'):
        capture_population(tmp_path,stage,2026,{'sources':sources,'retrieved_utc':'new-time'})


def test_incomplete_full_source_skills_block():
    p,s,c,m=fixtures()
    s=s.iloc[1:].copy()
    with pytest.raises(PipelineValidationError,match='missing skills'):
        build(p,s)
