# ESPN Analytics WCBB pipeline: overview

This repository maintains source-backed team and player metrics for a fixed 45-school cohort: the November 16, 2026 AP Top 25 and 20 watchlist schools. North Carolina (153) and NC State (152) remain separate members.

The first GitHub refresh succeeded on November 23, 2026. Its QA manifest records 45 teams in each season, 564 players in 2025–26, and 549 players in 2026–27. These are source-season records, not independently verified roster availability. Current-season counts can change.

Outputs include team Net Points, four factors, BPI, player fingerprints, skill impacts, and exception tables. The combined database is `data/latest/wcbb_espn_data_families.duckdb`; matching Parquet tables are under `data/latest/`.

The 2025–26 baseline stays frozen. Tuesday and Friday refreshes at 9:15 a.m. America/Los_Angeles update 2026–27 and retain dated snapshots. Successful manual execution is verified; the first scheduled execution remains an operational check.

Use these tables for source-specific scouting, role evaluation, and team context. ESPN Net Points, BPI, and computed skill percentiles describe different measures and should retain their labels. See [methodology](methodology.md), [data dictionary](data_dictionary.md), and [QA rules](QA_GATES.md).
