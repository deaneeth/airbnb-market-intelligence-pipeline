# EDA Coverage

City: amsterdam
Snapshot date: 2026-06-15

| Analysis | Status | Reason |
|---|---|---|
| price distribution and log-price distribution | completed | price and price_log are available |
| price by room type and property type | completed | room_type and property_type are available |
| price by neighbourhood with minimum sample threshold | completed | N >= 15 |
| listing and host portfolio concentration | completed | host_id and portfolio_size are available |
| review-score distribution and subdimensions | completed | review score fields are available in staged detailed listings |
| availability by month | completed | calendar_agg.parquet provides month-level availability |
| neighbourhood listing density and price map | completed | GeoJSON and listing coordinates are available |
| neighbourhood review-score table | completed | review score fields are available |
| geographic mix of room types and property types | completed | room type and top property type geography figures generated |
| price versus approximate distance to centre | completed | distance_to_centre_km is available |
| host tenure versus price | unavailable | host_tenure_years populated rows: 0 |
| newer-versus-established host comparison | unavailable | host_since is fully null for snapshot 2026-06-15 |
| host segment versus price and availability | completed | host_segment and availability_rate are available |
| host response rate versus listing performance | unavailable | host_response_rate populated rows: 0 |
| superhost status versus listing performance | completed | host_is_superhost is available in staged detailed listings |
| review frequency versus price and review score | completed | review_frequency is available as a demand signal proxy only |
| high-review, low-score listing profile | completed | profile table generated from review count and score quartiles |
| review volume trend over available dates | completed | reviews_summary.csv provides review dates |
| minimum-night policy by month | completed | calendar_agg.parquet provides monthly minimum-night summaries |
| event-level analysis | unavailable | no external event data was introduced |
