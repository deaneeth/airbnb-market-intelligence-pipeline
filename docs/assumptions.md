# Assumptions

This file records every assumption made about ambiguous fields, data quality decisions,
and analytical choices. Entries are added as decisions are made during development.

---

## Format

Each entry follows this structure:

```
### [YYYY-MM-DD] Short title

- **Component**: affected module or notebook
- **Assumption**: what is assumed
- **Rationale**: why this choice over alternatives
- **Consequence**: which outputs or claims depend on this
- **Alternative considered**: other interpretation and why it was rejected
```

---

## Entries

### [2026-07-11] Snapshot semantics

- **Component**: ingestion, all downstream modules
- **Assumption**: The Inside Airbnb dataset is a point-in-time scrape. All analysis describes
  conditions at the snapshot date (2026-06-15), not current or historical market conditions.
- **Rationale**: Inside Airbnb documentation states data is collected on a single scrape date.
  No longitudinal inference is possible from a single snapshot.
- **Consequence**: Every report finding is scoped to "Amsterdam, snapshot 2026-06-15".
  Time-series or trend claims are not made.
- **Alternative considered**: Treat data as representative of "current" conditions.
  Rejected because scrape lag and seasonal effects are not measurable from one snapshot.

### [2026-07-11] Availability rate as occupancy proxy

- **Component**: cleaning, enrichment, statistics, reporting
- **Assumption**: `occupancy_proxy = 1 - availability_rate`, where `availability_rate` is
  the share of days in the calendar file marked available by the host. This is used as a
  proxy for booking density, not confirmed occupancy.
- **Rationale**: Actual booking confirmations are not available in the Inside Airbnb dataset.
  The calendar file records host-set availability, which is the closest observable signal.
- **Consequence**: Every use of `occupancy_proxy` in output tables, captions, and report text
  carries the caveat: "Derived from host-set availability; not equivalent to confirmed booked nights."
- **Alternative considered**: Use reviews per month as a demand proxy exclusively.
  Both measures are used; neither is labelled as confirmed occupancy.

### [2026-07-11] Professional host definition

- **Component**: enrichment, statistics
- **Assumption**: A host with 2 or more active listings in the snapshot is classified as
  "professional". A host with exactly 1 listing is classified as "casual".
- **Rationale**: This threshold is commonly used in short-term rental research. It distinguishes
  hosts who may be operating commercially from those subletting a single property.
- **Consequence**: The `host_segment` column takes values "casual" or "professional". All
  comparative analyses between segments use this binary classification.
- **Alternative considered**: Use 3+ listings as the professional threshold. Rejected to align
  with the more common convention; documented here for reviewer transparency.

### [2026-07-11] Minimum neighbourhood sample size

- **Component**: enrichment, statistics, EDA
- **Assumption**: Neighbourhoods with fewer than 15 listings are excluded from comparative
  statistical analyses. They are retained in the master table and map visualisations.
- **Rationale**: Small samples produce unstable estimates. 15 is a conservative lower bound
  that retains analytical power without making claims from single-digit samples.
- **Consequence**: Neighbourhood-level analyses state "N >= 15 listings" in every caption.
- **Alternative considered**: Use 10 as the threshold. Rejected as too low for reliable median
  price estimates given the right-skew of the price distribution.

### [2026-07-11] City centre reference coordinates for Amsterdam

- **Component**: enrichment
- **Assumption**: The city centre is defined as Dam Square, Amsterdam:
  latitude 52.37310, longitude 4.89319.
- **Rationale**: Dam Square is the historical and geographic centre of Amsterdam and is
  commonly used as the reference point in urban economics research on the city.
- **Consequence**: `distance_to_centre_km` is the Haversine distance from each listing to
  this coordinate. The choice of reference point affects which listings are classified as
  "central" in the OLS model.
- **Alternative considered**: Use the centroid of all listing coordinates. Rejected because
  the centroid shifts with the listing distribution and is not geographically meaningful.

### [2026-07-11] Price currency symbol handling

- **Component**: cleaning, data dictionary
- **Assumption**: The `$` symbol in exported price fields is treated as a formatting artifact,
  not evidence that Amsterdam prices are denominated in USD.
- **Rationale**: The official Inside Airbnb data dictionary says the dollar sign is a technical
  artifact of the export. The Amsterdam quote payloads also identify `EUR` where currency is
  present.
- **Consequence**: Price parsing will strip currency symbols and separators before storing
  numeric price values. Report text will avoid USD wording unless a later source explicitly
  proves currency conversion.
- **Alternative considered**: Treat `$` as USD. Rejected because that would contradict the
  official dictionary and misstate Amsterdam prices.

### [2026-07-11] Host response fields unavailable in Amsterdam snapshot

- **Component**: data dictionary, validation, enrichment
- **Assumption**: `host_response_time`, `host_response_rate`, and `host_acceptance_rate`
  are documented as source fields but are not used for dataset discovery because the Amsterdam
  detailed listings snapshot has 100.00% nulls for each field.
- **Rationale**: A field with complete missingness cannot support a defensible comparison or
  feature without external imputation, which is outside the current scope.
- **Consequence**: These fields remain documented in `docs/data_dictionary.md` but are excluded
  from planned analysis until a later snapshot or second city has usable coverage.
- **Alternative considered**: Fill missing response fields with `"unknown"` and analyse them.
  Rejected because it would silently turn missing source data into a false category.

### [2026-07-11] Review score coverage

- **Component**: data dictionary, validation, statistics
- **Assumption**: Review score fields are listing-level aggregates available only for listings
  with review history; missing values mean no usable source score, not a zero score.
- **Rationale**: The Amsterdam snapshot shows about 9.87% nulls across the review score fields,
  matching listings without review history.
- **Consequence**: Review score analyses must report the analysed population and must not impute
  missing scores to zero.
- **Alternative considered**: Treat missing review scores as poor quality ratings. Rejected
  because no source definition supports that interpretation.

### [2026-07-11] Anonymized listing coordinates

- **Component**: data dictionary, enrichment, maps
- **Assumption**: Listing latitude and longitude are approximate locations, not exact addresses.
- **Rationale**: Inside Airbnb states Airbnb anonymizes listing coordinates and nearby listings
  can appear scattered around their actual building.
- **Consequence**: Distance-to-centre features and maps are approximate. They can support
  neighbourhood-scale analysis, not address-level claims.
- **Alternative considered**: Treat coordinates as exact property locations. Rejected because
  the official assumptions page explicitly says coordinates are anonymized.

### [2026-07-11] Coordinate precision for canonical listings

- **Component**: validation, cleaning
- **Assumption**: Canonical listing latitude and longitude are rounded to 5 decimal places,
  while original coordinate values are preserved in `latitude_raw` and `longitude_raw`.
- **Rationale**: Five decimal places is precise enough for neighbourhood-scale grouping while
  avoiding false address-level precision.
- **Consequence**: Geographic grouping and distance calculations use rounded coordinates, and
  raw coordinates remain available for audit.
- **Alternative considered**: Keep only the raw coordinate fields. Rejected because downstream
  grouping would be less deterministic and would imply more precision than the source supports.

### [2026-07-11] Fuzzy duplicate candidate threshold

- **Component**: validation
- **Assumption**: Potential duplicate listings are flagged only when listings share the same
  `host_id`, rounded coordinate block, and have normalised `name` similarity of at least 90
  using RapidFuzz.
- **Rationale**: Blocking by host and rounded coordinates prevents all-pairs comparison and
  keeps the signal conservative.
- **Consequence**: Fuzzy matches are labelled as unusual candidate signals, not confirmed
  duplicates, and are not deleted by validation.
- **Alternative considered**: Compare every listing name against every other listing. Rejected
  because it is slow, noisy, and not needed for a conservative quality signal.

### [2026-07-11] Outlier visibility

- **Component**: validation, reporting
- **Assumption**: Plausible extreme values for price, availability, minimum nights, review count,
  and review frequency are flagged as unusual using a 3 IQR rule; price is also flagged above
  the 99th percentile.
- **Rationale**: Extreme values are analytically important but are not invalid solely because
  they are rare.
- **Consequence**: Validation reports outliers separately from missing and invalid records. No
  downstream analysis may exclude them without a new documented assumption and row count.
- **Alternative considered**: Quarantine all outliers during validation. Rejected because the
  validation step must not delete or quarantine plausible source records.

### [2026-07-11] Listing price parsing convention

- **Component**: cleaning
- **Assumption**: Listing price strings use comma thousands separators and dot decimal separators,
  for example `$1,075.00`.
- **Rationale**: The staged Amsterdam detailed listings sample contains `$94.00`, `$313.67`,
  and `$1,075.00`, which confirms the exported convention for this snapshot.
- **Consequence**: `price_raw` preserves the source string and `price` strips currency symbols
  plus comma separators before float conversion.
- **Alternative considered**: Treat dots as thousands separators. Rejected because sampled
  values use dots as decimal separators.

### [2026-07-11] Missing listing price handling

- **Component**: cleaning
- **Assumption**: A blank listing price is unknown source data, not a zero price and not a
  malformed price.
- **Rationale**: Validation already reports missing prices separately, and silently treating
  missing prices as invalid would remove many otherwise usable listing records from non-price
  analyses.
- **Consequence**: Rows with missing `price_raw` remain in `listings_master.parquet` with
  `price = null`, `price_log = null`, and `is_price_usable = false`. Non-empty unparseable
  prices and non-positive prices are quarantined.
- **Alternative considered**: Quarantine every missing price. Rejected because unknown values
  should remain null unless a downstream method requires a price-complete analysis view.

### [2026-07-11] Calendar aggregation fields

- **Component**: cleaning
- **Assumption**: The Amsterdam staged calendar file contains `listing_id`, `date`, `available`,
  `minimum_nights`, and `maximum_nights`; it does not contain a calendar price column.
- **Rationale**: The actual staged header was inspected before transformation. Adding price or
  revenue fields would invent source data.
- **Consequence**: `calendar_agg.parquet` contains monthly availability fields and
  `occupancy_proxy`; no calendar price or `revenue_proxy` is created from this file.
- **Alternative considered**: Join detailed listing price into calendar aggregation to estimate
  revenue. Rejected because that would mix quote prices with calendar availability and would need
  a separate documented analytical method.

### [2026-07-11] Long-stay listing treatment

- **Component**: cleaning
- **Assumption**: Listings with `minimum_nights > 365` are retained but flagged as
  `is_long_stay = true`.
- **Rationale**: Such listings are valid records but are not comparable in nightly-price analysis
  against short-stay listings.
- **Consequence**: `listings_master.parquet` preserves the rows and downstream price comparisons
  can exclude them explicitly with a reported row count.
- **Alternative considered**: Quarantine long-stay listings. Rejected because long minimum stays
  are unusual-but-plausible source values, not invalid data.

### [2026-07-11] host_since field is fully null in the Amsterdam 2026-06-15 snapshot

- **Component**: enrichment
- **Assumption**: The `host_since` column in the Amsterdam 2026-06-15 staged listings file
  contains no populated values. All 10,369 rows have a null `host_since`.
- **Rationale**: The staged file was inspected before implementing the enrichment. The field
  is documented in the Inside Airbnb data dictionary but is not populated in this snapshot export.
- **Consequence**: `host_tenure_years` is null for all listings in the Amsterdam run. It is
  retained as a column for compatibility if a later snapshot or city provides data.
- **Alternative considered**: Drop the column from the schema. Rejected because the field may
  be present in a future snapshot; keeping it null is less disruptive than altering the schema.

### [2026-07-11] Revenue proxy formula

- **Component**: enrichment
- **Assumption**: `revenue_proxy = listing_price * occupancy_proxy * total_calendar_days_observed`
  where `total_calendar_days_observed` is the sum of all daily rows in the calendar window for
  that listing, and `occupancy_proxy` is the mean monthly value across all observed months.
- **Rationale**: The calendar file does not contain a per-day price. The listing-level quote
  price is the only available price signal. This is a deliberate approximation, not observed
  revenue.
- **Consequence**: Every use of `revenue_proxy` carries the caveat:
  "Estimated from availability proxy and calendar price; not observed revenue."
  Listings with no calendar data or no usable price receive null.
- **Alternative considered**: Use only availability-derived days without price (i.e., a day-count
  proxy). Rejected because a price-weighted measure is more informative as a relative signal.

### [2026-07-11] Bedrooms field excluded from enrichment

- **Component**: enrichment
- **Assumption**: `price_per_bedroom` is not computed because the `bedrooms` column is not
  included in the set of columns selected during the cleaning step.
- **Rationale**: `bedrooms` was not in the `LISTING_COLUMNS` list used by cleaning. Adding it
  now would require re-running the cleaning step. The field is analytically optional for the
  enrichment outputs required.
- **Consequence**: `price_per_bedroom` is absent from `listings_master.parquet`. If added
  in a later iteration, a new assumption entry must document the null-handling rule
  (null when bedrooms is zero or null).
- **Alternative considered**: Re-run cleaning to include bedrooms. Deferred to avoid invalidating
  the existing quarantine and cleaning outputs.

### [2026-07-11] DuckDB star schema columns match enriched master only

- **Component**: database
- **Assumption**: The DuckDB star schema (`sql/schema.sql`) is defined based on columns that
  actually exist in `listings_master.parquet` after the cleaning and enrichment steps. Columns
  referenced in the original speculative schema design (e.g., `bedrooms`, `bathrooms`,
  `accommodates`, `property_type`, `host_is_superhost`, `host_response_rate`, review score
  sub-fields) were omitted because they are not present in the cleaned master.
- **Consequence**: Q4 uses host segment (casual vs professional) rather than superhost status.
  Q6 uses distance-to-centre buckets rather than weekday/weekend (day-level calendar data not
  available in `calendar_agg.parquet`).
- **Alternative considered**: Re-run cleaning to include additional columns. Deferred; adding
  fields requires documented schema change and re-validation.

### [2026-07-11] fact_calendar uses month-level grain, not day-level

- **Component**: database
- **Assumption**: `fact_calendar` stores one row per (listing_id, calendar month) because the
  pre-aggregated `calendar_agg.parquet` is the only available calendar source. Day-level calendar
  data was not loaded into pandas to respect the 8 GB RAM constraint.
- **Consequence**: Q6 (weekday vs weekend) cannot be answered from the current `fact_calendar`
  table. It was replaced with distance-to-centre vs price analysis, which uses listing-level data.
  A future day-level calendar table could be added by direct DuckDB scan of the raw calendar CSV.
- **Alternative considered**: DuckDB direct scan of raw calendar CSV at query time. Not implemented;
  deferred to a future iteration documented in decision_log.md.

### [2026-07-11] No slowly-changing dimension implementation

- **Component**: database
- **Assumption**: The star schema uses a drop-and-recreate pattern per load run. No history is
  preserved for changed attribute values (e.g., if a listing changes its price or room type between
  snapshots). This is a single-snapshot database.
- **Consequence**: Longitudinal analysis across multiple snapshots is not supported without an SCD
  implementation. The decision to defer SCD is documented in decision_log.md.
- **Alternative considered**: Type-2 SCD with effective date ranges. Deferred; requires multiple
  snapshots to be meaningful and adds significant complexity for a single-snapshot analytical goal.

### [2026-07-11] EDA figure selection

- **Component**: reporting
- **Assumption**: The EDA output set is limited to figures and tables that answer market structure,
  price, host concentration, review, availability, and geography questions using available source
  fields.
- **Rationale**: Decorative or redundant charts make the report harder to review and can distract
  from defensible business findings.
- **Consequence**: `reports/eda_coverage.md` records completed analyses and unavailable items.
  Host-tenure and host-response-rate charts are not generated because their populated row count is
  zero in this snapshot.
- **Alternative considered**: Generate placeholder charts for every requested topic. Rejected
  because placeholders would imply evidence that the snapshot does not contain.

### [2026-07-11] Review-score ceiling interpretation

- **Component**: reporting
- **Assumption**: Review-score distributions near the upper end of the 1-5 scale are described
  as ceiling concentration patterns only.
- **Rationale**: A distribution with many high ratings can suggest limited score separation, but
  it cannot prove rating inflation without a ground-truth quality measure or longitudinal design.
- **Consequence**: Review-score figures and tables avoid claiming inflated ratings from the
  distribution alone.
- **Alternative considered**: Label high-score concentration as rating inflation. Rejected because
  that would overstate what the dataset can support.

### [2026-07-11] Statistical test family and corrections

- **Component**: statistics
- **Assumption**: The planned statistical family contains seven documented hypothesis rows.
  Six rows are testable from the current Amsterdam outputs; the weekday/weekend calendar-price
  comparison is recorded as unavailable because no calendar price field exists in the staged
  calendar data or `calendar_agg.parquet`.
- **Rationale**: Multiple testing correction should apply to tests that were actually run.
  Reporting the unavailable row preserves the planned question without inventing a substitute.
- **Consequence**: `reports/tables/hypothesis_tests.csv` applies Benjamini-Hochberg and
  Bonferroni corrections across the six completed p-values. H4 has no p-value, effect size,
  or conclusion.
- **Alternative considered**: Substitute listing-level quote price for weekday/weekend calendar
  prices. Rejected because it mixes listing and listing-day grain and would not answer the
  calendar-price question.

### [2026-07-11] Statistical confidence interval method

- **Component**: statistics
- **Assumption**: Two-group log-price comparisons use Welch confidence intervals for mean
  log-price differences. Group median price intervals use deterministic bootstrap intervals
  with 500 resamples and seed 42. Neighbourhood comparisons require at least 15 listings.
- **Rationale**: Welch intervals match the unequal-variance tests. Bootstrap median intervals
  are simple and transparent for skewed price distributions.
- **Consequence**: `price_ci_by_room_type.csv` and `price_ci_by_neighbourhood.csv` can be quoted
  as descriptive median price intervals, not causal effects.
- **Alternative considered**: Use normal-theory intervals for medians. Rejected because the
  nightly price distribution is right-skewed.

### [2026-07-11] OLS model feature limits

- **Component**: statistics
- **Assumption**: The OLS model uses only fields available in the current analysis frame:
  log price, room type, grouped property type, bedrooms, minimum nights, review score,
  superhost flag, availability rate, distance to centre, and grouped neighbourhood fixed
  effects where the model sample has at least 15 rows.
- **Rationale**: The model must not add placeholder predictors for missing source fields.
  Property type, bedrooms, review score, and superhost flag are joined from staged detailed
  listings by `listing_id` instead of being added to the canonical Parquet contract.
- **Consequence**: `ols_price_model.csv` is an associational diagnostic table, not a causal
  pricing model or prediction system. The complete-case model uses 4,878 of 10,369 listings.
- **Alternative considered**: Add null-filled host tenure or response-rate predictors, or include
  all sparse property and neighbourhood categories. Rejected because null placeholders and sparse
  categories would make the model appear richer or more stable than the source data supports.

### [2026-07-11] Price-model correlation and residual diagnostics

- **Component**: statistics
- **Assumption**: Correlations are computed with Pearson correlation on complete model rows and
  are treated as screening diagnostics only. LOWESS scatter plots are generated for numeric
  features with enough distinct values to support a smoother. Residual summaries are grouped by
  room type, neighbourhood, and price decile.
- **Rationale**: Correlation and residual plots can reveal strong associations, non-linear
  patterns, and model fit issues, but they do not identify causal mechanisms.
- **Consequence**: `price_model_correlations.csv`, `price_model_strongest_correlations.csv`,
  `price_model_lowess_*.png`, `price_model_residuals_vs_fitted.png`, and residual summary CSVs
  are diagnostic artifacts for reviewer inspection.
- **Alternative considered**: Use every numeric field and every low-cardinality feature for
  smoothing. Rejected because low-unique-count features can produce unstable LOWESS curves and
  distract from interpretable diagnostics.

### [2026-07-11] Predictive experiment leakage policy and feature set

- **Component**: ml
- **Assumption**: The nightly-price prediction experiment uses `price_log` as the target and
  excludes identifiers, raw price, parsed price, `price_log` as a feature, `revenue_proxy`,
  `occupancy_proxy`, `availability_rate`, and `review_frequency`.
- **Rationale**: Price-derived fields and post-booking demand signals would leak information
  that would not be available for a clean pre-booking prediction task. `availability_rate` is
  also excluded because it is derived from future calendar availability relative to the listing
  snapshot.
- **Consequence**: `ml_experiment_results.csv`, `ml_test_predictions.csv`, and
  `ml_feature_importance.csv` evaluate only the documented non-price feature set.
- **Alternative considered**: Include `availability_rate`, `review_frequency`, and
  `revenue_proxy` to improve accuracy. Rejected because they are leakage-prone for the stated
  prediction task.

### [2026-07-11] Predictive experiment validation and metrics

- **Component**: ml
- **Assumption**: Each listing appears once in the modelling frame, so the experiment uses a
  reproducible 80/20 train-test split with `random_state = 42` and 5-fold cross-validation on
  the training set. MAPE is reported only where true price is at least 1.
- **Rationale**: There are no repeated listing observations requiring a grouped split. The test
  set must remain untouched until final evaluation.
- **Consequence**: Reported test metrics are based on 5,101 training rows and 1,276 test rows.
  Cross-validation mean and standard deviation are reported for log-scale MAE and RMSE.
- **Alternative considered**: Tune models on the test set or use full-dataset medians for
  imputation. Rejected because both would leak test-set information.

### [2026-07-11] Limited amenity features and no interactions

- **Component**: ml
- **Assumption**: Amenity feature engineering is limited to amenity count and six pre-selected
  flags: wifi, kitchen, washer, air conditioning, dedicated workspace, and free parking. No
  interaction terms are included.
- **Rationale**: These amenities are common, interpretable, and relevant to guest-visible listing
  value. Avoiding interactions keeps the experiment reviewable and prevents arbitrary feature
  expansion.
- **Consequence**: `ml_model_card.md` documents the exact feature set and notes that feature
  importance is predictive association, not causal evidence.
- **Alternative considered**: Generate one-hot features for every amenity and multiple
  interactions. Rejected because it would create hundreds of sparse features from one snapshot.

### [2026-07-12] Calendar-derived availability excluded from prediction

- **Component**: ml
- **Assumption**: `availability_rate` is forbidden as a predictive feature because it is derived
  from the calendar window after the listing snapshot date.
- **Rationale**: The predictive experiment should use listing attributes available before
  prediction. Future calendar availability can leak host strategy and future availability
  information into the model.
- **Consequence**: `availability_rate` is included in `FORBIDDEN_FEATURES`; attempting to add it
  to the model feature columns raises a leakage validation error.
- **Alternative considered**: Keep `availability_rate` with a caveat. Rejected because the
  stricter no-future-calendar rule is cleaner and easier to defend.
