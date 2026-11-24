# Phase 2 QA report

Source run: `20261124T013238Z`. Status: **PASS_WITH_REVIEW**.

## Published coverage

- 1,113 selected player-season rows; 23,373 selected player-season-skill rows.
- 1,020 unique season × comparison kind × group × metric reference rows.
- Full-source inputs: 4,677 historical and 5,590 current players, before eligibility filtering.
- The 45 teams are the output selection, not the benchmark universe. Provider coverage is not independently NCAA-roster certified.
- All original ESPN and Phase 1 columns and the existing accumulated-skill percentiles remain unchanged. No composite score or single archetype was added.

## Full-source eligibility and exclusions

Reason counts overlap and should not be added to obtain total exclusions. Metric-specific valid denominators are in the reference table.

### API 2025

- total_players: 4677
- eligible_players: 3142
- identity_review: 93
- unknown_position: 35
- below_or_missing_games: 507
- below_or_missing_minutes: 1317
- below_or_missing_possessions: 1456
- exposure_reconciliation_review: 0
- note: Exclusion reason counts overlap; valid metric-specific counts are in the reference table.

Eligible positions: {"Center": 143, "Forward": 945, "Guard": 2054}

### API 2026

- total_players: 5590
- eligible_players: 1806
- identity_review: 200
- unknown_position: 82
- below_or_missing_games: 2313
- below_or_missing_minutes: 3411
- below_or_missing_possessions: 3680
- exposure_reconciliation_review: 0
- note: Exclusion reason counts overlap; valid metric-specific counts are in the reference table.

Eligible positions: {"Center": 59, "Forward": 482, "Guard": 1265}

## Selected position evidence

- Ineligible exposure or identity: 458
- Available: 398
- Provisional: 253
- Unknown position: 4

## Selected role evidence

- Role unavailable: 463
- Available: 397
- Provisional: 245
- Insufficient peers: 8

## Reference availability

- Insufficient peers: 352
- Available: 210
- Provisional: 198
- Unknown position: 170
- Constant distribution: 90

## Selected skill total-component status

- Ineligible exposure or identity: 9618
- Available: 6368
- Provisional: 4048
- Constant distribution: 3255
- Unknown position: 84

## Function evidence

- Model-based candidate; film review required: 632
- Ineligible or source vintage mismatch: 462
- No qualifying candidate: 19

## Missing player benchmarks

- usage_position_pctile: 463
- efg_position_pctile: 462
- efg_role_pctile: 471
- ast40_position_pctile: 462
- ast40_role_pctile: 471
- reb40_position_pctile: 462
- ftr_position_pctile: 462
- tov_position_pctile: 462
- tov_role_pctile: 471
- assisted_rate_position_pctile: 462
- fingerprint_off_per100_position_pctile: 462
- fingerprint_def_per100_position_pctile: 462
- fingerprint_total_per100_position_pctile: 462
- fingerprint_total_per100_role_pctile: 471

## Limits and required review

The selected Phase 1 identity-review count remains 18. Name differences are review signals, not confirmed identity errors; no player or team IDs were reassigned.

The current full-source center reference has 59 eligible players, but usage bands have only 19–20 valid peers. Those role percentiles are suppressed under the n=30 rule. Wing and Hybrid are absent from explicit source position labels and are reported with zero reference counts, not inferred from average position. Constant skill distributions remain unavailable.

Historical inputs were retrieved separately from the frozen baseline and retain their own date and hashes. The original seven historical Parquet files are byte-for-byte unchanged. Metric/context mismatches would be suppressed rather than silently using a newer historical metric value. The subsequent live refresh reused the historical reference extraction, with fresh current inputs checked against the ingestion response hashes.

632 of 651 benchmark-eligible selected players have at least one model-based function candidate. This broad coverage is expected from multiple parallel skill comparisons; candidates are neither rarity nor statistical significance claims. Positive contribution and high position percentile are scouting leads that require film and game-context validation. No overlapping skills are summed.

AST_40 and REB_40 comparisons remain exploratory until their exact source rate denominators are independently verified. High usage, assisted-rate or turnover percentiles do not imply quality. Current-season comparisons are provisional; historical Available refers to statistical availability, not independently verified basketball conclusions.

## Validation performed

- Full regression suite, including full-source universe, exact-member ties, per-metric denominators, sparse/constant suppression, role independence, vintage mismatch, negative-contribution handling, original column preservation and full-source input integrity.
- Initial and subsequent full live refresh, manifest/config/output hash checks, and preserved historical source hashes.
- Representative eligible guard, forward and center profiles inspected in both seasons.
- Independent recomputation of exported player and skill percentiles against full-source caches found no mismatches.
- Injected Phase 2 failure preserved prior source/Phase 1 files; existing mid-promotion rollback test still passes.

Use [the feature dictionary](peer_feature_dictionary.md) and [example queries](../sql/peer_benchmark_examples.sql) to interpret the tables. Complete machine-readable QA is `data/processed/phase2/manifest.json`.
