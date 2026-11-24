"""Versioned full-provider reference extraction, separate from the frozen cohort."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from .features import build_features,load_feature_rules,require
from .pipeline import PipelineValidationError

def full_source_frames(team_data,fingerprints,season,retrieved):
    p=pd.DataFrame(team_data['plyr_stats']).copy()
    for source,target in [('PLYR_ID','player_id'),('TEAM_ID','team_id')]:
        values=pd.to_numeric(p[source],errors='coerce')
        require(values.notna().all() and (values%1==0).all(),'Invalid full-source ID')
        p[target]=values.astype('int64')
    require(not p.player_id.duplicated().any(),'Duplicate full-source player')
    records=[];skills=[]
    mapping={'tm_id':'fingerprint_team_id','displayName':'fingerprint_player_name','tPoss':'fingerprint_possessions','minutes_played':'fingerprint_minutes','games_played':'fingerprint_games','offensive_usage':'fingerprint_usage','assisted_rate':'fingerprint_assisted_rate','average_position':'fingerprint_avg_position','total_oNetPts':'fingerprint_off_raw','total_dNetPts':'fingerprint_def_raw','total_tNetPts':'fingerprint_total_raw'}
    for key,raw in fingerprints.items():
        require(isinstance(raw,dict),'Invalid full-source fingerprint record')
        records.append({'player_id':int(key),**{dest:raw.get(src) for src,dest in mapping.items()}})
        for name,value in raw.items():
            if name.endswith('_tNetPts') and name!='total_tNetPts':
                skill=name[:-8];skills.append({'player_id':int(key),'skill':skill,'impact_total_raw':value,'impact_off_raw':raw.get(skill+'_oNetPts'),'impact_def_raw':raw.get(skill+'_dNetPts'),'source_possessions':raw.get('tPoss')})
    p=p.merge(pd.DataFrame(records),on='player_id',how='left',validate='one_to_one')
    skill=pd.DataFrame(skills)
    require(not skill.duplicated(['player_id','skill']).any(),'Duplicate full-source skill')
    for part in ['off','def','total']:
        column='impact_'+part+'_raw';skill[column]=pd.to_numeric(skill[column],errors='coerce')
        skill['computed_'+part+'_league_pctile']=skill.groupby('skill')[column].rank(pct=True,method='average')*100
        skill['league_'+part+'_n']=skill.groupby('skill')[column].transform('count')
    skill['percentile_method']='COMPUTED_FULL_FEED_API_SEASON_BY_SKILL_NOT_PUBLISHED_ESPN'
    p=p.rename(columns={'TEAM_ID':'source_team_id'})
    p['team_requested']=p.TEAM_NAME;p['cohort']='FULL_SOURCE_REFERENCE';p['ap_rank']=np.nan
    skill=skill.merge(p[['player_id','team_id','team_requested','cohort','ap_rank']],on='player_id',validate='many_to_one')
    for f in [p,skill]:
        f['api_season']=season;f['academic_season']=f'{season}-{str(season+1)[-2:]}';f['retrieval_utc']=retrieved
        f['team_data_source_url']=f'https://espnanalytics.com/api/team-data?league=wcbb&season={season}'
        f['fingerprint_source_url']=f'https://espnanalytics.com/api/fingerprint-data?league=wcbb&season={season}'
    return p,skill

def capture_population(root,stage,season,qa=None):
    """Current: read exact ingestion bytes. Historical: fetch a new explicit vintage."""
    from .refresh import get_public_json,parse_response,write_parquet
    from .peers import load_peer_rules
    stage=Path(stage);stage.mkdir(parents=True,exist_ok=True)
    sources={};payload={}
    for name,route in [('team_data','team-data'),('fingerprint_data','fingerprint-data')]:
        url=f'https://espnanalytics.com/api/{route}?league=wcbb&season={season}'
        raw_path=stage/'raw'/f'{name}_{season}.json'
        if qa is not None:
            require(raw_path.is_file(),'Full-source current reference must use exact ingestion response bytes')
            raw=raw_path.read_bytes();obj=json.loads(raw)
            require(hashlib.sha256(raw).hexdigest()==qa['sources'][name]['sha256'],'Full-source response hash mismatch')
        else:obj,raw=get_public_json(url)
        payload[name]=obj;sources[name]={'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    at=qa['retrieved_utc'] if qa else datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    inputs=full_source_frames(parse_response(payload['team_data']),payload['fingerprint_data'],season,at)
    config=load_peer_rules(root)
    require(len(inputs[0])>=config['minimum_full_source_players'],'Insufficient full-source player population')
    require(inputs[0].fingerprint_player_name.notna().mean()>=config['minimum_fingerprint_coverage'],'Insufficient full-source fingerprint coverage')
    rules,taxonomy=load_feature_rules(root);p,s,_=build_features(*inputs,rules,taxonomy)
    expected_skills=set(taxonomy.skill)
    require(set(s.skill)==expected_skills and s.groupby(['api_season','player_id']).skill.nunique().eq(len(expected_skills)).all(),'Incomplete full-source skill taxonomy coverage')
    label='Current ingestion response' if qa else 'Historical re-extraction'
    reference_id=f'{season}_{at.replace("-","").replace(":","")}_{sources["team_data"]["sha256"][:12]}'
    for f in [p,s]:
        f['analysis_population']=config['population'];f['season_status']='Partial season' if season==2026 else 'Historical benchmark re-extraction'
    dest=stage/'benchmark_inputs'/str(season);dest.mkdir(parents=True)
    for name,frame in [('players',p),('skills',s)]:write_parquet(frame,dest/f'{name}.parquet')
    meta={'api_season':season,'retrieved_utc':at,'sources':sources,'input_vintage':label,'reference_id':reference_id,'player_rows':len(p),'skill_rows':len(s),'fingerprint_coverage':float(inputs[0].fingerprint_player_name.notna().mean()),'population':config['population']}
    meta['phase1_rule_sha256']={name:hashlib.sha256((Path(root)/'data/reference'/name).read_bytes()).hexdigest() for name in ['player_feature_rules_v1.json','skill_taxonomy_v1.csv']}
    meta['file_sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in dest.glob('*.parquet')}
    (dest/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    return p,s,meta,dest

def load_population(folder):
    from .refresh import read_parquet
    folder=Path(folder);meta=json.loads((folder/'manifest.json').read_text())
    for name,digest in meta['file_sha256'].items():require(hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,'Historical full-source cache hash mismatch')
    return read_parquet(folder/'players.parquet'),read_parquet(folder/'skills.parquet'),meta
