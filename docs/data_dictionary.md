# Data dictionary

## Tables and grain

| Schema | Table | Grain / key |
|---|---|---|
| `wcbb_espn_team_netpoints` | `team_season` | `api_season`, `team_id` |
| `wcbb_espn_team_netpoints` | `four_factors` | `api_season`, `team_id`, `Side` |
| `wcbb_espn_team_netpoints` | `bpi` | `api_season`, `team_id` |
| `wcbb_espn_team_netpoints` | `unkeyed_team_stats` | Quarantined source rows without usable team ID |
| `wcbb_espn_player_fingerprints` | `player_season` | `api_season`, `player_id` |
| `wcbb_espn_player_fingerprints` | `skill_impacts` | `api_season`, `player_id`, `skill` |
| `wcbb_espn_player_fingerprints` | `team_id_discrepancies` | Source team-ID disagreement evidence |
| `main` | `cohort_45` | `espn_team_id` |
| `main` | `qa_summary` | One QA record per API season |

## Identity, metrics, and lineage

| Fields | Meaning |
|---|---|
| `api_season`, `academic_season` | Source year parameter and academic-season label |
| `team_id`, `player_id` | Canonical numeric ESPN join identifiers |
| `source_team_id` | Original BPI/player `TEAM_ID` value; may retain source string type |
| `team_requested`, `cohort`, `ap_rank` | Frozen cohort name, AP_TOP25/WATCHLIST label, and November 16 rank; rank is null for watchlist teams |
| `espn_team_name`, `DISPLAY_NAME` | Provider team/player labels |
| `team_net_points_off`, `team_net_points_def`, `team_net_points_total` | Provider team Net Points components |
| `team_stat_*`, `bpi_*` | Original team-stat and BPI fields joined to the team-season table |
| `Side`, `Total`, `FB`, `FG2`, `FG3`, `FT`, `Putback`, `REB`, `TOV` | Original team four-factor side and contribution fields |
| `BPI`, `BPI_OFF`, `BPI_DEF`, `*_RK` | Source BPI values and rank fields in the BPI table |
| `ONETPTS`, `DNETPTS`, `TNETPTS` | Source player offensive, defensive, and total Net Points |
| `fingerprint_team_id`, `fingerprint_player_name`, `fingerprint_*_raw` | Separate fingerprint identity and original impact values |
| `fingerprint_team_id_disagrees`, `reason` | Review flags; original IDs are retained without reassignment |
| `skill`, `impact_off_raw`, `impact_def_raw`, `impact_total_raw` | Skill label and original source components |
| `computed_*_league_pctile`, `league_*_n`, `percentile_method` | Descriptive full-feed percentile, denominator, and method label |
| `netpoints_additivity_delta` | Total minus offense minus defense; absolute tolerance is 0.15 |
| `retrieval_utc`, `team_data_source_url`, `fingerprint_source_url` | Table retrieval time and source routes |
| `rejection_reason` | Why a source team-stat row is quarantined |

The manifest adds run ID, status, row counts, source hashes/byte counts, player-ID changes, and snapshot location. Frozen baseline provenance retains its original retrieval time; it is not relabeled with each refresh time. Fields prefixed `team_stat_`, BPI fields, and original player columns remain source-defined; consult ESPN rather than assuming cross-model equivalence.

## Processed feature layer

See [Phase 1 feature dictionary](player_feature_dictionary.md) for all added fields, exact formulas, units, inputs, null rules, populations and provenance. Source-normalized fields above are unchanged.

## Phase 2 peer benchmarks

The [Phase 2 dictionary](peer_feature_dictionary.md) documents position/role/skill percentiles, metric-specific denominators, source vintages, suppression states and model-based function candidates. The comparison universe is the full provider feed, while outputs remain the selected 45 teams.

## GitHub-readable Parquet catalog

After every successful refresh, open [data/latest/catalog/README.md](../data/latest/catalog/README.md). The catalog indexes canonical published Parquet paths (frozen cohort, stable full-provider inputs, selected Phase 1/2 and provider-wide Phase 2). Archived run snapshots and versioned benchmark copies remain at their original locations and are not duplicated.

- `datasets.csv`: file path, rows, columns, size, SHA-256, coverage and links to individual previews/profiles.
- `columns.csv` and `columns/<dataset path>.csv`: DuckDB logical types, pandas dtypes, exact full-file missing/nonmissing counts, coverage and separately counted blank strings.
- `coverage.csv`: file/season rows, distinct team/player/skill IDs, benchmark-eligible and cohort-membership counts where present.
- `previews/<dataset path>.csv`: at most 20 original rows spread across physical order; no imputation or statistical representativeness claim.
- `manifest.json`: run ID, source and output hashes, scope and preview policy.

NA/NaN are missing, not empty strings; rates for zero-row datasets are undefined. Team/player counts are distinct provider identifiers, not independently verified NCAA membership. Catalog generation occurs before rollback-protected publication and is checked by the existing manifest validator. No new scheduler or dependency is needed. The first successful refresh after merging generates the files.
