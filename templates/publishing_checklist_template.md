# Refresh acceptance checklist

## Before changing ingestion

- Run `PYTHONPATH=src python -m pytest -q tests`.
- Check cohort identity, source-season mapping, and output keys.
- Preserve frozen historical tables and their original source provenance.
- Review changes to QA tolerances or source exceptions explicitly.

## After a GitHub refresh

- Confirm the Actions run succeeds through the data commit step.
- Confirm `reports/manifest_latest.json` has PASS or PASS_WITH_REVIEW.
- Confirm both seasons contain all 45 cohort team IDs and all expected tables.
- Review player-ID changes, discrepancy rows, and reference-count deltas.
- Confirm frozen 2025–26 hashes/retrieval time remain original.
- Check the snapshot manifest and combined DuckDB/Parquet outputs.

## Operational follow-up

- Observe the first Tuesday/Friday scheduled execution.
- Review GitHub failure notifications according to the account's preferences.
- Connect downstream analyses only after checking source scope and freshness.

This checklist covers data publication through GitHub commits. The manual-only Pages workflow is a notice; it does not deploy a website.
