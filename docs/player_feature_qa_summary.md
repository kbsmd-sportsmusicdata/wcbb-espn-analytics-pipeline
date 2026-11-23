# Phase 1 QA summary

Built by the verified extended live refresh, source run `20261123T235117Z`. Historical source provenance remains the first frozen retrieval; current-season source metadata is in the processed manifest. Threshold distributions were inspected on the prior committed source revision `defc099a48845fa6af83ee51f4ec3cb898ef261e` and retained as a fixed audit reference. No frozen baseline or source-normalized metric definition was changed.

Status: **PASS_WITH_REVIEW**. 1,113 player-season rows; 23,373 player-season-skill rows; 564 historical and 549 current players, 21 skill categories each. All player/skill keys are unique and aligned; no infinite derived rates or unmapped skills.

## Evidence categories

- Small sample: 633
- Ready: 405
- Missing key metric: 57
- Identity review: 18

## Nulls and source issues

- Three out-of-range usage values become null usage_pct; original values remain unchanged.
- 56 missing assisted rates remain null assisted_rate_pct.
- One TOV% above 1 becomes null turnover_pct_display; the original source value remains unchanged.
- Eighteen player-season name variants require identity review after accent/case/punctuation normalization; these are review flags, not confirmed identity errors. No IDs were changed.
- Four missing explicit positions remain Unknown.
- No player/skill per-100 rates are null in this build.
- Early current-season records remain Small sample under the 10-game/200-minute readiness rule.

Full null counts, sample tiers, classification coverage, source lineage and output hashes are in `data/processed/manifest.json`. These are source-scoped descriptive features, not independently verified rosters or an overall ranking.
