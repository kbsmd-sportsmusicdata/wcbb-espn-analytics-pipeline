-- Run from the repository root in DuckDB, or replace paths with downloaded files.
-- One player profile: parameterize the ESPN player ID in your application.
SELECT api_season, DISPLAY_NAME, team_requested, fingerprint_impact_total_per100,
       fingerprint_minutes, evidence_status, identity_consistency_status
FROM read_parquet('data/processed/player_features.parquet')
WHERE player_id = 4433794 ORDER BY api_season;

-- Compare source-scoped profiles without creating a composite or rank.
SELECT DISPLAY_NAME, position_group, fingerprint_impact_off_per100,
       fingerprint_impact_def_per100, usage_pct, minutes_sample_tier, evidence_status
FROM read_parquet('data/processed/player_features.parquet')
WHERE api_season = 2026 AND player_id IN (4433794, 4565508);

-- Inspect skills and preserve the distinction between raw full-feed percentiles
-- and independently derived per-100 contributions.
SELECT skill, functional_skill_group, impact_total_raw, skill_impact_total_per100,
       computed_total_league_pctile, league_total_n, percentile_method
FROM read_parquet('data/processed/player_skill_features.parquet')
WHERE api_season = 2026 AND player_id = 4433794 ORDER BY skill;

-- The same tables are independently queryable in data/processed/player_features.duckdb.
-- Its table names are player_features and player_skill_features.
