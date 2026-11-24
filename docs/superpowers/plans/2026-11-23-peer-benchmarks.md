# Phase 2 implementation plan

Goal: full-source, evidence-qualified position/role/skill benchmarks for the unchanged 45-team output.
Spec: ../specs/2026-11-23-peer-benchmarks-design.md
Architecture: full_source.py captures peer inputs; peers.py builds distributions and joins; existing staged refresh publishes Phase 1 and 2 atomically with rollback.

- [x] Inspect full-source distributions, units, eligibility and position coverage.
- [x] Add failing tests for universe selection, ties, no leakage, per-metric n, roles, suppression, direction, source vintage mismatch and source preservation.
- [x] Implement full-source input extraction plus separately versioned historical cache, metadata and integrity hashes.
- [x] Implement configured position/role/skill reference distributions and overlapping function candidates.
- [x] Extend staging, manifest checks and existing workflow commit paths, preserving rollback on any failure.
- [x] Build all three datasets and independently query representative positions and seasons.
- [x] Document definitions, coverage, limitations and coaching vs exploratory use; review, test, push and verify CI.

Review focus: cohort accidentally used as universe; historical source drift; sparse positions/metrics; constant/tied distributions; role circularity; negative or ambiguous contributions; interrupted publication.
