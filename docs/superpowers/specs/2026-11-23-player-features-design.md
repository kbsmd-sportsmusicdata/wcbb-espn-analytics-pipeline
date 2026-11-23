# Phase 1 processed player features

Implement the user's supplied 20-feature specification in a separate processed layer. Keep original player and skill columns unchanged. Use accumulated fingerprint contributions / positive source possessions * 100; retain model labels and source metrics. Percentage displays convert verified fractional inputs, with invalid values left null and reported. Position groups use explicit roster positions; no inferred archetypes.

Use version-controlled JSON thresholds and a CSV mapping all observed skills. Fixed thresholds are descriptive operational choices informed by both source-season distributions, not calibrated scouting benchmarks. Preserve missingness, distinguish inadequate sample from zero impact, and flag source identity/name disagreements for review.

The existing refresh stages source tables, then processed calculations and critical feature QA, then Parquet/CSV, a separate processed DuckDB database and the updated manifest. Publish latest, per-season and snapshot copies only after all staging succeeds. Never modify source-normalized or frozen historical tables to add features. Source hashes and retrieval times remain linked to each season through the processed manifest.

Alternatives considered: a separate scheduled feature pipeline risks revision mismatch; calculations in downstream projects duplicate rules. A single module within existing refresh staging keeps one source revision and publication gate. No composite score, role translation, benchmarks or expanded archetypes.
