"""Bounded GitHub-readable previews and full-file Parquet profiling."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pandas as pd
from .features import require

PREVIEW_LIMIT = 20
POLICY = 'Canonical latest, frozen, processed and stable benchmark Parquet files; immutable archival copies are not reprofiled.'

def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()

def source_paths(mappings):
    found={}
    for source,logical in mappings:
        source=Path(source)
        for path in sorted(source.rglob('*.parquet')):
            relative=(Path(logical)/path.relative_to(source)).as_posix()
            require(relative not in found,'Duplicate catalog logical path: '+relative)
            found[relative]=path
    return found

def distinct(frame,column):
    return int(frame[column].nunique(dropna=True)) if column in frame else None

def count_value(frame,column,value):
    return int(frame[column].eq(value).sum()) if column in frame else None

def pct(n,d):
    return round(100*n/d,6) if d else None

def population(path):
    if '/d1_population/' in path:
        if 'peer_benchmark_reference' in path:return 'Division I-competing reference distributions'
        if '/cohort_45/' in path:return 'Selected cohort; Division I-competing reference'
        if 'division_membership_reconciliation' in path:return 'All provider team IDs; D1 membership audit'
        return 'Division I-competing membership or player population'
    if '/benchmarks/latest/' in path or '/full_population/' in path:
        return 'Full ESPN provider feed; not independently certified D1'
    if 'peer_benchmark_reference' in path:
        return 'Full-provider benchmark distributions; aggregate reference rows'
    return 'Selected cohort or associated source QA exceptions'

def preview_indices(n):
    k=min(n,PREVIEW_LIMIT)
    return [0] if k==1 else [i*(n-1)//(k-1) for i in range(k)] if k else []

def write_catalog(mappings,destination,run_id):
    from .refresh import _duckdb
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    sources=source_paths(mappings)
    require(bool(sources),'No Parquet inputs for catalog')
    datasets=[];columns=[];coverage=[]
    con=_duckdb().connect(':memory:')
    try:
        for logical,source in sorted(sources.items()):
            schema=con.execute('DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning=false)',[str(source)]).fetchall()
            frame=con.execute('SELECT * FROM read_parquet(?, hive_partitioning=false)',[str(source)]).df()
            require(list(frame.columns)==[row[0] for row in schema],'Catalog schema mismatch: '+logical)
            n=len(frame);missing=frame.isna().sum();indices=preview_indices(n)
            rel=Path(logical).relative_to('data').with_suffix('.csv')
            preview=Path('previews')/rel;profile=Path('columns')/rel
            for out in (preview,profile):(dest/out).parent.mkdir(parents=True,exist_ok=True)
            frame.iloc[indices].to_csv(dest/preview,index=False)
            per=[]
            for i,(name,dtype,*_) in enumerate(schema):
                m=int(missing[name]);series=frame[name]
                blanks=int(series.map(lambda v:isinstance(v,str) and not v.strip()).sum()) if dtype=='VARCHAR' else None
                per.append(dict(dataset_path=logical,column_index=i,column=name,duckdb_type=dtype,
                                pandas_dtype=str(series.dtype),rows=n,non_missing=n-m,missing=m,
                                missing_pct=pct(m,n),coverage_pct=pct(n-m,n),blank_string_count=blanks))
            pd.DataFrame(per).to_csv(dest/profile,index=False)
            columns.extend(per)
            seasons=sorted(str(v) for v in frame.api_season.dropna().unique()) if 'api_season' in frame else []
            datasets.append(dict(dataset_path=logical,source_run_id=run_id,population=population(logical),
                rows=n,columns=len(schema),bytes=source.stat().st_size,sha256=sha256(source),
                preview_rows=len(indices),preview_path=preview.as_posix(),column_profile_path=profile.as_posix(),
                seasons=';'.join(seasons),distinct_team_ids=distinct(frame,'team_id'),distinct_player_ids=distinct(frame,'player_id'),
                distinct_skills=distinct(frame,'skill'),benchmark_eligible_rows=count_value(frame,'position_benchmark_eligible',True),
                missing_cells=int(missing.sum()),missing_cell_pct=pct(int(missing.sum()),n*len(schema))))
            groups=frame.groupby('api_season',dropna=False,sort=True) if 'api_season' in frame and n else [('Not applicable' if 'api_season' not in frame else 'Empty',frame)]
            for season,g in groups:
                coverage.append(dict(dataset_path=logical,api_season=season,rows=len(g),
                    distinct_team_ids=distinct(g,'team_id'),distinct_player_ids=distinct(g,'player_id'),
                    distinct_skills=distinct(g,'skill'),benchmark_eligible_rows=count_value(g,'position_benchmark_eligible',True),
                    cohort_member_rows=count_value(g,'in_cohort_45',True),outside_cohort_rows=count_value(g,'in_cohort_45',False)))
    finally:
        con.close()
    pd.DataFrame(datasets).to_csv(dest/'datasets.csv',index=False)
    pd.DataFrame(columns).to_csv(dest/'columns.csv',index=False)
    pd.DataFrame(coverage).to_csv(dest/'coverage.csv',index=False)
    lines=['# WCBB Parquet dataset catalog','',f'Publication run: `{run_id}`','',POLICY,'',
           'Previews contain at most 20 original rows spread over physical file order, not statistical samples. Null/NaN counts use the entire file; blank strings are separate. Empty files have header-only previews and undefined missingness rates. Team IDs are provider IDs, not certified Division I membership.','',
           '[Dataset inventory](datasets.csv) · [All column profiles](columns.csv) · [Season coverage](coverage.csv) · [Manifest](manifest.json)','',
           '| Parquet dataset | Rows | Columns | Preview | Column profile |','|---|---:|---:|---|---|']
    for d in datasets:
        lines.append(f"| [`{d['dataset_path']}`](../../../{d['dataset_path']}) | {d['rows']:,} | {d['columns']} | [CSV]({d['preview_path']}) | [CSV]({d['column_profile_path']}) |")
    (dest/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    receipt={'source_run_id':run_id,'catalog_version':'v1','status':'PASS','scope':POLICY,
             'preview_limit':PREVIEW_LIMIT,'sampling':'Deterministic evenly spaced physical row indices; not a statistical sample',
             'dataset_count':len(datasets),'column_profile_count':len(columns),'coverage_row_count':len(coverage),
             'source_sha256':{d['dataset_path']:d['sha256'] for d in datasets},
             'output_sha256':{p.relative_to(dest).as_posix():sha256(p) for p in sorted(dest.rglob('*')) if p.is_file()}}
    (dest/'manifest.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return receipt
