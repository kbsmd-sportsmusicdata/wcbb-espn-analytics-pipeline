# Phase 1 player feature dictionary

The machine-readable dictionary is [`player_feature_dictionary_v1.csv`](../data/reference/player_feature_dictionary_v1.csv). Thresholds are in [`player_feature_rules_v1.json`](../data/reference/player_feature_rules_v1.json); skill mappings are in [`skill_taxonomy_v1.csv`](../data/reference/skill_taxonomy_v1.csv).

## fingerprint_impact_off_per100

- **definition:** Accumulated fingerprint off contribution normalized by source possessions.
- **formula rule:** 100 * fingerprint_off_raw / fingerprint_possessions
- **units:** Contribution units per 100 ESPN source possessions
- **source columns:** fingerprint_off_raw; fingerprint_possessions
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Positive possession denominator for rates; finite derived values; no source-column changes.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## fingerprint_impact_def_per100

- **definition:** Accumulated fingerprint def contribution normalized by source possessions.
- **formula rule:** 100 * fingerprint_def_raw / fingerprint_possessions
- **units:** Contribution units per 100 ESPN source possessions
- **source columns:** fingerprint_def_raw; fingerprint_possessions
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Positive possession denominator for rates; finite derived values; no source-column changes.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## fingerprint_impact_total_per100

- **definition:** Accumulated fingerprint total contribution normalized by source possessions.
- **formula rule:** 100 * fingerprint_total_raw / fingerprint_possessions
- **units:** Contribution units per 100 ESPN source possessions
- **source columns:** fingerprint_total_raw; fingerprint_possessions
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Positive possession denominator for rates; finite derived values; no source-column changes.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## minutes_total_est

- **definition:** Estimated season minutes; separate from observed fingerprint_minutes.
- **formula rule:** MIN_PLAYED * GAMES_PLAYED
- **units:** Estimated minutes
- **source columns:** MIN_PLAYED; GAMES_PLAYED
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Inputs >=0; games must be integer; difference >1 minute from fingerprint_minutes is flagged.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## minutes_share_est

- **definition:** Regulation-minute playing-time estimate; not share of all team minutes.
- **formula rule:** MIN_PLAYED / 40
- **units:** Fraction of one 40-minute regulation game
- **source columns:** MIN_PLAYED
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Nonnegative; can exceed 1 in overtime; no clipping.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## usage_pct

- **definition:** Fingerprint usage displayed on a percentage scale.
- **formula rule:** 100 * fingerprint_usage only if 0 <= source <= 1
- **units:** Percentage (0–100)
- **source columns:** fingerprint_usage
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Native fractional scale verified; out-of-range values stay in original column, derived display null and flagged. No automatic per-row scale inference.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## assisted_rate_pct

- **definition:** Fingerprint assisted rate displayed on a percentage scale.
- **formula rule:** 100 * fingerprint_assisted_rate only if 0 <= source <= 1
- **units:** Percentage (0–100)
- **source columns:** fingerprint_assisted_rate
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Native fractional scale verified; out-of-range values stay in original column, derived display null and flagged. No automatic per-row scale inference.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## turnover_pct_display

- **definition:** Source turnover ratio displayed on a percentage scale.
- **formula rule:** 100 * TOV% only if 0 <= source <= 1
- **units:** Percentage (0–100)
- **source columns:** TOV%
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Native fractional scale verified; out-of-range values stay in original column, derived display null and flagged. No automatic per-row scale inference.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## position_group

- **definition:** Broad explicit source roster position.
- **formula rule:** Versioned position_mapping: G/PG/SG Guard; SF/W Wing; F/PF Forward; C Center; G/F,F/C,G-F,F-C Hybrid; otherwise Unknown.
- **units:** Category
- **source columns:** POSITION
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Unknown for missing/unrecognized source position. AVG_POSITION retained, not used to invent a roster position.
- **validation thresholds:** Only configured categories; no archetype inference.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## minutes_sample_tier

- **definition:** Descriptive exposure category.
- **formula rule:** [0,50) Very small; [50,200) Small; [200,500) Developing; >=500 Established
- **units:** Category
- **source columns:** fingerprint_minutes
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Unknown for missing, nonfinite or negative input; games must be integer.
- **validation thresholds:** Configured fixed thresholds; not calibrated evaluation benchmarks.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## games_sample_tier

- **definition:** Descriptive exposure category.
- **formula rule:** [0,3) Very small; [3,10) Small; [10,20) Developing; >=20 Established
- **units:** Category
- **source columns:** GAMES_PLAYED
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Unknown for missing, nonfinite or negative input; games must be integer.
- **validation thresholds:** Configured fixed thresholds; not calibrated evaluation benchmarks.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## playing_time_tier

- **definition:** Descriptive exposure category.
- **formula rule:** [0,6) Minimal; [6,16) Limited rotation; [16,28) Regular rotation; >=28 Rotation anchor
- **units:** Category
- **source columns:** MIN_PLAYED
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Unknown for missing, nonfinite or negative input; games must be integer.
- **validation thresholds:** Configured fixed thresholds; not calibrated evaluation benchmarks.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## creation_context

- **definition:** Assisted-scoring context; does not measure passing ability.
- **formula rule:** With >=50 observed minutes, >=3 games and >=100 possessions: assisted rate <=0.4 More self-created; >=0.7 Mostly assisted; otherwise Mixed.
- **units:** Category
- **source columns:** fingerprint_assisted_rate; fingerprint_minutes; GAMES_PLAYED; fingerprint_possessions
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Unknown if evidence or fraction is inadequate.
- **validation thresholds:** Valid assisted fraction 0–1; context exposure thresholds required.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## impact_balance

- **definition:** Relative component magnitude, not a quality score.
- **formula rule:** With context exposure and finite components: opposite signs Mixed-sign; abs(off-def) <=0.2*(abs(off)+abs(def)) Balanced; otherwise larger abs component sets leaning. Both zero Balanced.
- **units:** Category
- **source columns:** fingerprint_off_raw; fingerprint_def_raw; fingerprint_minutes; GAMES_PLAYED; fingerprint_possessions
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Unknown if component/exposure evidence inadequate.
- **validation thresholds:** Offensive-leaning and Defensive-leaning refer to magnitude, including negative impacts; no composite score.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## identity_consistency_status

- **definition:** Review signal for linked source identities.
- **formula rule:** Agreement if canonical team_id equals fingerprint_team_id and nonempty names match after Unicode accent/punctuation/case normalization; else Review required.
- **units:** Category
- **source columns:** team_id; fingerprint_team_id; DISPLAY_NAME; fingerprint_player_name
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Missing identity evidence requires review; IDs never reassigned.
- **validation thresholds:** Conservative nickname/truncation variants require human review even when player ID joins agree.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## evidence_status

- **definition:** Readiness of descriptive evidence, not player quality.
- **formula rule:** Priority: Identity review; then Missing key metric for missing/invalid rates, percentages, games/minutes or exposure reconciliation flags; then Small sample if observed minutes <200 OR games <10; otherwise Ready.
- **units:** Category
- **source columns:** Derived rates; exposure; source percentage inputs; identity status
- **grain:** Player-season
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Missing key metric or Identity review; never filled to Ready.
- **validation thresholds:** Current season can remain Small sample throughout early season. No additional benchmark comparison implied.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## skill_impact_off_per100

- **definition:** Normalized source skill off contribution.
- **formula rule:** 100 * impact_off_raw / source_possessions
- **units:** Contribution units per 100 ESPN source possessions
- **source columns:** impact_off_raw; source_possessions
- **grain:** Player-season-skill
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Positive possession denominator for rates; finite derived values; no source-column changes.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## skill_impact_def_per100

- **definition:** Normalized source skill def contribution.
- **formula rule:** 100 * impact_def_raw / source_possessions
- **units:** Contribution units per 100 ESPN source possessions
- **source columns:** impact_def_raw; source_possessions
- **grain:** Player-season-skill
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Positive possession denominator for rates; finite derived values; no source-column changes.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## skill_impact_total_per100

- **definition:** Normalized source skill total contribution.
- **formula rule:** 100 * impact_total_raw / source_possessions
- **units:** Contribution units per 100 ESPN source possessions
- **source columns:** impact_total_raw; source_possessions
- **grain:** Player-season-skill
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** Null when a required numeric input is missing, nonfinite or invalid.
- **validation thresholds:** Positive possession denominator for rates; finite derived values; no source-column changes.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## functional_skill_group

- **definition:** Broad descriptive grouping of source skill names.
- **formula rule:** Exact skill lookup in data/reference/skill_taxonomy_v1.csv.
- **units:** Category
- **source columns:** skill
- **grain:** Player-season-skill
- **comparison population:** Pointwise calculation on fixed 45-team cohort; no league ranking
- **missing value behavior:** A new or unmapped source skill stops publication until the mapping is reviewed.
- **validation thresholds:** 21 observed skills; unique mapping per skill; original offense/defense/total retained. Skills overlap; group totals must not be summed into an evaluation score.
- **provenance:** Independently derived phase1_v1; not an official ESPN rating

## Interpretation and source verification

The [ESPN WCBB fingerprint page](https://www.espnanalytics.com/wcbb-fingerprint) describes per-100 skill views. This project independently normalizes accumulated raw fingerprint contributions by `tPoss`; it does not reproduce or certify ESPN website ratings, adjustments, qualifications, percentiles or display methodology. `ONETPTS`, `DNETPTS`, and `TNETPTS` are preserved separately: in these feeds they reconcile to accumulated fingerprint contributions divided by games, not source possessions.

On the pinned source revision, `MIN_PLAYED * GAMES_PLAYED` differs from observed fingerprint minutes by at most 0.684 minutes due to source display precision. Native usage, assisted rate, and TOV% are fractional inputs. Invalid negative usage and TOV% >1 are preserved and flagged; their derived displays are null. Full-source skill percentiles and denominators remain unchanged and describe original raw skill contributions, not these new per-100 rates. No ranks are recalculated within the 45 teams.

Threshold rationale: source-cohort median minutes are approximately 526 in 2025 and 103 in 2026; median appearances are 31 and 6. Fixed exposure bands distinguish early/limited evidence from sustained participation. Rotation cutoffs 6/16/28 minutes bracket minimal, lower-rotation, normal-rotation and high-minute participation; the observed upper quartile is roughly 27/25 minutes. Assisted 40%/70% and balance tolerance 20% are transparent descriptive choices, not externally validated scouting cutoffs. Position groups use explicit source labels; four missing roster positions remain Unknown rather than inferred from average position.

Extra metadata includes `feature_version`, `analysis_population`, `derived_rate_model`, `season_status`, and `feature_qa_flags`. The processed manifest links source retrieval times/hashes and rule hashes to the source run. Source columns (including actual minutes and position inputs) remain intact.

Publication copy errors trigger rollback of all replaced source and processed files, including latest manifests. Prior snapshots are not recopied for rollback. GitHub additionally publishes each successful run in one Git commit. Abrupt machine termination outside Python exception handling is not an atomic local filesystem transaction; the prior remote Git commit remains authoritative. The turnover skill is labeled Possession management / defensive activity because both offensive costs and defensive gains are present.
