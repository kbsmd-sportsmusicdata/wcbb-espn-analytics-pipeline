"""Season-specific D1 membership and peer benchmarks; preserve provider-wide v1."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from .features import KEY, require
from .peers import build_peer_features, eligible

TEAM_KEY=['api_season','team_id']
SKILL_KEY=KEY+['skill']
P4={'Atlantic Coast Conference','Big Ten Conference','Big 12 Conference','Southeastern Conference'}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_membership(root,c):
    root=Path(root)
    folder=root/'data/reference/sdv'
    frames=[]; hashes={}
    for year in (2025,2026):
        path=folder/f'wbb_team_crosswalk_{year+1}.csv'
        raw=pd.read_csv(path)
        require(raw.season.eq(year+1).all(),'Crosswalk season mismatch')
        ids=pd.to_numeric(raw.espn_team_id,errors='coerce')
        require(ids.notna().all() and (ids%1==0).all() and ids.is_unique,'Invalid crosswalk ESPN IDs')
        require(raw.espn_conference.notna().all() and raw.espn_conference.str.strip().ne('').all(),'Missing SDV conference')
        f=raw[['espn_team_id','espn_display_name','espn_conference']].rename(columns={'espn_team_id':'team_id','espn_display_name':'membership_team_name','espn_conference':'conference_name'}).copy()
        f['team_id']=ids.astype('int64')
        f['api_season']=year
        f['division_verification_status']='SDV season-specific exact ESPN ID'
        f['ncaa_membership_status']='D1-competing; championship eligibility not assessed'
        f['membership_source']=path.name
        f['membership_source_url']=''
        f['membership_evidence_note']='Supplied SDV crosswalk; no NCAA ID field'
        frames.append(f)
        hashes[str(path.relative_to(root))]=digest(path)
    path=folder/'d1_membership_overrides.csv'
    ov=pd.read_csv(path).rename(columns={'espn_team_id':'team_id','espn_display_name':'membership_team_name','espn_conference':'conference_name','membership_status':'ncaa_membership_status','evidence_note':'membership_evidence_note'})
    require(ov.membership_source_url.str.startswith('https://').all(),'Missing override evidence URL')
    ov['division_verification_status']='Officially verified membership override'
    ov['membership_source']=path.name
    ov['ncaa_membership_status']=ov['ncaa_membership_status'].astype(str)+'; D1-competing'
    hashes[str(path.relative_to(root))]=digest(path)
    m=pd.concat([*frames,ov],ignore_index=True)
    require(not m.duplicated(TEAM_KEY).any(),'Duplicate membership key/override')
    require(m.groupby('api_season').size().to_dict()=={int(y):n for y,n in c['membership_policy']['expected_team_count'].items()},'Unexpected D1 membership counts')
    m['ncaa_division']='D1'
    m['is_ncaa_d1']=True
    m['conference_tier']=np.select([m.conference_name.isin(P4),m.conference_name.eq('Big East Conference')],['Power 4','Big East'],default='Other D1')
    return m.sort_values(TEAM_KEY).reset_index(drop=True),hashes

def reconcile(fullp,m,c):
    require(not fullp.duplicated(KEY).any(),'Duplicate source player key')
    counts=fullp.groupby(TEAM_KEY,as_index=False).agg(provider_player_rows=('player_id','size'),provider_team_name=('TEAM_NAME','first'))
    ledger=counts.merge(m,on=TEAM_KEY,how='outer',validate='one_to_one',indicator=True)
    ledger['membership_match_status']=ledger['_merge'].map({'both':'Matched D1 membership','left_only':'Outside reviewed D1 membership; division unresolved','right_only':'D1 membership without source players'}).astype(str)
    ledger['is_ncaa_d1']=ledger['_merge'].ne('left_only')
    ledger['provider_player_rows']=ledger.provider_player_rows.fillna(0).astype('int64')
    require(not ledger['_merge'].eq('right_only').any(),'D1 reference team absent from provider: review membership/source coverage before publication')
    ledger=ledger.drop(columns='_merge').sort_values(TEAM_KEY).reset_index(drop=True)
    return ledger

def attach_membership(frame,m,strict=False):
    out=frame.merge(m,on=TEAM_KEY,how='left',validate='many_to_one',indicator='_d1_join')
    if strict:
        require(out._d1_join.eq('both').all(),'Selected cohort includes unresolved/non-D1 team')
    return out[out._d1_join.eq('both')].drop(columns='_d1_join').reset_index(drop=True)

def raw_d1_skill_reference(skills):
    """D1 raw accumulated skill ranks, no Phase 2 exposure gate (legacy method)."""
    out=skills[SKILL_KEY+['team_id']].copy()
    for part in ('off','def','total'):
        raw='impact_'+part+'_raw'
        value=pd.to_numeric(skills[raw],errors='coerce').replace([np.inf,-np.inf],np.nan)
        out[raw+'_reference']=value
        groups=value.groupby([skills.api_season,skills.skill])
        out['computed_'+part+'_d1_league_pctile']=groups.rank(method='average',pct=True)*100
        out['d1_league_'+part+'_n']=groups.transform('count').astype('int64')
    return out

def attach_raw_d1_skill_ranks(skills,ref):
    out=skills.merge(ref,on=SKILL_KEY,suffixes=('','_reference'),how='left',validate='one_to_one')
    for part in ('off','def','total'):
        raw='impact_'+part+'_raw'; pct='computed_'+part+'_d1_league_pctile'; n='d1_league_'+part+'_n'
        v=pd.to_numeric(out[raw],errors='coerce'); rv=out[raw+'_reference']
        same_team=out.team_id.eq(out.team_id_reference)
        same_value=v.eq(rv)
        out['d1_league_'+part+'_status']=np.select([~same_team,v.isna(),~same_value,out[pct].notna()],['Source identity/vintage mismatch','Missing metric','Source vintage mismatch','Available'],default='Unavailable')
        out.loc[~same_team | ~same_value,pct]=np.nan
        out[n]=out[n].astype('Int64')
        out=out.drop(columns=raw+'_reference')
    return out.drop(columns='team_id_reference')

def comparison(old,new,keys,pairs,kind):
    merged=new[keys+[b for a,b in pairs]].merge(old[keys+list(dict.fromkeys(a for a,b in pairs))],on=keys,how='left',suffixes=('_new','_old'),validate='one_to_one')
    rows=[]
    for oldcol,newcol in pairs:
        same=oldcol==newcol
        a=pd.to_numeric(merged[oldcol+'_old' if same else oldcol],errors='coerce')
        b=pd.to_numeric(merged[newcol+'_new' if same else newcol],errors='coerce')
        for year in sorted(merged.api_season.unique()):
            mask=merged.api_season.eq(year)
            both=mask&a.notna()&b.notna()
            diff=(a[both]-b[both]).abs()
            rows.append(dict(api_season=int(year),comparison=kind,metric=newcol,matched_rows=int(mask.sum()),both_available=int(both.sum()),changed=int(diff.gt(1e-9).sum()),median_absolute_change=float(diff.median()) if len(diff) else None,max_absolute_change=float(diff.max()) if len(diff) else None,newly_suppressed=int((mask&a.notna()&b.isna()).sum()),newly_available=int((mask&a.isna()&b.notna()).sum())))
    return rows

def build_d1_bundle(players,skills,fullp,fulls,oldp,olds,root,destination,metadata,run_id):
    from .refresh import write_parquet
    root=Path(root);dest=Path(destination)
    configpath=root/'data/reference/peer_benchmark_rules_v2.json'
    c=json.loads(configpath.read_text())
    require(c['version']=='phase2_v2_d1','Unexpected D1 benchmark rules')
    m,hashes=load_membership(root,c)
    ledger=reconcile(fullp,m,c)
    fp=attach_membership(fullp,m)
    fs=attach_membership(fulls,m)
    p=attach_membership(players,m,strict=True)
    s=attach_membership(skills,m,strict=True)
    require(set(map(tuple,fs[KEY].drop_duplicates().to_numpy()))==set(map(tuple,fp[KEY].to_numpy())),'D1 skill/player coverage mismatch')
    require(fs.groupby(KEY).skill.nunique().eq(fulls.skill.nunique()).all(),'D1 skill coverage mismatch')
    rawref=raw_d1_skill_reference(fs)
    fs=attach_raw_d1_skill_ranks(fs,rawref)
    s=attach_raw_d1_skill_ranks(s,rawref)
    # Keep all legacy provider-wide fields, including their original labels and ranks.
    fp,fs,ref,qa=build_peer_features(fp,fs,fp,fs,c,metadata,run_id)
    # Reference distributions are identical for the full D1 and selected cohort views.
    # Supply the original (pre-Phase 2) D1 input frames, not already augmented v2 frames.
    refp=attach_membership(fullp,m);refs=attach_raw_d1_skill_ranks(attach_membership(fulls,m),rawref)
    cp,cs,cref,cqa=build_peer_features(p,s,refp,refs,c,metadata,run_id)
    pd.testing.assert_frame_equal(ref,cref)
    cohort_ids=set(pd.read_csv(root/'data/reference/cohort_45.csv').espn_team_id.astype(int))
    require(len(cohort_ids)==45,'Unexpected fixed cohort size')
    for pf,sf,scope in ((fp,fs,'D1 source population'),(cp,cs,'45-team cohort; D1 reference')):
        pf['d1_benchmark_eligible']=pf.position_benchmark_eligible
        sf['d1_benchmark_eligible']=sf.merge(pf[KEY+['position_benchmark_eligible']],on=KEY,how='left',validate='many_to_one').position_benchmark_eligible.to_numpy()
        for frame in (pf,sf):
            require(frame.is_ncaa_d1.eq(True).all(),'Non-D1 row in D1 publication')
            frame['in_cohort_45']=frame.team_id.isin(cohort_ids)
            frame['peer_output_population']=scope
            frame['peer_source_run_id']=run_id
            frame['d1_membership_reference_version']='sdv_2026_2027_plus_official_overrides_v1'
    dest.mkdir(parents=True,exist_ok=True)
    for frame,name in ((m,'wcbb_team_membership'),(ledger,'division_membership_reconciliation')):
        frame.to_csv(dest/f'{name}.csv',index=False)
        write_parquet(frame,dest/f'{name}.parquet')
    seasons={}
    for year in (2025,2026):
        fy=fp[fp.api_season.eq(year)]; sy=fs[fs.api_season.eq(year)]
        cy=cp[cp.api_season.eq(year)]; csy=cs[cs.api_season.eq(year)]
        for folder,a,b in ((dest/f'season={year}',fy,sy),(dest/'cohort_45'/f'season={year}',cy,csy)):
            write_parquet(a,folder/'player_peer_features.parquet')
            write_parquet(b,folder/'player_skill_peer_features.parquet')
        write_parquet(ref[ref.api_season.eq(year)],dest/f'season={year}/peer_benchmark_reference.parquet')
        fy_old=fullp[fullp.api_season.eq(year)]
        seasons[str(year)]={'provider_team_ids':int(fy_old.team_id.nunique()),'d1_team_ids':int(fy.team_id.nunique()),'excluded_team_ids':int(fy_old.team_id.nunique()-fy.team_id.nunique()),'provider_player_rows':len(fy_old),'d1_player_rows':len(fy),'excluded_player_rows':len(fy_old)-len(fy),'d1_skill_rows':len(sy),'d1_eligible_players':int(fy.position_benchmark_eligible.sum()),'excluded_previously_eligible':int(eligible(fy_old,c).sum()-fy.position_benchmark_eligible.sum()),'cohort_player_rows':len(cy),'cohort_skill_rows':len(csy),'d1_conferences':int(fy.conference_name.nunique()),'functional_candidates':int(fy.functional_strength_tags.ne('[]').sum())}
        require(len(sy)==len(fy)*fulls.skill.nunique(),'Unexpected D1 skill row count')
    ppairs=[(x,x) for x in fp if x.endswith('_pctile') and x in oldp]
    spairs=[(x,x) for x in fs if x.endswith('_position_pctile') and x in olds]
    spairs += [(f'computed_{part}_league_pctile',f'computed_{part}_d1_league_pctile') for part in ('off','def','total')]
    sensitivity=pd.DataFrame(comparison(oldp,fp,KEY,ppairs,'player')+comparison(olds,fs,SKILL_KEY,spairs,'skill'))
    sensitivity.to_csv(dest/'benchmark_population_comparison.csv',index=False)
    delta=fp[KEY+['team_id','fingerprint_total_per100_position_pctile','functional_strength_tags']].merge(oldp[KEY+['fingerprint_total_per100_position_pctile','functional_strength_tags']],on=KEY,how='left',validate='one_to_one',suffixes=('_d1','_provider'))
    delta['fingerprint_total_percentile_change']=delta.fingerprint_total_per100_position_pctile_d1-delta.fingerprint_total_per100_position_pctile_provider
    delta['functional_tags_changed']=delta.functional_strength_tags_d1.ne(delta.functional_strength_tags_provider)
    write_parquet(delta,dest/'player_benchmark_changes.parquet')
    receipt={'status':'PASS_WITH_REVIEW','version':c['version'],'population':c['population'],'source_run_id':run_id,'seasons':seasons,'reference_matches_cohort':True,'reference_rows':len(ref),'config_sha256':digest(configpath),'membership_input_sha256':hashes,'original_crosswalk_parquet_sha256':c['membership_policy']['crosswalk_parquet_sha256'],'source_reference_ids':{str(y):metadata[y]['reference_id'] for y in metadata},'cautions':['Membership based on supplied SDV and two official historical overrides; NCAA team IDs not provided. Unknown teams excluded, not labeled D2/D3. D1 affiliation is not NCAA championship eligibility.','D1 raw league rank fields use all available D1 raw skill values without Phase 2 exposure gating; legacy computed_*_league_pctile remains provider-wide.','Current season comparisons remain provisional; functional candidates require film review.','Source metrics may reflect games against non-D1 opponents; no game-level schedule adjustment.']}
    receipt['output_sha256']={x.relative_to(dest).as_posix():digest(x) for x in sorted(dest.rglob('*')) if x.is_file()}
    (dest/'manifest.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    return receipt

def prepare_d1_bundle(root,stage,manifest):
    from .refresh import read_parquet
    root=Path(root);stage=Path(stage)
    phase2=stage/'processed/phase2'
    meta={int(y):v for y,v in manifest['peer_benchmarks']['provenance'].items()}
    benchmark=stage/'benchmark_publication/latest'
    def combined(folder,name):
        return pd.concat([read_parquet(folder/f'season={y}'/name) for y in (2025,2026)],ignore_index=True)
    return build_d1_bundle(read_parquet(stage/'processed/player_features.parquet'),read_parquet(stage/'processed/player_skill_features.parquet'),combined(benchmark,'players.parquet'),combined(benchmark,'skills.parquet'),combined(phase2/'full_population','player_peer_features.parquet'),combined(phase2/'full_population','player_skill_peer_features.parquet'),root,phase2/'d1_population',meta,manifest['run_id'])
