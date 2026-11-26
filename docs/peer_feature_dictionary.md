# Phase 2 benchmark dictionary and interpretation

The machine-readable [feature dictionary](../data/reference/peer_feature_dictionary_v1.csv) gives every added metric's formula, units, inputs, grain, population, missing behavior, thresholds and provenance. The [versioned configuration](../data/reference/peer_benchmark_rules_v1.json) defines eligibility, percentile methods, usage quantiles, sparse-group rules and candidate functions.

## What the percentiles mean

All percentiles ascend with the metric. High turnover is more turnovers, not better ball security. High usage is more usage, not a quality rating. Assisted rate describes creation context. FTR is a ratio and can legitimately exceed 1. Source EFG uses a percentage scale and can reach 150 mathematically; it is not multiplied by 100 again. AST_40 and REB_40 retain the provider's per-40 labels, but their exact denominators were not independently verified; use those comparisons descriptively and confirm the source definition before coaching claims.

Full-source reference populations are distinct from the 45 selected teams. All observations in the provider player feed are considered; NCAA division membership and roster coverage are not independently certified. Source/player-ID and full fingerprint coverage checks guard the extraction. Eligibility uses observed minutes, appearances and source possessions; Phase 1 missing metrics are assessed separately for each benchmark rather than discarding a player from unrelated comparisons.

The statistic is 100 * average tied rank / n among exact eligible reference members. Minimum-peer suppression uses each metric's valid n, not a general position count. Constant distributions are unavailable. Quantiles use linear interpolation. Positions remain separate; Unknown is unavailable and Hybrid is never silently pooled. Role bands use independent eligible same-position usage quantiles at .33/.67; usage percentiles always use position peers, not usage-selected peers. Collapsed cutoffs yield Typical usage rather than fabricated distinctions.

## Source vintages and evidence

The full historical benchmark population is a new versioned extraction under `data/benchmarks/historical/`, with separate hashes and retrieval time. It is not the original frozen baseline. The original selected historical data is preserved; if its metric or required identity/exposure context differs from this newer reference vintage, that metric's comparison is suppressed. Current benchmarks use the exact JSON response bytes used by the ingestion job, verified against the source QA hashes.

Historical eligibility is at least 10 games, 200 observed minutes and 400 source possessions. Current provisional eligibility is 5 games, 100 minutes and 200 possessions. Initial exposure-only feed counts were approximately 2,090/960/149 historical guards/forwards/centers and 1,280/475/60 current peers, before identity and metric filters. Those counts support a minimum n of 30 but do not guarantee role-group sufficiency. Current center usage bands may be suppressed. These are transparent operational evidence choices, not calibrated predictive reliability thresholds.

## Functional candidates, not verified skills

Only configured source skill/components with positive modeled Net Points contribution and a valid position percentile >=75 receive function candidates. Labels can overlap and may be empty. Evidence preserves component, contribution, percentile, n and provisional status. Negative or semantically unmapped high percentiles receive a statistical-distinction label only. A low-cost negative turnover contribution is not forced into a strength. Skills overlap; never sum them into a function score or overall ranking.

The component-specific map keeps offensive shooting/finishing/passing, offensive or total rebound/second-chance activity, defensive turnover creation and offensive transition separate. No positions, player archetypes, draft eligibility or WNBA role projections are inferred.

## Reusable tables

`data/processed/phase2/player_peer_features.parquet`: player-season, all Phase 1 columns unchanged plus new comparisons and evidence.

`data/processed/phase2/player_skill_peer_features.parquet`: player-season-skill, both the existing raw-impact full-source percentiles and the independent per-100 position percentiles retained.

`data/processed/phase2/peer_benchmark_reference.parquet`: unique API season × comparison kind × comparison group × metric. Includes unit/direction, exact valid n, exposure-eligible n, minimum exposure JSON, median, q10/q25/q50/q75/q90, status/validity, usage cutoffs, percentile and tie method, configuration version, declared population, source hashes, source retrieval time, source reference ID and publication snapshot ID.

CSV counterparts and `peer_features.duckdb` contain the same three tables. Per-season copies are under `season=2025` and `season=2026`; source-run snapshots use the existing processed snapshot path. `manifest.json` records rule/output hashes, populations, suppression coverage, identities and cautions. Full-source normalized inputs are retained separately for reproducibility.

## Appropriate use

- **Ready for descriptive scouting:** source/Phase 1 metrics, exact counts, position/role membership, available historical statistical percentiles and the provenance-rich reference table, subject to visible metric cautions.
- **Exploratory:** current provisional percentiles, usage-based responsibility bands, AST_40/REB_40 source-label comparisons and overlapping model-based function candidates.
- **Requires independent game or film validation:** actual defensive assignments, shooting portability, decision-making, role fulfillment, NCAA roster status, opponent context and WNBA fit. No breakout, transfer-change or draft projection is claimed.

## Full-population discovery outputs and stable inputs

The existing Phase 2 cohort outputs and benchmark rules are unchanged. Stable input aliases are byte-identical to the versioned sources:

- `data/benchmarks/latest/season=2025/players.parquet` and `skills.parquet`
- `data/benchmarks/latest/season=2026/players.parquet` and `skills.parquet`
- `data/benchmarks/latest/manifest.json`: source run, vintage, counts, reference IDs and input hashes.

Full-population Phase 2 peer outputs are published as Parquet only to avoid large CSV duplication:

- `data/processed/phase2/full_population/season=2025/player_peer_features.parquet` and `player_skill_peer_features.parquet`
- `data/processed/phase2/full_population/season=2026/player_peer_features.parquet` and `player_skill_peer_features.parquet`

They use the same position/role/skill distributions, cutoffs, eligibility, metric-specific denominators, tie rules and candidate tags as the selected 45-team outputs. All reference observations are retained, including ineligible ones with suppressed comparisons. `in_cohort_45` is a boolean for membership of the source team ID in the fixed cohort; `peer_output_population` identifies the provider-wide output, and `peer_source_run_id` identifies the publishing run. Historical full-population rows reflect the separately versioned historical extraction, not the frozen selected-cohort source. Current comparisons remain provisional. Provider-wide coverage is not independently certified NCAA Division I coverage.

The Phase 2 manifest records per-season row counts, outside-cohort counts, eligible counts and full-output hashes. Existing benchmark reference tables apply to both populations. The normal scheduled refresh publishes all files only after validation, with rollback protection. Stable input aliases are initially seeded from the already published snapshots; full peer outputs require the first successful refresh with the new code.
