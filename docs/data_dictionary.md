# Data Dictionary

Column-level documentation for every field used in analysis. Null rates and value ranges
are populated after the profiling step runs on the real dataset.

---

## Source Files

| File Key | File Name | Format | Description |
|---|---|---|---|
| `listings_detailed` | `listings.csv.gz` | gzip CSV | Full listing attributes including all review scores, host details, and amenities |
| `listings_summary` | `listings.csv` | CSV | Subset of listing fields optimised for map visualisations |
| `calendar` | `calendar.csv.gz` | gzip CSV | Daily availability and price per listing for the next 365 days |
| `reviews_detailed` | `reviews.csv.gz` | gzip CSV | Individual review text with reviewer ID, date, and comments |
| `reviews_summary` | `reviews.csv` | CSV | Aggregate review counts and scores per listing |
| `neighbourhoods` | `neighbourhoods.csv` | CSV | Neighbourhood names and optional group labels |
| `neighbourhoods_geojson` | `neighbourhoods.geojson` | GeoJSON | Polygon boundaries for each neighbourhood |

---

## Key Column Definitions

### Listings (listings_detailed)

| Column | Constant | Type | Description | Notes |
|---|---|---|---|---|
| `id` | `COL_LISTING_ID` | int64 | Airbnb listing identifier | Renamed to `listing_id` in canonical table |
| `host_id` | `COL_HOST_ID` | int64 | Airbnb host identifier | |
| `price` | `COL_PRICE_RAW` | str (raw) / float64 (parsed) | Nightly price string | Includes `$` and `,`; parsed to float and stored in `price` |
| `room_type` | `COL_ROOM_TYPE` | category | Listing type | Values: Entire home/apt, Private room, Shared room, Hotel room |
| `neighbourhood_cleansed` | `COL_NEIGHBOURHOOD` | str | Neighbourhood name as cleaned by Inside Airbnb | Do not alter spelling |
| `latitude` | n/a | float64 | Latitude (5 d.p. in canonical table) | Original stored in `latitude_raw` |
| `longitude` | n/a | float64 | Longitude (5 d.p. in canonical table) | Original stored in `longitude_raw` |
| `availability_365` | n/a | int32 | Days available in the next 365 days | Set by the host, not by bookings |
| `minimum_nights` | n/a | int32 | Minimum booking length | Values > 365 flagged as `is_long_stay` |
| `reviews_per_month` | `COL_REVIEW_FREQUENCY` | float64 | Avg reviews per month | Renamed to `review_frequency`; used as demand proxy only |

### Derived Columns (added in enrichment)

| Column | Constant | Type | Description |
|---|---|---|---|
| `price_log` | `COL_PRICE_LOG` | float64 | `log1p(price)`; used as regression target |
| `availability_rate` | `COL_AVAILABILITY_RATE` | float64 | Mean share of available days across calendar months |
| `occupancy_proxy` | `COL_OCCUPANCY_PROXY` | float64 | `1 - availability_rate`; not confirmed bookings |
| `revenue_proxy` | `COL_REVENUE_PROXY` | float64 | Estimated monthly revenue from calendar price and occupancy proxy |
| `host_segment` | `COL_HOST_SEGMENT` | category | `"casual"` (1 listing) or `"professional"` (2+ listings) |
| `snapshot_date` | `COL_SNAPSHOT_DATE` | date | Snapshot date from config; 2026-06-15 for Amsterdam |

### Calendar (calendar)

| Column | Type | Description |
|---|---|---|
| `listing_id` | int64 | Foreign key to listings `id` |
| `date` | date | Calendar date |
| `available` | str | `"t"` (available) or `"f"` (booked/blocked) |
| `price` | str | Host-set nightly price for that date; may differ from listing price |

---

## Ambiguous Fields

- **`availability_365`** (listings): Set by the host, not derived from bookings. A host
  can set their listing as available for 0 days to effectively pause it. This field does
  not reflect actual bookings. See `docs/assumptions.md` - Availability rate as occupancy proxy.

- **`reviews_per_month`** (listings): Computed by Inside Airbnb from the review history.
  It is used as a demand signal proxy, not as a confirmed booking rate. Review submission is
  optional; not all guests leave reviews.

- **`price`** (calendar vs listings): The calendar price is a host-set nightly price that
  can vary by date (e.g. weekend surcharge). The listings `price` is the base nightly price.
  The pipeline uses calendar price for monthly revenue proxy calculations and listings price
  for cross-listing comparisons.
