import pandas as pd
import pytest
from pathlib import Path
from wcbb_espn.d1 import attach_membership, raw_d1_skill_reference, attach_raw_d1_skill_ranks, load_membership, reconcile
from wcbb_espn.pipeline import PipelineValidationError
import json
ROOT=Path(__file__).resolve().parents[1]

def test_supplied_membership_counts_and_verified_overrides():
    c=json.loads((ROOT/'data/reference/peer_benchmark_rules_v2.json').read_text())
    m,h=load_membership(ROOT,c)
    assert m.groupby('api_season').size().to_dict()=={2025:363,2026:363}
    assert not m.duplicated(['api_season','team_id']).any()
    assert m.is_ncaa_d1.all()
    assert set(m.loc[(m.api_season==2025)&m.division_verification_status.str.contains('override'),'team_id'])=={2385,2698}
    assert m.loc[(m.api_season==2025)&m.team_id.eq(2698),'conference_name'].iloc[0]=='Atlantic Sun Conference'
    assert m.loc[(m.api_season==2026)&m.team_id.eq(2698),'conference_name'].iloc[0]=='United Athletic Conference'

def test_membership_join_and_d1_raw_ranks():
    m=pd.DataFrame({'api_season':[2026,2026],'team_id':[1,2],'is_ncaa_d1':[True,True]})
    p=pd.DataFrame({'api_season':[2026]*3,'player_id':[11,22,33],'team_id':[1,2,3],'TEAM_NAME':['A','B','C']})
    out=attach_membership(p,m)
    assert out.player_id.tolist()==[11,22]
    with pytest.raises(PipelineValidationError):attach_membership(p,m,strict=True)
    ledger=reconcile(p,m,{})
    assert ledger.loc[ledger.team_id.eq(3),'membership_match_status'].iloc[0].startswith('Outside')
    assert not ledger.loc[ledger.team_id.eq(3),'is_ncaa_d1'].iloc[0]
    s=p.assign(skill='assist',impact_off_raw=[1.,2.,100.],impact_def_raw=[0.,1.,100.],impact_total_raw=[1.,3.,200.])
    d=attach_membership(s,m)
    r=raw_d1_skill_reference(d)
    a=attach_raw_d1_skill_ranks(d,r)
    assert a.computed_off_d1_league_pctile.tolist()==[50.,100.]
    assert a.d1_league_off_n.tolist()==[2,2]
    d.loc[0,'impact_off_raw']=99.
    assert pd.isna(attach_raw_d1_skill_ranks(d,r).computed_off_d1_league_pctile.iloc[0])

def test_missing_reference_team_blocks():
    m=pd.DataFrame({'api_season':[2026,2026],'team_id':[1,2]})
    p=pd.DataFrame({'api_season':[2026],'team_id':[1],'player_id':[11],'TEAM_NAME':['A']})
    with pytest.raises(PipelineValidationError,match='absent'):reconcile(p,m,{})
