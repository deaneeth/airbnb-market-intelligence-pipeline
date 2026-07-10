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
