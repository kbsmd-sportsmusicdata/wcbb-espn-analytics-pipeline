# ESPN WCBB ingestion — QA and data dictionary

## Source families and grains

| Family | DuckDB table | Primary key | Key ESPN source fields |
|---|---|---|---|
| Team Net Points | `wcbb_espn_team_netpoints.team_season` | `(api_season, team_id)` | `offense_total`, `defense_total`, `total_total`, standard `team_stat_*` factors, `bpi_*` |
| Team four factors | `wcbb_espn_team_netpoints.four_factors` | `(api_season, team_id, Side)` | Offense/Defense/Total categories `FB`, `FG2`, `FG3`, `FT`, `Putback`, `REB`, `TOV`, `Total` |
| Source team ID exceptions | `wcbb_espn_team_netpoints.unkeyed_team_stats` | review table | Source team-stat rows with no usable `digital_team_id` |
| Team BPI | `wcbb_espn_team_netpoints.bpi` | `(api_season, team_id)` | `BPI`, `BPI_RK`, `BPI_OFF`, `BPI_OFF_RK`, `BPI_DEF`, `BPI_DEF_RK` |
| Player fingerprints | `wcbb_espn_player_fingerprints.player_season` | `(api_season, player_id)` | `ONETPTS`, `DNETPTS`, `TNETPTS`, source `fingerprint_*`, `fingerprint_team_id` |
| Skill impacts | `wcbb_espn_player_fingerprints.skill_impacts` | `(api_season, player_id, skill)` | `impact_off_raw`, `impact_def_raw`, `impact_total_raw`, `computed_*_league_pctile` |
| Team ID discrepancies | `wcbb_espn_player_fingerprints.team_id_discrepancies` | review table | Both provider team IDs and player names; never auto-reassign |

API `season=2026` means **academic season 2026–27**; API `season=2025` means **2025–26**.

Source API:
- `https://espnanalytics.com/api/team-data?league=wcbb&season=2026`
- `https://espnanalytics.com/api/fingerprint-data?league=wcbb&season=2026`

The team endpoint nests JSON tables under `team4f`, `team_stats`, `bpi_stats`, `plyr_stats`. The live feeds return column-indexed objects such as `{"TEAM_ID":{"0":"152"},"BPI":{"0":15.0}}`, often encoded as JSON strings. The parser converts these to row records by matching source row indices, while also accepting existing row-record lists. Empty tables, malformed column structures, and inconsistent row indices still stop publication. The fingerprint endpoint is a player-ID-keyed object. `digital_team_id` and `TEAM_ID` are cross-family IDs; `tmID` is a different source field and must **not** be substituted as the canonical ESPN team ID.

In exported BPI and player tables, the original `TEAM_ID` value is named `source_team_id`, while `team_id` is the canonical numeric join key. This prevents DuckDB's case-insensitive identifiers from renaming one of the two fields during export. Parquet reloads disable automatic directory partition columns; the explicit `api_season` and `academic_season` columns remain authoritative.

## Cohort

The original 25-school November 16 AP poll plus 19 watchlist schools gained NC State as an explicitly supplemental 20th watchlist school, for 45 total. North Carolina (153) remains ranked 24; NC State (152) remains unranked/watchlist in this fixed snapshot. See `data/reference/cohort_45.csv` for exact IDs, source date, and provenance.

## Hard-stop QA

The pipeline throws an error and does not commit a new remote snapshot if:
- A provider request fails, changes schema, returns malformed JSON, or has an empty required family.
- Expected cohort IDs, team stats, all three four-factor sides or BPI rows are missing.
- Duplicate player IDs or duplicate team/model grain keys appear in input/output.
- Cohort player IDs lack fingerprint metadata or associated skills.
- Source team Net Points differ from offense + defense by **more than 0.15** (allowing provider rounding), or player Net Points differ by more than 0.15.
- More than 10% of players in the previous current-season snapshot disappear on refresh (with a minimum 5-player absolute tolerance).
- Parquet or DuckDB export fails.

Individual source ID team disagreements are **not silently resolved**. Preserve `team_id` and `fingerprint_team_id`, output discrepancy table and mark `PASS_WITH_REVIEW`. A future source team-label mismatch therefore stays visible instead of duplicating a player-season.

## Expected baseline vs moving season

2025–26 historical source data is fetched on the **first successful run** and stored under `data/frozen/season=2025/`. It is *not* refetched each Tuesday/Friday; use an explicit historic backfill process for corrections. 2026–27 lives under `data/latest/season=2026/`, versioned `data/snapshots/<UTC-run>/season=2026/`, and combined `data/latest/` Parquet plus DuckDB.

Due to source model differences, never treat `BPI`, player `TNETPTS`, team `total_total`, source skill impacts and custom calculated percentiles as interchangeable composite rankings. Our calculated percentiles rank the **full ESPN source feed** within skill and source season, not just 45 selected schools, and are **not** ESPN's official displayed percentile fields.

## Reproducibility and source rights

The refresh manifest includes original endpoint URLs, UTC retrieval timestamp, response byte length, SHA-256, exact row counts and QA statuses. Raw source JSON is **not** committed to Git; source rights for bulk redistribution have not been verified. Keep the new repo private while source permission is assessed, and preserve the attribution and provider links.

GitHub Actions scheduled runs can be delayed; they are not a transactional real-time feed. On an unsuccessful run, the job fails before Git commits anything, leaving the last remote snapshot untouched. Check the Actions job log and last manifest before presenting current-season reports.

## Frozen source provenance

The baseline retains its original source metadata in `data/frozen/season=2025/provenance.json`. Subsequent QA summaries carry forward the same URLs, response hashes, byte counts, and retrieval time. Existing repositories recover a missing provenance file from a matching snapshot manifest. Metadata must match the frozen table retrieval time and contain both historical source URLs and valid SHA-256 hashes; otherwise publication stops. Recovery never refetches or rewrites the baseline Parquet tables.

## Phase 1 feature publication gate

Feature calculations, critical key/source-preservation checks, numeric validation, taxonomy validation and all exports run in staging before any source or processed output promotion. Duplicate or missing keys, orphan or mismatched player/skill links, unknown skills, infinite derived outputs, or out-of-range derived displays stop publication. Missing input observations propagate to null/Unknown and are counted. Source anomalies remain in original fields and are flagged. Identity name variants receive Identity review; small samples are descriptive evidence limits. The processed manifest records source QA, source run ID, rule hashes, output hashes, null counts and categorical coverage. A regression test injects critical feature failure and checks that all previously published source and processed files remain unchanged.

Publication copy errors trigger rollback of all replaced source and processed files, including latest manifests. Prior snapshots are not recopied for rollback. GitHub additionally publishes each successful run in one Git commit. Abrupt machine termination outside Python exception handling is not an atomic local filesystem transaction; the prior remote Git commit remains authoritative. The turnover skill is labeled Possession management / defensive activity because both offensive costs and defensive gains are present.

## Phase 2 benchmark gates

Current full-source peer inputs must match the ingestion response hashes. Historical full-source inputs are separately versioned, hash-checked, and retain their Phase 1 rule hashes; a rule change requires an explicit new extraction. Every source player must have all configured source skills. Duplicate/orphan/team-mismatched joins, source-cache integrity failures and invalid percentiles stop publication. Phase 1 columns and source identities are checked unchanged. Eligibility, per-metric denominators, no cross-season comparisons, average-tie handling, constant/sparse suppression and role independence are tested. An injected Phase 2 error occurs before promotion and preserves previous source, frozen and Phase 1 outputs. The same file transaction includes benchmark inputs and Phase 2 files, so promotion exceptions restore all prior outputs. Remote publication remains one Git commit.
