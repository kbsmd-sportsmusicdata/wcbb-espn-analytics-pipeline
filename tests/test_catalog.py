import json
import pandas as pd
from wcbb_espn.catalog import write_catalog,preview_indices,sha256
from wcbb_espn.refresh import write_parquet

def test_catalog_exact_counts_nulls_and_preview_bound(tmp_path):
    source=tmp_path/'source';source.mkdir()
    frame=pd.DataFrame({'api_season':[2025]*15+[2026]*15,'team_id':[1,2,3]*10,
                        'player_id':range(30),'metric':[None]*3+[float(i) for i in range(27)],
                        'note':['']+['x']*29,'position_benchmark_eligible':[True]*10+[False]*20})
    write_parquet(frame,source/'players.parquet')
    write_parquet(frame.iloc[:0].copy(),source/'empty.parquet')
    dest=tmp_path/'catalog'
    receipt=write_catalog([(source,'data/processed/full_population')],dest,'test-run')
    assert receipt['dataset_count']==2 and receipt['source_run_id']=='test-run'
    inv=pd.read_csv(dest/'datasets.csv').set_index('dataset_path')
    row=inv.loc['data/processed/full_population/players.parquet']
    assert row.rows==30 and row.preview_rows==20 and row.distinct_team_ids==3
    assert row.missing_cells==3 and row.benchmark_eligible_rows==10
    sample=pd.read_csv(dest/row.preview_path)
    assert sample.player_id.tolist()==preview_indices(30)
    assert list(sample.columns)==list(frame.columns)
    profile=pd.read_csv(dest/row.column_profile_path).set_index('column')
    assert profile.loc['metric','missing']==3 and profile.loc['metric','coverage_pct']==90
    assert profile.loc['note','blank_string_count']==1
    assert profile.loc['metric','duckdb_type']=='DOUBLE'
    coverage=pd.read_csv(dest/'coverage.csv')
    assert coverage.loc[coverage.dataset_path.eq(row.name),'rows'].tolist()==[15,15]
    emptyrow=inv.loc['data/processed/full_population/empty.parquet']
    assert emptyrow.rows==emptyrow.preview_rows==0
    assert pd.isna(emptyrow.missing_cell_pct)
    assert pd.read_csv(dest/emptyrow.preview_path).empty
    assert receipt['source_sha256'][row.name]==sha256(source/'players.parquet')
    assert all(sha256(dest/name)==digest for name,digest in receipt['output_sha256'].items())
    assert json.loads((dest/'manifest.json').read_text())==receipt

def test_catalog_is_deterministic_and_source_files_unchanged(tmp_path):
    source=tmp_path/'source';source.mkdir()
    write_parquet(pd.DataFrame({'x':list(range(100))}),source/'x.parquet')
    before=sha256(source/'x.parquet')
    a=write_catalog([(source,'data/latest')],tmp_path/'one','run')
    b=write_catalog([(source,'data/latest')],tmp_path/'two','run')
    assert a==b and sha256(source/'x.parquet')==before
    assert preview_indices(1)==[0] and preview_indices(0)==[]
    assert preview_indices(100)[-1]==99
