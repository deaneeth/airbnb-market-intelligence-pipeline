# Data Quality Report

City: `amsterdam`
Snapshot date: `2026-06-15`

## File Summary

| File | Rows | Columns | Highest Null Column | Highest Null % |
|---|---:|---:|---|---:|
| `listings_detailed` | 10369 | 90 | `neighborhood_overview` | 100.00 |
| `listings_summary` | 10465 | 19 | `neighbourhood_group` | 100.00 |
| `calendar` | 3819725 | 5 | `listing_id` | 0.00 |
| `reviews_detailed` | 545162 | 6 | `comments` | 0.01 |
| `reviews_summary` | 545162 | 2 | `listing_id` | 0.00 |
| `neighbourhoods` | 22 | 2 | `neighbourhood_group` | 100.00 |
| `neighbourhoods_geojson` | 22 | 3 | `neighbourhood_group` | 100.00 |

## Highest-Risk Findings

### `listings_detailed`
- `neighborhood_overview` has 100.00% null values.
- `host_since` has 100.00% null values.
- `host_response_time` has 100.00% null values.

### `listings_summary`
- `neighbourhood_group` has 100.00% null values.
- `price` has 38.17% null values.
- `last_review` has 9.87% null values.

### `calendar`
- `listing_id` has 0.00% null values.
- `date` has 0.00% null values.
- `available` has 0.00% null values.

### `reviews_detailed`
- `comments` has 0.01% null values.
- `reviewer_name` has 0.00% null values.
- `listing_id` has 0.00% null values.

### `reviews_summary`
- `listing_id` has 0.00% null values.
- `date` has 0.00% null values.

### `neighbourhoods`
- `neighbourhood_group` has 100.00% null values.
- `neighbourhood` has 0.00% null values.

### `neighbourhoods_geojson`
- `neighbourhood_group` has 100.00% null values.
- `neighbourhood` has 0.00% null values.
- `geometry_type` has 0.00% null values.
