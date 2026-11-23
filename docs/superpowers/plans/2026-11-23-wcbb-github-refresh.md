# WCBB ESPN Analytics ingestion — implementation plan

## Objective
Create a dedicated private repository from the existing sports-analytics GitHub template, ingest 2025–26 historical and 2026–27 live WCBB ESPN Analytics models for a fixed cohort of 45 schools, validate source continuity, and publish versioned Parquet and DuckDB tables twice a week.

## Evidence and constraints
- The user's GitHub account `kbsmd-sportsmusicdata` owns an actual template repository, `template-sports-analytics`, with `scripts`, `docs`, `data`, `tests` and `.github/workflows`.
- The connected GitHub tool can modify existing repositories but does **not** expose repository-creation/template-generation actions; new remote repository must be created via GitHub's `Use this template` UI or authenticated `gh repo create` from the user's Mac.
- The validated cohort reference CSV has 45 unique ESPN team IDs; North Carolina 153 is AP No. 24, NC State 152 is supplemental watchlist.
- ESPN Analytics public source fingerprints expose raw impacts. Descriptive within-skill percentiles must be labeled as **computed**.
- Do not automatically publish complete provider data publicly until redistribution terms are checked.

## Delivery decisions
1. Preserve original template structure but replace project metadata and workflows to prevent automatic Pages deployment.
2. New repo proposed name: `wcbb-espn-analytics-pipeline`, visibility private by default.
3. Two distinct DuckDB schemas and five principal model tables plus discrepancy evidence.
4. Python ingestion code with offline synthetic tests and fail-closed QA gates. Source downloads use GET and retry transient errors.
5. First successful run fetches both `season=2025` and `season=2026`, freezes historical baseline. Later runs refresh only `season=2026`.
6. GitHub Actions schedule: Tuesday and Friday at 09:15 America/Los_Angeles, with manual run fallback.
7. Source data and model snapshot files are promoted only after QA. GitHub commits and pushes only on successful completion.
8. The package is a local overlay until the new repo exists. A one-command authenticated `gh` script is supplied; no claim of remote enabling until the first workflow run is verified.

## Verification gates
- `PYTHONPATH=src pytest -q`: cohort integrity, schema parsing, skill-percentile population, duplicate and missing source cases, team-ID mismatch preservation, QA report counts.
- `python -m compileall -q src scripts`
- Workflow YAML parse and exact schedule assertion.
- After remote creation: **manually** run Actions refresh, verify run status, `reports/manifest_latest.json`, historical frozen outputs, latest source-season outputs, DuckDB database and family row keys.

## Next phase
After initial remote run succeeds, connect the published Parquet files to Newcomer Impact × Team Execution, transfer translation and draft tracker. Monitor source changes/QA in Actions; do not silently backfill or rewrite frozen historic snapshots.
