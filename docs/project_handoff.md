# Project handoff

## Current state

The repository is operational: the first manual GitHub refresh published validated DuckDB and Parquet outputs on November 23, 2026. The first scheduled execution remains to be observed. GitHub Pages publication is disabled for this data pipeline.

## Run and inspect

1. Open Actions → ESPN Analytics WCBB — validated refresh → Run workflow on `main`.
2. Confirm that source fetching, manifest verification, and the data commit succeed.
3. Inspect `reports/manifest_latest.json` and the matching dated snapshot.
4. Use `data/latest/wcbb_espn_data_families.duckdb` or the Parquet tables under `data/latest/`.

The schedule is Tuesday and Friday at 9:15 a.m. America/Los_Angeles. Scheduling is best effort. The historical 2025–26 baseline is frozen; only 2026–27 is downloaded on subsequent refreshes.

## Maintenance commands

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m pytest -q tests
python scripts/refresh_wcbb.py --season 2026
python scripts/check_manifest.py
```

`generate_docs.py` and `generate_readme.py` regenerate this repository's pipeline documentation from its customized templates. The original sports analytics template repository is separate and unchanged.

## Recovery and limitations

A missing baseline `provenance.json` is recovered from matching committed snapshot metadata on the next successful refresh. Missing or mismatched provenance stops the job. Do not delete frozen tables to force a refetch; historical corrections require a separately reviewed backfill.

Use the most recent passing manifest to assess freshness after failures. Current-season metrics can change. Cohort AP labels remain fixed to November 16. Provider redistribution terms and independent roster availability are not verified; repository visibility is managed separately.
