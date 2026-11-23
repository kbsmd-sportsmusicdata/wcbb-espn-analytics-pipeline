import copy
from pathlib import Path
import pandas as pd
import pytest

from wcbb_espn.pipeline import load_cohort, build_frames, PipelineValidationError

ROOT = Path(__file__).resolve().parents[1]


def small_cohort():
    return pd.DataFrame([
        {'espn_team_id': 152, 'team_requested': 'NC State', 'cohort': 'WATCHLIST', 'ap_rank': None},
        {'espn_team_id': 153, 'team_requested': 'North Carolina', 'cohort': 'AP_TOP25', 'ap_rank': 24},
    ])


def synthetic():
    teams = [152,153]
    t4 = []
    for tid in teams:
        for side, total in [('Offense', 20.0),('Defense', 12.0),('Total', 32.01)]:
            t4.append({'digital_team_id': tid,'Side': side, 'Total':total,'FB':1.0,'FG2':2.0,'FG3':3.0,'FT':4.0,'Putback':5.0,'REB':6.0,'TOV':7.0})
    ts = [{'digital_team_id': t,'tmID':t,'tmName':str(t),'GAMES_PLAYED':7,'EFG':0.51,'FTR':0.32,'OFF_REB_RATE':0.30,'DEF_REB_RATE':0.73,'TOV':13.0} for t in teams]
    bpi = [{'TEAM_ID':t,'BPI':15.0,'BPI_RK':18,'BPI_OFF':10.0,'BPI_OFF_RK':15,'BPI_DEF':5.0,'BPI_DEF_RK':33} for t in teams]
    players = [
      {'PLYR_ID': 501,'DISPLAY_NAME':'Jo Sample','TEAM_ID':152,'TEAM_NAME':'NC State','GAMES_PLAYED':7,'TNETPTS':5.0,'ONETPTS':4.0,'DNETPTS':1.0},
      {'PLYR_ID': 502,'DISPLAY_NAME':'Jane Doe','TEAM_ID':153,'TEAM_NAME':'North Carolina','GAMES_PLAYED':7,'TNETPTS':4.0,'ONETPTS':2.0,'DNETPTS':2.0},
    ]
    fp = {
     '501':{'tm_id':152,'displayName':'Jo Sample','games_played':7,'tPoss':200,'minutes_played':90,'total_oNetPts':4,'total_dNetPts':1,'total_tNetPts':5,'passing_oNetPts':2,'passing_dNetPts':1,'passing_tNetPts':3},
     '502':{'tm_id':153,'displayName':'Jane Doe','games_played':7,'tPoss':220,'minutes_played':101,'total_oNetPts':2,'total_dNetPts':2,'total_tNetPts':4,'passing_oNetPts':1,'passing_dNetPts':0.5,'passing_tNetPts':1.5},
     '503':{'tm_id':999,'displayName':'Outside Cohort','games_played':7,'tPoss':100,'minutes_played':50,'total_oNetPts':1,'total_dNetPts':1,'total_tNetPts':2,'passing_oNetPts':0.1,'passing_dNetPts':0.1,'passing_tNetPts':0.2},
    }
    return {'team4f': t4,'team_stats':ts,'bpi_stats':bpi,'plyr_stats':players},fp


def test_cohort_identities_preserved():
    frame=load_cohort(ROOT/'data/reference/cohort_45.csv')
    assert len(frame)==45
    assert frame.espn_team_id.nunique()==45
    assert frame.groupby('cohort').size().to_dict()=={'AP_TOP25':25,'WATCHLIST':20}
    assert frame.loc[frame.espn_team_id.eq(153),'ap_rank'].iloc[0]==24
    assert frame.loc[frame.espn_team_id.eq(152),'cohort'].iloc[0]=='WATCHLIST'


def test_build_splits_models_and_preserves_source_identity():
    team_data, fp=synthetic()
    out=build_frames(team_data,fp,small_cohort(),2026,'2026-11-23T18:00:00Z')
    assert len(out['team_season'])==2
    assert len(out['four_factors'])==6
    assert len(out['bpi'])==2
    assert len(out['player_season'])==2
    assert len(out['skill_impacts'])==2
    assert set(out['team_season'].columns)>={'team_net_points_off','team_net_points_def','team_net_points_total','bpi_bpi','team_stat_efg'}
    assert set(out['player_season'].columns)>={'player_id','team_id','fingerprint_team_id','fingerprint_total_raw','TNETPTS'}
    assert set(out['skill_impacts'].columns)>={'skill','impact_off_raw','impact_def_raw','impact_total_raw','computed_total_league_pctile'}
    # Percentiles of full league, not just two selected teams.
    got=dict(zip(out['skill_impacts'].player_id,out['skill_impacts'].computed_total_league_pctile))
    assert got[501]==100.0
    assert round(got[502],2)==round(100*2/3,2)


def test_duplicate_player_key_stops_publish():
    team_data,fp=synthetic()
    team_data['plyr_stats'].append(copy.deepcopy(team_data['plyr_stats'][0]))
    with pytest.raises(PipelineValidationError,match='duplicate'):
        build_frames(team_data,fp,small_cohort(),2026,'2026-11-23T18:00:00Z')


def test_missing_fingerprint_for_cohort_player_is_fatal():
    team_data,fp=synthetic()
    del fp['501']
    with pytest.raises(PipelineValidationError,match='fingerprint'):
        build_frames(team_data,fp,small_cohort(),2026,'2026-11-23T18:00:00Z')


def test_source_team_mismatch_is_flagged_not_overwritten():
    team_data,fp=synthetic()
    fp['501']['tm_id']=153
    out=build_frames(team_data,fp,small_cohort(),2026,'2026-11-23T18:00:00Z')
    row=out['player_season'].set_index('player_id').loc[501]
    assert row.team_id==152
    assert row.fingerprint_team_id==153
    assert bool(row.fingerprint_team_id_disagrees)
    assert len(out['team_id_discrepancies'])==1


def test_missing_required_team_side_is_fatal():
    team_data,fp=synthetic()
    team_data['team4f']=[x for x in team_data['team4f'] if not (x['digital_team_id']==152 and x['Side']=='Defense')]
    with pytest.raises(PipelineValidationError,match='factor'):
        build_frames(team_data,fp,small_cohort(),2026,'2026-11-23T18:00:00Z')


def test_unkeyed_outside_cohort_team_rows_are_quarantined_without_fake_ids():
    team_data, fp=synthetic()
    team_data['team_stats'].append({'digital_team_id':None,'tmID':12345,'tmName':'unknown','GAMES_PLAYED':6,'EFG':0.44})
    out=build_frames(team_data,fp,small_cohort(),2026,'2026-11-23T18:00:00Z')
    assert len(out['team_season'])==2
    assert len(out['unkeyed_team_stats'])==1
    assert out['unkeyed_team_stats']['team_id'].isna().all()
    assert out['unkeyed_team_stats']['rejection_reason'].iloc[0]=='MISSING_ESPN_DIGITAL_TEAM_ID'
