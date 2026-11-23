# Phase 1 implementation plan

Goal: publish source-preserving player and skill feature tables with documented rules and QA.
Architecture: independent features module called in refresh staging before promotion; one existing schedule.
Tech stack: Python, pandas, DuckDB, JSON/CSV configuration, pytest.
Spec: ../specs/2026-11-23-player-features-design.md

- [x] Verify source schemas, units, populations, minutes reconciliation and source per-100 semantics.
- [x] Write tests for formulas, invalid denominators, missing inputs, percentage units, classification boundaries, taxonomy, identities and source preservation.
- [x] Implement features.py, versioned thresholds and skill taxonomy; include QA summaries and rule hashes.
- [x] Stage processed outputs before source promotion; include manifest checks and workflow commit paths.
- [x] Build Parquet/CSV and processed DuckDB outputs from the current committed source tables, preserving historical file hashes.
- [x] Document all 20 features, decisions, source audit and DuckDB examples.
- [x] Run complete tests, failure-publication checks and real-data builds; verify remote files, commit and CI.

Review focus: zero possessions; anomalous fractions; missing names and identity ambiguity; unrecognized skills; failed feature QA leaving published outputs unchanged. Tests must exercise each of these.
