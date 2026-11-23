# Methodology

## Sources and season mapping

The public ESPN Analytics routes `/api/team-data?league=wcbb&season=YYYY` and `/api/fingerprint-data?league=wcbb&season=YYYY` supply the metrics. API 2025 means academic 2025–26; API 2026 means 2026–27. Full URLs, response SHA-256 hashes, byte counts, and UTC retrieval times accompany each season in the manifest.

Team tables may arrive as JSON strings containing column-indexed objects. The parser aligns cells by source row identifier and rejects inconsistent or empty tables. Fingerprints are keyed by player ID.

## Identity and transformations

The versioned cohort is `data/reference/cohort_45.csv`. Join team statistics using `digital_team_id` and player/BPI records using ESPN `TEAM_ID`; never substitute the separate `tmID` field. Export the original `TEAM_ID` as `source_team_id` and its numeric join key as `team_id` to avoid DuckDB identifier collisions.

Team Net Points retain the provider's Offense, Defense, and Total values. Skill impacts retain original offense, defense, and total values. Descriptive skill percentiles use average-tie `rank(pct=True) * 100` over the full source feed for each skill, component, and season before filtering to the cohort. They are not official ESPN percentiles.

## Publication and baseline provenance

All required source collection, QA, Parquet export, and database construction complete in staging before promotion. GitHub commits the results only after the manifest check succeeds. Failed QA leaves the prior remote snapshot intact.

The first successful refresh freezes 2025–26 under `data/frozen/season=2025/`. `provenance.json` beside those tables retains the original baseline source hashes and retrieval time. Existing installations recover these details from a snapshot manifest whose historical retrieval time matches the frozen table. If no valid record matches, the refresh stops rather than inventing provenance or fetching a replacement baseline.

Later runs revalidate the frozen tables, carry their original provenance into each new manifest, and fetch only 2026–27. They preserve the historical Parquet files byte for byte. Parquet reloads use explicit season columns, without inferring additional fields from directory names.

## Limits

These are provider metrics, not an independent game-level model or roster audit. The current season is partial, source values can change, and redistribution terms have not been independently verified. See [QA rules](QA_GATES.md) for coverage, arithmetic tolerances, and source exceptions.
