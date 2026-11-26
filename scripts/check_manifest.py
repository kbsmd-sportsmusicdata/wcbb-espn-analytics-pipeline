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
