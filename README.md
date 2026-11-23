# ESPN Analytics WCBB — Data Ingestion Pipeline

Reproducible ingestion and quality gates for ESPN Analytics public college women's basketball team and player data. Uses the user's **[`template-sports-analytics`](https://github.com/kbsmd-sportsmusicdata/template-sports-analytics)** repository structure.

**Cohort:** 45 distinct schools: AP Top 25 as of November 16, 2026 plus 20 watchlist schools. North Carolina **153** and NC State **152** are distinct members. The reference list is versioned in [`data/reference/cohort_45.csv`](data/reference/cohort_45.csv); AP cohort labels are frozen.

**Source seasons:** API `2025` = academic 2025–26 (baseline, frozen at initial successful run); API `2026` = academic 2026–27 (partial season, refreshed). 

## Two DuckDB families

| Schema | Tables | Model components |
|---|---|---|
| `wcbb_espn_team_netpoints` | `team_season`, `four_factors`, `bpi`, `unkeyed_team_stats` | Team offensive/defensive/total Net Points, original 4-factor sides and conventional team factors, BPI offense/defense/total and ranks |
| `wcbb_espn_player_fingerprints` | `player_season`, `skill_impacts`, `team_id_discrepancies` | Player Net Points, ESPN IDs and team labels, original fingerprint skills (off/def/total), computed descriptive percentiles, source conflicts |

Tables are also exported as **Parquet**, with the latest normalized data in `data/latest/<schema>/<table>.parquet`. The combined database is `data/latest/wcbb_espn_data_families.duckdb`. An initial successful run creates `data/frozen/season=2025/`, and each successful current-season run creates `data/snapshots/<UTC timestamp>/season=2026/` plus a QA `manifest.json`.

## Scheduling

`.github/workflows/refresh_wcbb.yml` schedules refreshes **Tuesday and Friday at 9:15 a.m. America/Los_Angeles**, accounting for DST. It can also be run manually with **Actions > ESPN Analytics WCBB — validated refresh > Run workflow**. GitHub Actions runner fetches provider JSON, checks keys, validates 45 team IDs and player identities, rebuilds DuckDB/Parquet and commits only after critical QA passes. Failed runs leave the last committed snapshot unchanged. GitHub scheduling is best-effort, not guaranteed exactly on the minute.

The cron does **not run until this workflow is present in the NEW repository's default branch**. This package by itself does not enable remote automation.

## Repository creation

1. Generate a new **private** repository from [the sports analytics template](https://github.com/kbsmd-sportsmusicdata/template-sports-analytics/generate) under `kbsmd-sportsmusicdata`, suggested name `wcbb-espn-analytics-pipeline`.
2. Clone it to your Mac and copy the files of this overlay archive into the repository root (overwriting matching placeholders). `git add . && git commit -m 'Install WCBB pipeline' && git push`.
3. Enable Actions if prompted, manually run the refresh workflow, and confirm the QA manifest and outputs in the newly created repository. This initial run also fetches/fixes the historical 2025–26 baseline.

**CLI alternative:** From the extracted overlay folder's parent directory, run `bash wcbb_espn_repo_overlay/scripts/create_repo_from_template.sh`. Requires the `gh` CLI authenticated (`gh auth login`), and creates the private repository and pushes the overlay. If the repository exists already, it refuses to modify it.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src pytest -q
python scripts/refresh_wcbb.py --season 2026
python scripts/check_manifest.py
```

The Python pipeline needs internet to reach ESPN Analytics. The workspace that produced the original 45-team validation exported CSVs but did not provide an accessible complete skill-level CSV here; the first repository refresh reconstructs those skills from the live endpoint. Previously downloaded CSVs are **not automatically treated as live results**. The original Hex 45-team QA report is retained in `reports/hex_45_team_validation_reference_2026-11-23.csv` for source-drift comparisons. Do **not** run the inherited template `scripts/generate_readme.py` after customization: it would replace this ingestion README with a portfolio template.

## Reproducibility and QA

All provider source URLs, retrieval timestamps, raw SHA-256 hashes, sample counts and join exceptions are stored in `reports/manifest_latest.json`, and each snapshot includes its own manifest. Missing team IDs outside the cohort remain excluded from *cohort* tables; see [QA documentation](docs/QA_GATES.md). Player/team source disagreements are preserved as a separate table and reported as `PASS_WITH_REVIEW` rather than silently corrected.

**Data rights:** Provider feeds are public to view, but licensing/republication terms have not been verified. Keep this repository **private** until you determine which portions you may distribute publicly. Don't use ESPN-sourced metrics as a substitute for independently validated game-level records or mix them with SDV/RAPM models without explicit labels.
