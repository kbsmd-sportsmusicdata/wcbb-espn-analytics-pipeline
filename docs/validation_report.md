# Validation status and evidence

The authoritative current report is [`reports/manifest_latest.json`](../reports/manifest_latest.json). Each successful refresh also stores `data/snapshots/<run_id>/manifest.json`. The manifest and output files are checked by `python scripts/check_manifest.py`.

The first successful remote refresh was [run 45264173644](https://github.com/kbsmd-sportsmusicdata/wcbb-espn-analytics-pipeline/actions/runs/45264173644), on November 23, 2026. It published:

| API season | Teams | Players | Skill rows | BPI rows | Status |
|---|---:|---:|---:|---:|---|
| 2025 | 45 | 564 | 11,844 | 45 | PASS |
| 2026 | 45 | 549 | 11,529 | 45 | PASS |

No cohort player/fingerprint team-ID disagreements were found. Ten current-season source team-stat rows lacked usable IDs and were quarantined outside the cohort tables. The current player count was one above the earlier Hex reference; that reference is a comparison point, not a fixed live count.

The regression suite covers parsing, IDs, cohort coverage, source exceptions, Parquet reloads, and baseline-provenance recovery and reuse. Run `PYTHONPATH=src python -m pytest -q tests` for the current results.

The inherited `scripts/validate_data.py` and `reports/validation_summary.*` concern generic configured-file checks. They do not certify live ESPN ingestion. Independent roster verification has not been performed. See [QA rules](QA_GATES.md).
