"""Independent full-source position/role distributions; no overall evaluation score."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .features import KEY, number, require

def load_peer_rules(root):
    c=json.loads((Path(root)/'data/reference/peer_benchmark_rules_v1.json').read_text())
    require(c['minimum_peer_n']>=3,'Peer minimum must be >=3')
    return c

def eligible(p,c):
    result=pd.Series(False,index=p.index)
    for y,limits in c['eligibility'].items():
        result |= p.api_season.eq(int(y)) & number(p,'GAMES_PLAYED').ge(limits['games']) & number(p,'fingerprint_minutes').ge(limits['minutes']) & number(p,'fingerprint_possessions').ge(limits['possessions'])
    return result & p.identity_consistency_status.eq('Agreement') & ~p.feature_qa_flags.fillna('').str.contains('GAME_COUNT_REVIEW|MINUTES_RECONCILIATION_REVIEW') & ~p.position_group.isin(c['excluded_positions'])

def metric_values(p, spec):
    v=number(p,spec['column'])
    if spec.get('min') is not None:v=v.where(v>=spec['min'])
    if spec.get('max') is not None:v=v.where(v<=spec['max'])
    return v

def exact(left,right):
    # Source identity/exposure and metric vintage are compared without rounding away drift.
    if pd.isna(left) or pd.isna(right):return pd.isna(left) and pd.isna(right)
    return left==right

def percentile(values,v):
    # Average-tie rank/n for an exact reference member. Caller suppresses nonmembers.
    return 100*(np.searchsorted(values,v,'left')+(np.searchsorted(values,v,'right')-np.searchsorted(values,v,'left')+1)/2)/len(values)

def build_peer_features(players,skills,full_players,full_skills,c,metadata,run_id):
    for f,key in [(players,KEY),(skills,KEY+['skill']),(full_players,KEY),(full_skills,KEY+['skill'])]:
        require(set(key+['team_id'])<=set(f),'Missing peer key')
        require(not f[key+['team_id']].isna().any().any(),'Null peer key')
        require(not f.duplicated(key).any(),'Duplicate peer key')
    for year in players.api_season.unique():
        require(len(full_players[full_players.api_season.eq(year)])>=c['minimum_full_source_players'],'Full-source population too small; cohort is not a valid universe')
        require(year in metadata,'Missing peer source provenance')
    fp=full_players.copy().reset_index(drop=True); fs=full_skills.copy().reset_index(drop=True)
    p=players.copy().reset_index(drop=True);s=skills.copy().reset_index(drop=True)
    parent=fp.set_index(KEY); selected_index=pd.MultiIndex.from_frame(p[KEY])
    selected=parent.reindex(selected_index).reset_index(drop=True)
    for keyrow,row in p.iterrows():
        if int(row.api_season)==2026:require(not pd.isna(selected.loc[keyrow,'team_id']),'Current player missing from exact source response')
    fullskillparent=fp.set_index(KEY).reindex(pd.MultiIndex.from_frame(fs[KEY])).reset_index(drop=True)
    require(fullskillparent.team_id.notna().all() and np.array_equal(fs.team_id.to_numpy(),fullskillparent.team_id.to_numpy()),'Full-source skill/player team mismatch')
    require(set(pd.MultiIndex.from_frame(fs[KEY]))==set(parent.index),'Full-source player missing skills')
    require(fs.groupby(KEY).skill.nunique().eq(fs.skill.nunique()).all(),'Incomplete full-source per-player skill coverage')
    targetparent=p.set_index(KEY).reindex(pd.MultiIndex.from_frame(s[KEY])).reset_index(drop=True)
    require(targetparent.team_id.notna().all() and np.array_equal(s.team_id.to_numpy(),targetparent.team_id.to_numpy()),'Selected skill/player team mismatch')
    require(set(pd.MultiIndex.from_frame(s[KEY]))==set(selected_index),'Selected player skill coverage missing')
    require(set(fp.position_group)<=set(c['position_groups']) and set(p.position_group)<=set(c['position_groups']),'Unrecognized peer position label')
    fp['_eligible']=eligible(fp,c)
    core=['team_id','position_group','identity_consistency_status','fingerprint_minutes','GAMES_PLAYED','fingerprint_possessions','feature_qa_flags']
    matched=pd.Series([all(exact(row.get(col),selected.loc[i].get(col)) for col in core) for i,row in p.iterrows()])
    p['position_benchmark_eligible']=eligible(p,c)&matched
    p['position_benchmark_n']=0
    p['position_benchmark_status']='Ineligible exposure or identity'
    p.loc[~matched,'position_benchmark_status']='Source vintage mismatch'
    p.loc[p.position_group.isin(c['excluded_positions']),'position_benchmark_status']='Unknown position'
    p['position_benchmark_version']=c['version'];p['comparison_population']=c['population']
    p['usage_role_band']='Unknown';p['role_peer_group']='Unavailable';p['role_peer_n']=0;p['role_benchmark_status']='Role unavailable'
    p['usage_role_lower_cutoff']=np.nan;p['usage_role_upper_cutoff']=np.nan
    refs=[]; distributions={};cutoffs={};reference_metrics={}
    def add_reference(year,kind,group,metric,spec,values,base_n,position,band=None):
        values=np.sort(np.asarray(values.dropna(),dtype=float));n=len(values)
        status='Insufficient peers' if n<c['minimum_peer_n'] else 'Constant distribution' if len(np.unique(values))<2 else 'Provisional' if year==2026 else 'Available'
        if position in c['excluded_positions']:status='Unknown position'
        meta=metadata[year]
        row={'api_season':year,'academic_season':f'{year}-{str(year+1)[-2:]}','comparison_kind':kind,'comparison_group':group,'position_group':position,'usage_role_band':band,'metric':metric,'source_column':spec['column'],'unit':spec['unit'],'directionality':spec['direction'],'eligible_n':n,'exposure_eligible_n':int(base_n),'minimum_peer_n':c['minimum_peer_n'],'minimum_exposure':json.dumps(c['eligibility'][str(year)],sort_keys=True),'status':status,'valid':status in ('Available','Provisional'),'percentile_method':c['percentile_method'],'tie_handling':'Average rank / n; constant distributions suppressed','configuration_version':c['version'],'reference_population':c['population'],'source_snapshot_id':run_id,'source_retrieved_utc':meta['retrieved_utc'],'source_vintage':meta['input_vintage'],'source_hashes':json.dumps(meta['sources'],sort_keys=True),'source_reference_id':meta.get('reference_id',run_id)}
        for q in c['reference_quantiles']:row[f'q{int(q*100):02d}']=float(np.quantile(values,q,method=c['quantile_method'])) if n else np.nan
        row['median']=row['q50']
        row['usage_lower_cutoff'],row['usage_upper_cutoff']=cutoffs.get((year,position),(np.nan,np.nan))
        refs.append(row);distributions[(year,kind,group,metric)]=(values,status)
        return values,status
    for (year,position),group in fp.groupby(['api_season','position_group'],sort=True):
        year=int(year);mask=group['_eligible'];base=group.loc[mask]
        usage=metric_values(base,c['metrics']['usage']).dropna()
        if len(usage)>=c['minimum_peer_n'] and position not in c['excluded_positions']:
            cutoffs[(year,position)]=tuple(usage.quantile(c['usage_quantiles'],interpolation=c['quantile_method']).to_numpy())
        for metric,spec in c['metrics'].items():
            add_reference(year,'position',position,metric,spec,metric_values(base,spec),len(base),position)
        lo,hi=cutoffs.get((year,position),(np.nan,np.nan))
        bands=pd.Series('Unknown',index=group.index)
        valid=metric_values(group,c['metrics']['usage']).notna()&mask
        if pd.notna(lo):
            bands.loc[valid]='Typical usage'
            if lo!=hi:
                uv=metric_values(group,c['metrics']['usage'])
                bands.loc[valid&(uv<=lo)]='Lower usage';bands.loc[valid&(uv>=hi)]='Higher usage'
        fp.loc[group.index,'_band']=bands
        for band in ['Lower usage','Typical usage','Higher usage']:
            rb=group.loc[bands.eq(band)]
            for metric in c['role_metrics']:
                spec=c['metrics'][metric]
                add_reference(year,'role',position+' | '+band,metric,spec,metric_values(rb,spec),len(rb),position,band)
    # Explicit unavailable rows for configured positions absent from the provider feed.
    for year in sorted(fp.api_season.unique()):
        for pos in c['position_groups']:
            if ((fp.api_season==year)&fp.position_group.eq(pos)).any():
                continue
            for metric,spec in c['metrics'].items():
                add_reference(int(year),'position',pos,metric,spec,pd.Series(dtype=float),0,pos)
            for band in ['Lower usage','Typical usage','Higher usage']:
                for metric in c['role_metrics']:
                    add_reference(int(year),'role',pos+' | '+band,metric,c['metrics'][metric],pd.Series(dtype=float),0,pos,band)
    for i,row in p.iterrows():
        year=int(row.api_season);pos=row.position_group
        n=int(((fp.api_season==year)&(fp.position_group==pos)&fp['_eligible']).sum())
        p.loc[i,'position_benchmark_n']=n
        if p.loc[i,'position_benchmark_eligible']:
            p.loc[i,'position_benchmark_status']='Insufficient peers' if n<c['minimum_peer_n'] else 'Provisional' if year==2026 else 'Available'
        lo,hi=cutoffs.get((year,pos),(np.nan,np.nan));p.loc[i,'usage_role_lower_cutoff']=lo;p.loc[i,'usage_role_upper_cutoff']=hi
        usage=metric_values(p.loc[[i]],c['metrics']['usage']).iloc[0]
        usage_matches=exact(usage,metric_values(selected.loc[[i]],c['metrics']['usage']).iloc[0])
        if p.loc[i,'position_benchmark_eligible'] and pd.notna(lo) and pd.notna(usage) and usage_matches:
            band='Typical usage' if lo==hi else 'Lower usage' if usage<=lo else 'Higher usage' if usage>=hi else 'Typical usage'
            label=pos+' | '+band
            rn=int(((fp.api_season==year)&(fp.position_group==pos)&fp['_eligible']&fp['_band'].eq(band)).sum())
            p.loc[i,'usage_role_band']=band;p.loc[i,'role_peer_group']=label;p.loc[i,'role_peer_n']=rn
            p.loc[i,'role_benchmark_status']='Insufficient peers' if rn<c['minimum_peer_n'] else 'Provisional' if year==2026 else 'Available'
    for metric,spec in c['metrics'].items():
        target_values=metric_values(p,spec).to_numpy();reference_values=metric_values(selected,spec).to_numpy()
        for kind in ['position']+(['role'] if metric in c['role_metrics'] else []):
            prefix=metric+'_'+kind;p[prefix+'_pctile']=np.nan;p[prefix+'_n']=0;p[prefix+'_status']='Unavailable'
            for i,row in p.iterrows():
                group=row.position_group if kind=='position' else row.role_peer_group
                values,status=distributions.get((int(row.api_season),kind,group,metric),(np.array([]),'Insufficient peers'))
                p.loc[i,prefix+'_n']=len(values)
                v=target_values[i];rv=reference_values[i]
                state=status
                if not p.loc[i,'position_benchmark_eligible']:state=p.loc[i,'position_benchmark_status']
                elif kind=='role' and row.usage_role_band=='Unknown':state='Role unavailable'
                elif pd.isna(v):state='Missing metric'
                elif not exact(v,rv):state='Source vintage mismatch'
                if state in ('Available','Provisional'):p.loc[i,prefix+'_pctile']=percentile(values,v)
                p.loc[i,prefix+'_status']=state
    # Build all per-skill/component distributions independently, without aggregating skills.
    fs['_position']=fullskillparent.position_group.to_numpy();fs['_eligible']=fp.set_index(KEY)['_eligible'].reindex(pd.MultiIndex.from_frame(fs[KEY])).to_numpy()
    for (year,pos,skill),group in fs.groupby(['api_season','_position','skill'],sort=True):
        base=group[group['_eligible']]
        for part in ['off','def','total']:
            metric='skill:'+skill+':'+part
            spec={'column':f'skill_impact_{part}_per100','unit':'Independent contribution per 100 source possessions','direction':'Higher modeled contribution; not independently verified basketball skill'}
            add_reference(int(year),'skill',pos,metric,spec,number(base,spec['column']),len(base),pos)
    for year in sorted(fp.api_season.unique()):
        for pos in c['position_groups']:
            if ((fp.api_season==year)&fp.position_group.eq(pos)).any():
                continue
            for skill in sorted(fs.loc[fs.api_season.eq(year),'skill'].unique()):
                for part in ['off','def','total']:
                    spec={'column':f'skill_impact_{part}_per100','unit':'Independent contribution per 100 source possessions','direction':'Higher modeled contribution; film validation required'}
                    add_reference(int(year),'skill',pos,'skill:'+skill+':'+part,spec,pd.Series(dtype=float),0,pos)
    skparent=p.set_index(KEY).reindex(pd.MultiIndex.from_frame(s[KEY])).reset_index(drop=True)
    skref=fs.set_index(KEY+['skill']).reindex(pd.MultiIndex.from_frame(s[KEY+['skill']])).reset_index(drop=True)
    s['skill_position_peer_n']=0;s['skill_benchmark_status']='Unavailable';s['skill_benchmark_version']=c['version'];s['skill_comparison_population']=c['population']
    for part in ['off','def','total']:
        dest=f'skill_{part}_per100_position';s[dest+'_pctile']=np.nan;s[dest+'_n']=0;s[dest+'_status']='Unavailable'
        target_values=number(s,f'skill_impact_{part}_per100').to_numpy();reference_values=number(skref,f'skill_impact_{part}_per100').to_numpy()
        for i,row in s.iterrows():
            values,status=distributions.get((int(row.api_season),'skill',skparent.loc[i,'position_group'],'skill:'+row.skill+':'+part),(np.array([]),'Insufficient peers'))
            v=target_values[i];rv=reference_values[i]
            if not skparent.loc[i,'position_benchmark_eligible']:status=skparent.loc[i,'position_benchmark_status']
            elif not exact(row.team_id,skref.loc[i].get('team_id')):status='Source vintage mismatch'
            elif pd.isna(v):status='Missing metric'
            elif not exact(v,rv):status='Source vintage mismatch'
            s.loc[i,dest+'_n']=len(values);s.loc[i,dest+'_status']=status
            if status in ('Available','Provisional'):s.loc[i,dest+'_pctile']=percentile(values,v)
        if part=='total':
            s['skill_position_peer_n']=s[dest+'_n'];s['skill_benchmark_status']=s[dest+'_status']
    s['functional_strength_tag']=None;s['functional_strength_status']='No qualifying candidate';s['skill_statistical_distinction']='None'
    evidence={tuple(row):[] for row in p[KEY].to_numpy()}
    for i,row in s.iterrows():
        mapping=c['strength_components'].get(row.skill)
        high=any(pd.notna(row[f'skill_{part}_per100_position_pctile']) and row[f'skill_{part}_per100_position_pctile']>=c['strength_percentile'] for part in ['off','def','total'])
        if high:s.loc[i,'skill_statistical_distinction']='Relative statistical distinction; not confirmed strength'
        if mapping:
            part=mapping['component'];v=row[f'skill_impact_{part}_per100'];pct=row[f'skill_{part}_per100_position_pctile'];n=row[f'skill_{part}_per100_position_n']
            if pd.notna(pct) and pct>=c['strength_percentile'] and v>0:
                s.loc[i,'functional_strength_tag']=mapping['tag'];s.loc[i,'functional_strength_status']='Model-based candidate; film review required'
                evidence[(row.api_season,row.player_id)].append({'tag':mapping['tag'],'skill':row.skill,'component':part,'contribution_per100':float(v),'position_percentile':float(pct),'peer_n':int(n),'benchmark_status':row[f'skill_{part}_per100_position_status'],'interpretation':c['strength_interpretation']})
    for field in ['functional_strength_tags','functional_strength_evidence','functional_strength_skill_ids']:
        p[field]='[]'
    p['functional_strength_peer_n']=pd.Series(pd.NA,index=p.index,dtype='Int64');p['functional_strength_status']='No qualifying candidate'
    for i,row in p.iterrows():
        ev=evidence[(row.api_season,row.player_id)]
        p.loc[i,'functional_strength_tags']=json.dumps(sorted(set(e['tag'] for e in ev)))
        p.loc[i,'functional_strength_evidence']=json.dumps(ev,sort_keys=True)
        p.loc[i,'functional_strength_skill_ids']=json.dumps(sorted(set(e['skill'] for e in ev)))
        if ev:p.loc[i,'functional_strength_peer_n']=min(e['peer_n'] for e in ev);p.loc[i,'functional_strength_status']='Model-based candidate; film review required'
        elif not row.position_benchmark_eligible:p.loc[i,'functional_strength_status']='Ineligible or source vintage mismatch'
    reference=pd.DataFrame(refs)
    require(not reference.duplicated(['api_season','comparison_kind','comparison_group','metric']).any(),'Duplicate benchmark reference grain')
    for original,out in [(players,p),(skills,s)]:
        pd.testing.assert_frame_equal(out[original.columns],original.reset_index(drop=True))
        for col in out:
            if col not in original and col.endswith('_pctile'):require(out[col].dropna().between(0,100).all(),'Invalid benchmark percentile')
    qa={'status':'PASS_WITH_REVIEW','version':c['version'],'player_rows':len(p),'skill_rows':len(s),'reference_rows':len(reference),'population':c['population'],
        'source_population_rows':{str(int(y)):len(g) for y,g in fp.groupby('api_season')},
        'eligible_source_positions':{str(int(y)):g.loc[g['_eligible'],'position_group'].value_counts().to_dict() for y,g in fp.groupby('api_season')},
        'position_status_counts':p.position_benchmark_status.value_counts().to_dict(),'role_status_counts':p.role_benchmark_status.value_counts().to_dict(),
        'reference_status_counts':reference.status.value_counts().to_dict(),'player_missing_percentiles':{col:int(p[col].isna().sum()) for col in p if col not in players and col.endswith('_pctile')},
        'skill_status_counts':s.skill_benchmark_status.value_counts().to_dict(),'functional_status_counts':p.functional_strength_status.value_counts().to_dict(),
        'identity_review_observations':int(p.identity_consistency_status.eq('Review required').sum()),'provenance':metadata,
        'metric_definition_cautions':['AST_40 and REB_40 retain provider labels; their rate denominators are not independently verified. Compare descriptively only.','High turnover, assisted rate or usage percentiles are not quality labels.','Historical reference is a separate extraction; source drift is suppressed, not filled.','Current benchmarks and model-based function candidates are provisional and require film validation.']}
    qa['source_population_quality'] = {}
    for year,group in fp.groupby('api_season'):
        limits=c['eligibility'][str(int(year))]
        qa['source_population_quality'][str(int(year))]={
            'total_players':len(group), 'eligible_players':int(group['_eligible'].sum()),
            'identity_review':int(group.identity_consistency_status.eq('Review required').sum()),
            'unknown_position':int(group.position_group.isin(c['excluded_positions']).sum()),
            'below_or_missing_games':int((~number(group,'GAMES_PLAYED').ge(limits['games'])).sum()),
            'below_or_missing_minutes':int((~number(group,'fingerprint_minutes').ge(limits['minutes'])).sum()),
            'below_or_missing_possessions':int((~number(group,'fingerprint_possessions').ge(limits['possessions'])).sum()),
            'exposure_reconciliation_review':int(group.feature_qa_flags.fillna('').str.contains('GAME_COUNT_REVIEW|MINUTES_RECONCILIATION_REVIEW').sum()),
            'note':'Exclusion reason counts overlap; valid metric-specific counts are in the reference table.'}
    qa['function_candidate_breadth']={
        'eligible_selected_players':int(p.position_benchmark_eligible.sum()),
        'selected_players_with_candidates':int(p.functional_strength_tags.ne('[]').sum()),
        'interpretation':'Many parallel skill comparisons produce broad candidate coverage. Tags are descriptive film-review leads, not rarity or statistical significance claims.'}
    return p,s,reference,qa

def write_full_population_bundle(full_players,full_skills,c,metadata,run_id,destination,cohort_ids,expected_reference):
    """Publish every reference player using the same Phase 2 engine and source vintage."""
    from .refresh import write_parquet
    p,s,reference,qa=build_peer_features(full_players,full_skills,full_players,full_skills,c,metadata,run_id)
    pd.testing.assert_frame_equal(reference,expected_reference)
    require(len(p)==len(full_players) and len(s)==len(full_skills),'Full-population peer output lost rows')
    require(set(map(tuple,p[KEY].to_numpy()))==set(map(tuple,full_players[KEY].to_numpy())),'Full-population player keys changed')
    require(set(map(tuple,s[KEY+['skill']].to_numpy()))==set(map(tuple,full_skills[KEY+['skill']].to_numpy())),'Full-population skill keys changed')
    for frame in (p,s):
        frame['in_cohort_45']=frame.team_id.isin(cohort_ids)
        frame['peer_output_population']='Full ESPN WCBB provider player feed'
        frame['peer_source_run_id']=run_id
    dest=Path(destination)
    seasons={}
    for year,g in p.groupby('api_season'):
        year=int(year);sk=s[s.api_season.eq(year)]
        folder=dest/f'season={year}'
        write_parquet(g,folder/'player_peer_features.parquet')
        write_parquet(sk,folder/'player_skill_peer_features.parquet')
        seasons[str(year)]={'player_rows':len(g),'skill_rows':len(sk),'team_ids':int(g.team_id.nunique()),
                            'outside_cohort_players':int((~g.in_cohort_45).sum()),
                            'eligible_players':int(g.position_benchmark_eligible.sum()),
                            'source_reference_id':metadata[year]['reference_id']}
    return {'status':qa['status'],'population':c['population'],'source_run_id':run_id,
            'seasons':seasons,'position_status_counts':qa['position_status_counts'],
            'role_status_counts':qa['role_status_counts'],'skill_status_counts':qa['skill_status_counts'],
            'functional_status_counts':qa['functional_status_counts'],
            'reference_matches_cohort':True}


def stage_stable_benchmark_inputs(publication,historical_folder,current_folder,metadata,run_id):
    """Copy exact versioned input bytes to stable paths, with independently checked hashes."""
    import hashlib,shutil
    latest=Path(publication)/'latest'
    latest.mkdir(parents=True,exist_ok=True)
    result={'source_run_id':run_id,'population':metadata[2026]['population'],'seasons':{}}
    for year,source in [(2025,historical_folder),(2026,current_folder)]:
        folder=latest/f'season={year}';folder.mkdir()
        meta=metadata[year]
        for name in ('players.parquet','skills.parquet'):
            shutil.copy2(Path(source)/name,folder/name)
            require(hashlib.sha256((folder/name).read_bytes()).hexdigest()==meta['file_sha256'][name],
                    'Stable benchmark input hash mismatch')
        result['seasons'][str(year)]={'reference_id':meta['reference_id'],'retrieved_utc':meta['retrieved_utc'],
                                     'input_vintage':meta['input_vintage'],'player_rows':meta['player_rows'],
                                     'skill_rows':meta['skill_rows'],'file_sha256':meta['file_sha256']}
    (latest/'manifest.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\\n'.replace('\\n','\n'))
    return result


def write_peer_bundle(players,skills,full_players,full_skills,root,destination,metadata,run_id):
    import hashlib
    from .refresh import write_parquet,_duckdb
    c=load_peer_rules(root)
    p,s,reference,qa=build_peer_features(players,skills,full_players,full_skills,c,metadata,run_id)
    destination=Path(destination);destination.mkdir(parents=True)
    tables={'player_peer_features':p,'player_skill_peer_features':s,'peer_benchmark_reference':reference}
    for name,frame in tables.items():
        write_parquet(frame,destination/f'{name}.parquet');frame.to_csv(destination/f'{name}.csv',index=False)
        for year,part in frame.groupby('api_season'):
            folder=destination/f'season={int(year)}';folder.mkdir(exist_ok=True)
            write_parquet(part,folder/f'{name}.parquet');part.to_csv(folder/f'{name}.csv',index=False)
    con=_duckdb().connect(str(destination/'peer_features.duckdb'))
    try:
        for name,frame in tables.items():
            con.register('incoming',frame);con.execute(f'CREATE TABLE {name} AS SELECT * FROM incoming');con.unregister('incoming')
    finally:con.close()
    cohort_ids=set(pd.read_csv(Path(root)/'data/reference/cohort_45.csv').espn_team_id.astype(int))
    require(len(cohort_ids)==45,'Expected 45 cohort team IDs')
    qa['full_population_outputs']=write_full_population_bundle(full_players,full_skills,c,metadata,run_id,
        destination/'full_population',cohort_ids,reference)
    qa['source_run_id']=run_id
    qa['config_sha256']=hashlib.sha256((Path(root)/'data/reference/peer_benchmark_rules_v1.json').read_bytes()).hexdigest()
    qa['output_sha256']={str(f.relative_to(destination)):hashlib.sha256(f.read_bytes()).hexdigest() for f in destination.rglob('*') if f.is_file()}
    (destination/'manifest.json').write_text(json.dumps(qa,indent=2,allow_nan=False)+'\n')
    return qa

def prepare_peer_bundle(root,stage,manifest):
    import shutil
    from .full_source import capture_population,load_population
    from .refresh import read_parquet
    root=Path(root);stage=Path(stage)
    publication=stage/'benchmark_publication';publication.mkdir()
    pointer=root/'data/benchmarks/historical/latest.json'
    if pointer.is_file():
        path=json.loads(pointer.read_text())['path']
        require(not Path(path).is_absolute() and '..' not in Path(path).parts,'Unsafe benchmark cache path')
        historical_folder=root/path
        hp,hs,hm=load_population(historical_folder)
        import hashlib
        for name,digest in hm['phase1_rule_sha256'].items():
            require(hashlib.sha256((root/'data/reference'/name).read_bytes()).hexdigest()==digest,'Historical peer input rules changed; explicit re-extraction required')
    else:
        hp,hs,hm,folder=capture_population(root,stage,2025)
        historical_folder=folder
        path=f'data/benchmarks/historical/{hm["reference_id"]}'
        dest=publication/'historical'/hm['reference_id'];shutil.copytree(folder,dest)
        (publication/'historical/latest.json').write_text(json.dumps({'path':path,'reference_id':hm['reference_id']},indent=2)+'\n')
    currentqa=next(q for q in manifest['qa'] if q['api_season']==2026)
    cp,cs,cm,folder=capture_population(root,stage,2026,currentqa)
    shutil.copytree(folder,publication/'current'/manifest['run_id'])
    stage_stable_benchmark_inputs(publication,historical_folder,folder,{2025:hm,2026:cm},manifest['run_id'])
    players=read_parquet(stage/'processed/player_features.parquet')
    skills=read_parquet(stage/'processed/player_skill_features.parquet')
    fullp=pd.concat([hp,cp],ignore_index=True);fulls=pd.concat([hs,cs],ignore_index=True)
    return write_peer_bundle(players,skills,fullp,fulls,root,stage/'processed/phase2',{2025:hm,2026:cm},manifest['run_id'])
