# WCBB ESPN Analytics live ingestion design

## Intent
Maintain a reusable, quality-controlled dataset for NCAA Division I women's basketball scouting, transfer translation, Newcomer Impact × Team Execution, draft tracking, and editorial reporting. The user wants a dedicated GitHub repository and twice-weekly refreshes rather than per-project manual extraction.

## Scope
- Fixed research cohort: 25 ranked schools from the November 16, 2026 AP poll; 20 watchlist schools, including supplemental NC State. Keep North Carolina (ID 153) and NC State (ID 152) separate.
- Provider data: ESPN Analytics WCBB team Net Points, complete four-factor breakdown, BPI, player Net Points, and fingerprint skills with offensive/defensive/total source contributions.
- Freeze the first successfully fetched 2025–26 baseline. Refresh 2026–27 twice weekly at 09:15 Pacific Tuesday/Friday.
- Persist versioned Parquet snapshots, a combined DuckDB database, manifest, source URLs, SHA-256, and validation evidence. Keep all source component families distinct.

## Non-goals
- No scraping of private or authenticated feeds.
- No player impact composite, imputation, automatic name-only cross-provider join, or synchronization with SDV/salary datasets.
- No claim that calculated source-season percentiles equal ESPN's displayed percentiles.
- No guarantee of real-time data or exact-minute GitHub scheduling.

## Decisions and alternative considered
- **Preferred:** GitHub Actions + Python + DuckDB + versioned Parquet in a private repo generated from the existing sports analytics template. Fits the user's GitHub-first portability and reproducibility goals.
- **Considered:** Hex scheduled notebook, but its ephemeral local file writes do not provide a stable cross-project dataset.
- **Considered:** ChatGPT scheduled reminders, but they cannot replace a verified ingestion workflow with durable persisted files.

## Controls
- Fail closed on missing cohort IDs, duplicate grain keys, incomplete skill records, absent BPI/four factors, empty/changed source responses and unexpected roster shrinkage.
- Preserve player ID and both source team labels; discrepancy table + review status for team labels that disagree.
- Historical baseline never silently re-fetched after first successful run.
- Promote only after all QA and Parquet/DuckDB generation complete; GitHub Actions commits only on success.

## Operational constraint
The connected GitHub tool exposes repository file and branch writes but not creating a new repository from a template; this package is a reproducible overlay. The account owner must create the private repository using GitHub's 'Use this template' or authenticated GitHub CLI; then the workflows can be enabled and manually tested.
