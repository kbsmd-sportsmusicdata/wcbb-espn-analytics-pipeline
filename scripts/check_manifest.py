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
