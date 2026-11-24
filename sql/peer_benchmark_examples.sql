-- Run in DuckDB from the repository root; candidates are not overall rankings.
-- 1. Position-adjusted player comparison. Exact per-metric sample sizes are visible.
SELECT DISPLAY_NAME, position_group, api_season, usage_position_pctile,
       efg_position_pctile, efg_position_n, efg_position_status,
       fingerprint_total_per100_position_pctile, position_benchmark_status
FROM read_parquet('data/processed/phase2/player_peer_features.parquet')
WHERE player_id IN (4433794,4565508) ORDER BY api_season, player_id;

-- 2. Low-usage film-review leads; not a draft, breakout or composite ranking.
SELECT DISPLAY_NAME, team_requested, position_group, usage_role_band,
       efg_role_pctile, efg_role_n, role_benchmark_status, functional_strength_tags
FROM read_parquet('data/processed/phase2/player_peer_features.parquet')
WHERE api_season=2026 AND usage_role_band='Lower usage'
  AND efg_role_pctile>=75 AND position_benchmark_eligible;

-- 3. Player-by-function profile. Retain statistical distinctions and status.
SELECT player_id, skill, functional_skill_group, functional_strength_tag,
       skill_impact_off_per100, skill_off_per100_position_pctile,
       skill_off_per100_position_n, skill_off_per100_position_status,
       skill_statistical_distinction
FROM read_parquet('data/processed/phase2/player_skill_peer_features.parquet')
WHERE api_season=2026 AND player_id=4433794 ORDER BY skill;

-- 4. Team function matrix: count DISTINCT eligible players per candidate function,
-- never overlapping skill totals. Current results are provisional film-review leads.
SELECT p.team_requested, s.functional_strength_tag,
       count(DISTINCT p.player_id) AS eligible_candidate_players
FROM read_parquet('data/processed/phase2/player_peer_features.parquet') p
JOIN read_parquet('data/processed/phase2/player_skill_peer_features.parquet') s
USING(api_season,player_id,team_id)
WHERE p.api_season=2026 AND p.position_benchmark_eligible
  AND s.functional_strength_tag IS NOT NULL
GROUP BY p.team_requested,s.functional_strength_tag
ORDER BY p.team_requested,s.functional_strength_tag;
