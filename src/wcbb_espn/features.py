"""Phase 1 descriptive features, independent of ESPN's published model ratings."""
from __future__ import annotations
import hashlib
import json
import unicodedata
from pathlib import Path
import numpy as np
import pandas as pd
from .pipeline import PipelineValidationError

PLAYER_RATES = [f'fingerprint_impact_{x}_per100' for x in ('off','def','total')]
SKILL_RATES = [f'skill_impact_{x}_per100' for x in ('off','def','total')]
KEY = ['api_season','player_id']

def load_feature_rules(root: Path):
    rules = json.loads((root/'data/reference/player_feature_rules_v1.json').read_text())
    taxonomy = pd.read_csv(root/'data/reference/skill_taxonomy_v1.csv')
    if taxonomy.skill.duplicated().any() or taxonomy.functional_skill_group.isna().any():
        raise PipelineValidationError('Invalid skill taxonomy')
    return rules, taxonomy

def number(frame, name):
    if name not in frame:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[name], errors='coerce').astype(float).replace([np.inf,-np.inf],np.nan)

def valid_fraction(frame, name):
    v=number(frame,name)
    return v.where(v.between(0,1))

def normalized_name(value):
    if not isinstance(value,str): return ''
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum() and not unicodedata.combining(c))

def tier(values, thresholds, labels):
    result=pd.Series('Unknown',index=values.index)
    for i,label in enumerate(labels):
        mask=values.ge(0)
        if i: mask &= values.ge(thresholds[i-1])
        if i<len(thresholds): mask &= values.lt(thresholds[i])
        result.loc[mask]=label
    return result

def require(condition, message):
    if not condition: raise PipelineValidationError(message)

def build_features(players, skills, rules, taxonomy):
    """Copy all source columns, add 16 player and four skill features, validate output."""
    require(not players.empty and not skills.empty,'Empty processed input')
    for frame,key in [(players,KEY),(skills,KEY+['skill'])]:
        require(set(key+['team_id']) <= set(frame),'Missing processed identity key')
        require(not frame[key+['team_id']].isna().any().any(),'NULL processed identity key')
        require(not frame.duplicated(key).any(),'Duplicate processed grain')
    require(set(players.api_season)<= {2025,2026},'Unexpected source season')
    p=players.copy(); s=skills.copy()
    poss=number(p,'fingerprint_possessions').where(lambda x:x>0)
    minutes=number(p,'fingerprint_minutes').where(lambda x:x>=0)
    games=number(p,'GAMES_PLAYED').where(lambda x:(x>=0)&(x%1==0))
    mpg=number(p,'MIN_PLAYED').where(lambda x:x>=0)
    for part in ('off','def','total'):
        p[f'fingerprint_impact_{part}_per100']=number(p,f'fingerprint_{part}_raw')/poss*100
    p['minutes_total_est']=mpg*games
    p['minutes_share_est']=mpg/rules['regulation_minutes']
    for src,dest in [('fingerprint_usage','usage_pct'),('fingerprint_assisted_rate','assisted_rate_pct'),('TOV%','turnover_pct_display')]:
        p[dest]=valid_fraction(p,src)*100
    p['position_group']=p.get('POSITION',pd.Series('',index=p.index)).fillna('').astype(str).str.upper().str.strip().map(rules['position_mapping']).fillna('Unknown')
    p['minutes_sample_tier']=tier(minutes,rules['minutes_sample_thresholds'],rules['sample_labels'])
    p['games_sample_tier']=tier(games,rules['games_sample_thresholds'],rules['sample_labels'])
    p['playing_time_tier']=tier(mpg,rules['playing_time_thresholds'],rules['playing_time_labels'])
    context=(minutes>=rules['context_min_minutes'])&(games>=rules['context_min_games'])&(poss>=rules['context_min_possessions'])
    assisted=valid_fraction(p,'fingerprint_assisted_rate')
    p['creation_context']='Unknown'
    p.loc[context&assisted.notna(),'creation_context']='Mixed'
    p.loc[context&(assisted<=rules['assisted_low']),'creation_context']='More self-created'
    p.loc[context&(assisted>=rules['assisted_high']),'creation_context']='Mostly assisted'
    off=number(p,'fingerprint_off_raw');deff=number(p,'fingerprint_def_raw')
    known=context&off.notna()&deff.notna()
    p['impact_balance']='Unknown'
    p.loc[known,'impact_balance']='Balanced'
    p.loc[known&(abs(off-deff)>rules['balance_relative_tolerance']*(abs(off)+abs(deff)))&(abs(off)>abs(deff)),'impact_balance']='Offensive-leaning'
    p.loc[known&(abs(off-deff)>rules['balance_relative_tolerance']*(abs(off)+abs(deff)))&(abs(deff)>abs(off)),'impact_balance']='Defensive-leaning'
    p.loc[known&(off*deff<0),'impact_balance']='Mixed-sign'
    names=p.get('DISPLAY_NAME',pd.Series('',index=p.index)).map(normalized_name)
    fpnames=p.get('fingerprint_player_name',pd.Series('',index=p.index)).map(normalized_name)
    identity=(number(p,'team_id')==number(p,'fingerprint_team_id'))&(names==fpnames)&names.ne('')
    # Identical player IDs establish the join; unresolved name variants still need review.
    p['identity_consistency_status']=np.where(identity,'Agreement','Review required')
    missing=p[PLAYER_RATES+['minutes_total_est','minutes_share_est','usage_pct','assisted_rate_pct','turnover_pct_display']].isna().any(axis=1)|minutes.isna()|games.isna()
    p['evidence_status']='Ready'
    p.loc[(minutes<rules['ready_minutes'])|(games<rules['ready_games']),'evidence_status']='Small sample'
    p.loc[missing,'evidence_status']='Missing key metric'
    p.loc[~identity,'evidence_status']='Identity review'
    flags=pd.Series('',index=p.index)
    for src in rules['native_fraction_columns']:
        flags+=np.where(number(p,src).notna()&valid_fraction(p,src).isna(),f'INVALID_FRACTION:{src};','')
    flags+=np.where(poss.isna(),'INVALID_OR_MISSING_POSSESSIONS;','')
    flags+=np.where(number(p,'fingerprint_games').ne(games),'GAME_COUNT_REVIEW;','')
    flags+=np.where((p.minutes_total_est-minutes).abs()>1,'MINUTES_RECONCILIATION_REVIEW;','')
    p['feature_qa_flags']=flags.str.rstrip(';')
    p.loc[p.feature_qa_flags.str.contains('GAME_COUNT_REVIEW|MINUTES_RECONCILIATION_REVIEW'),'evidence_status']='Missing key metric'
    p.loc[~identity,'evidence_status']='Identity review'
    require(set(s.skill)<=set(taxonomy.skill),'Unmapped source skill; update taxonomy before publication')
    parent=p.set_index(KEY)
    skill_keys=pd.MultiIndex.from_frame(s[KEY])
    require(skill_keys.isin(parent.index).all(),'Orphan skill record')
    linked=parent.reindex(skill_keys).reset_index(drop=True)
    require(np.array_equal(s.team_id.to_numpy(),linked.team_id.to_numpy()),'Skill/player team mismatch')
    require(set(skill_keys)==set(parent.index),'Player missing skill records')
    denom=number(s,'source_possessions').where(lambda x:x>0)
    require(np.isclose(number(s,'source_possessions'),number(linked,'fingerprint_possessions'),equal_nan=True).all(),'Skill/player possession mismatch')
    for part in ('off','def','total'):
        s[f'skill_impact_{part}_per100']=number(s,f'impact_{part}_raw')/denom*100
    s['functional_skill_group']=s.skill.map(taxonomy.set_index('skill').functional_skill_group)
    for col in ['DISPLAY_NAME','fingerprint_minutes','GAMES_PLAYED','evidence_status','identity_consistency_status']:
        if col in linked: s['player_'+col.lower()]=linked[col].to_numpy()
    for frame in (p,s):
        frame['feature_version']=rules['version']
        frame['analysis_population']='Fixed 45-team cohort; not full league'
        frame['derived_rate_model']='Independent accumulated fingerprint contribution / ESPN source possessions * 100; not official ESPN rating'
        frame['season_status']=np.where(frame.api_season.eq(2026),'Partial season','Frozen historical baseline')
    for original,output in [(players,p),(skills,s)]:
        pd.testing.assert_frame_equal(output[original.columns],original)
        added=output.loc[:,~output.columns.isin(original.columns)].select_dtypes('number')
        require(not np.isinf(added.to_numpy(dtype=float)).any(),'Infinite derived feature')
    for c in ['usage_pct','assisted_rate_pct','turnover_pct_display']:
        require(p[c].dropna().between(0,100).all(),'Invalid percentage display')
    qa={'status':'PASS_WITH_REVIEW' if ((p.evidence_status=='Identity review')|p.feature_qa_flags.ne('')).any() else 'PASS','feature_version':rules['version'],'player_rows':len(p),'skill_rows':len(s),
        'player_null_counts':{c:int(p[c].isna().sum()) for c in p if c not in players},
        'skill_null_counts':{c:int(s[c].isna().sum()) for c in s if c not in skills},
        'classifications':{c:{str(k):int(v) for k,v in p[c].value_counts(dropna=False).items()} for c in ['position_group','minutes_sample_tier','games_sample_tier','playing_time_tier','creation_context','impact_balance','identity_consistency_status','evidence_status']},
        'flag_counts':{flag:int(p.feature_qa_flags.str.contains(flag,regex=False).sum()) for flag in ['INVALID_FRACTION:fingerprint_usage','INVALID_FRACTION:fingerprint_assisted_rate','INVALID_FRACTION:TOV%','INVALID_OR_MISSING_POSSESSIONS','GAME_COUNT_REVIEW','MINUTES_RECONCILIATION_REVIEW']},
        'season_rows':{str(int(k)):int(v) for k,v in p.api_season.value_counts().items()},
        'unknown_skill_count':0,'full_source_percentiles':'Preserved unchanged; original raw skill-impact ranks, not recalculated on cohort or per-100 rates',
        'unresolved_issues':'Source name variants require review; small samples and invalid fractions remain labeled, never imputed.'}
    return p,s,qa

def write_feature_bundle(players, skills, root: Path, destination: Path, source_manifest: dict):
    """Build in the caller's staging directory; never writes published source tables."""
    from .refresh import write_parquet, _duckdb
    rules,taxonomy=load_feature_rules(root)
    p,s,qa=build_features(players,skills,rules,taxonomy)
    destination.mkdir(parents=True,exist_ok=True)
    for name,frame in [('player_features',p),('player_skill_features',s)]:
        write_parquet(frame,destination/f'{name}.parquet')
        frame.to_csv(destination/f'{name}.csv',index=False)
        for season,part in frame.groupby('api_season'):
            out=destination/f'season={int(season)}';out.mkdir(exist_ok=True)
            write_parquet(part,out/f'{name}.parquet');part.to_csv(out/f'{name}.csv',index=False)
    db=_duckdb().connect(str(destination/'player_features.duckdb'))
    try:
        db.register('players',p);db.register('skills',s)
        db.execute('CREATE TABLE player_features AS SELECT * FROM players')
        db.execute('CREATE TABLE player_skill_features AS SELECT * FROM skills')
    finally:db.close()
    qa['source_run_id']=source_manifest['run_id']
    qa['source_qa']=source_manifest['qa']
    qa['rule_sha256']={name:hashlib.sha256((root/'data/reference'/name).read_bytes()).hexdigest() for name in ['player_feature_rules_v1.json','skill_taxonomy_v1.csv']}
    qa['output_sha256']={str(f.relative_to(destination)):hashlib.sha256(f.read_bytes()).hexdigest() for f in destination.rglob('*') if f.is_file()}
    (destination/'manifest.json').write_text(json.dumps(qa,indent=2,allow_nan=False)+'\n')
    return qa
