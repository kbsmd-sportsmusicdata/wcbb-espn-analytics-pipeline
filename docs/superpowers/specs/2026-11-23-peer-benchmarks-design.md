# Phase 2 design

Use complete ESPN player/fingerprint responses as the declared reference population, including feed records outside the fixed 45-team selection. This is full provider coverage, not independently roster-verified NCAA coverage. Cohort output remains the Phase 1 selection and retains every source/Phase 1 field unchanged.

Current benchmarks use the exact ingestion responses. Historical full-source inputs are a new, separately versioned extraction with retrieval time and hashes; never relabel it as the original frozen baseline. Retain normalized full-source benchmark input tables and metadata for reproducibility without a persistent notebook or historical re-fetch on each scheduled run.

Independent position groups use Phase 1 explicit position labels. Unknown is unavailable; Hybrid is separate if sufficient. No silent position pooling. Minimum valid metric population is 30. Historical eligibility: 10 games, 200 observed minutes, 400 source possessions, matching source identities, no exposure discrepancies. Current provisional eligibility: 5 games, 100 minutes, 200 possessions. Metric missingness is applied independently; missing usage affects roles and usage benchmarks, not unrelated metrics.

Percentiles use 100*(number strictly below + (number equal + 1)/2)/n for exact reference members (average rank / n), with searchsorted implementation. Cohort observations outside reference eligibility receive no percentile. Historical cohort values are ranked only when their metric and required exposure/position/identity fields match the separately extracted historical record; otherwise suppress vintage mismatch. Current source/player matches must be exact. Roles use within-position eligible usage quantiles at .33/.67, calculated independently from target metrics; collapsed cutoffs yield Typical usage only.

Only positive modeled contributions with explicitly mapped source meaning and valid >=75th percentile evidence receive overlapping function candidates. They remain film-review leads, not verified skill strengths. Ambiguous or negative high percentiles receive statistical-distinction labels, not strength tags. No combined score or archetype.

Alternative: selected-cohort benchmarks were rejected because they violate the requested universe. Separate schedules were rejected because they risk mismatched source vintages. Extend the existing staged publication transaction; all Phase 2 QA/export work precedes promotion. Deliver three linked Parquet/CSV tables, independent DuckDB, dictionary, configuration, provenance, QA and SQL examples.
