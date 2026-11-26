#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=ROOT/'reports/manifest_latest.json'
assert manifest.is_file(), 'No validated manifest published'
s=json.loads(manifest.read_text())
assert s['status'] in ('PASS','PASS_WITH_REVIEW'),s
assert s['cohort_count']==45
assert {q['api_season']:q['team_count'] for q in s['qa']}=={2025:45,2026:45}
assert (ROOT/'data/latest/wcbb_espn_data_families.duckdb').is_file()
for family,tables in {'wcbb_espn_team_netpoints':['team_season','four_factors','bpi','unkeyed_team_stats'],
                     'wcbb_espn_player_fingerprints':['player_season','skill_impacts','team_id_discrepancies']}.items():
    for name in tables:
        assert (ROOT/'data/latest'/family/f'{name}.parquet').is_file(),(family,name)
print('45 teams, two seasons, both DuckDB data families: manifest and files verified')
# Processed features are certified against the same source run and output hashes.
import hashlib
processed=ROOT/'data/processed'
features=json.loads((processed/'manifest.json').read_text())
assert features['status'] in ('PASS','PASS_WITH_REVIEW')
assert features['source_run_id']==s['run_id']
assert s['processed_features']['source_run_id']==s['run_id']
for name,digest in features['output_sha256'].items():
    assert hashlib.sha256((processed/name).read_bytes()).hexdigest()==digest,name
assert (processed/'player_features.parquet').is_file()
assert (processed/'player_skill_features.parquet').is_file()
print('Processed player/skill outputs match the validated source run and file hashes')
# Independently validate Phase 2 files and source/rule linkage.
peers=processed/'phase2'
peer=json.loads((peers/'manifest.json').read_text())
assert peer['source_run_id']==s['run_id']
assert peer['status'] in ('PASS','PASS_WITH_REVIEW')
assert s['peer_benchmarks']['source_run_id']==s['run_id']
assert hashlib.sha256((ROOT/'data/reference/peer_benchmark_rules_v1.json').read_bytes()).hexdigest()==peer['config_sha256']
for name,digest in peer['output_sha256'].items():
    assert hashlib.sha256((peers/name).read_bytes()).hexdigest()==digest,name
print('Full-source Phase 2 outputs match the source run, configuration and file hashes')

# Stable benchmark inputs and full-population outputs must match the published source run.
stable=ROOT/'data/benchmarks/latest'
latest=json.loads((stable/'manifest.json').read_text())
assert latest['source_run_id']==s['run_id']
full=peer['full_population_outputs']
assert full['source_run_id']==s['run_id'] and full['reference_matches_cohort']
for year in ('2025','2026'):
    meta=peer['provenance'][year]
    stable_meta=latest['seasons'][year]
    assert stable_meta['reference_id']==meta['reference_id']
    assert stable_meta['file_sha256']==meta['file_sha256']
    assert full['seasons'][year]['player_rows']==meta['player_rows']==stable_meta['player_rows']
    assert full['seasons'][year]['skill_rows']==meta['skill_rows']==stable_meta['skill_rows']
    for name,digest in stable_meta['file_sha256'].items():
        assert hashlib.sha256((stable/f'season={year}'/name).read_bytes()).hexdigest()==digest,name
    for name in ('player_peer_features.parquet','player_skill_peer_features.parquet'):
        assert f'full_population/season={year}/{name}' in peer['output_sha256']
print('Stable input paths and full-population Phase 2 outputs verified')

# Verify every canonical Parquet path and the generated catalog's source/output hashes.
import csv
catalog=ROOT/'data/latest/catalog'
receipt=json.loads((catalog/'manifest.json').read_text())
assert receipt==s['dataset_catalog']
assert receipt['source_run_id']==s['run_id'] and receipt['status']=='PASS'
canonical=set()
for directory in ('data/benchmarks/latest','data/frozen','data/latest','data/processed'):
    for path in (ROOT/directory).rglob('*.parquet'):
        rel=path.relative_to(ROOT)
        if 'snapshots' not in rel.parts:canonical.add(rel.as_posix())
assert canonical==set(receipt['source_sha256']), (canonical-set(receipt['source_sha256']),set(receipt['source_sha256'])-canonical)
for name,digest in receipt['source_sha256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
for name,digest in receipt['output_sha256'].items():
    assert hashlib.sha256((catalog/name).read_bytes()).hexdigest()==digest,name
with (catalog/'datasets.csv').open(newline='',encoding='utf-8') as stream:
    inventory=list(csv.DictReader(stream))
assert len(inventory)==receipt['dataset_count']==len(canonical)
for row in inventory:
    with (catalog/row['preview_path']).open(newline='',encoding='utf-8') as stream:
        reader=csv.reader(stream);header=next(reader);n=sum(1 for _ in reader)
    assert len(header)==int(row['columns'])
    assert n==int(row['preview_rows'])==min(int(row['rows']),receipt['preview_limit'])
print('Catalog source hashes, output hashes, canonical coverage and preview row limits verified')
