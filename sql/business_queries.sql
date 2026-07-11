-- Business SQL queries for the Inside Airbnb analytical database.
-- All queries run against the star schema defined in schema.sql.
-- Results are exported to reports/tables/ by database.py.
--
-- Proxy caveats:
--   occupancy_proxy : Derived from host-set availability; not equivalent to confirmed booked nights.
--   revenue_proxy   : Estimated from availability proxy and calendar price; not observed revenue.
--   review_frequency: Reviews per month as reported by Inside Airbnb; demand signal proxy only.

-- ── Q1: Median nightly price by neighbourhood and room type ──────────────────

SELECT
    dn.neighbourhood,
    dl.room_type,
    COUNT(*)                                                    AS listing_count,
    MEDIAN(fls.price)                                           AS median_nightly_price,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY fls.price)    AS price_p25,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY fls.price)    AS price_p75
FROM fact_listing_snapshot fls
JOIN dim_listing       dl ON fls.listing_id      = dl.listing_id
JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
WHERE fls.price > 0
GROUP BY dn.neighbourhood, dl.room_type
HAVING COUNT(*) >= 10
ORDER BY median_nightly_price DESC;


-- ── Q2: Listing supply and host concentration by neighbourhood ────────────────

SELECT
    dn.neighbourhood,
    COUNT(DISTINCT fls.listing_id)                                          AS total_listings,
    COUNT(DISTINCT fls.host_id)                                             AS unique_hosts,
    ROUND(
        COUNT(DISTINCT fls.listing_id) * 100.0
        / SUM(COUNT(DISTINCT fls.listing_id)) OVER (),
        2
    )                                                                       AS share_of_total_pct
FROM fact_listing_snapshot fls
JOIN dim_listing       dl ON fls.listing_id      = dl.listing_id
JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
GROUP BY dn.neighbourhood
ORDER BY total_listings DESC;


-- ── Q3: Availability rate and occupancy proxy by calendar month ───────────────
-- occupancy_proxy: Derived from host-set availability; not equivalent to confirmed booked nights.

SELECT
    fc.month,
    COUNT(DISTINCT fc.listing_id)           AS listings_with_calendar_data,
    ROUND(AVG(fc.availability_rate), 4)     AS avg_availability_rate,
    ROUND(AVG(fc.occupancy_proxy), 4)       AS avg_occupancy_proxy,
    ROUND(SUM(fc.days_observed), 0)         AS total_days_observed
FROM fact_calendar fc
GROUP BY fc.month
ORDER BY fc.month;


-- ── Q4: Host segment comparison (casual vs professional) ─────────────────────
-- host_segment: 'casual' = 1 listing, 'professional' = 2+ listings in snapshot.

SELECT
    dh.host_segment,
    COUNT(DISTINCT fls.listing_id)      AS listing_count,
    COUNT(DISTINCT fls.host_id)         AS host_count,
    MEDIAN(fls.price)                   AS median_price,
    ROUND(AVG(fls.number_of_reviews), 1) AS avg_review_count,
    ROUND(AVG(fls.review_frequency), 3) AS avg_review_frequency
FROM fact_listing_snapshot fls
JOIN dim_host dh ON fls.host_id = dh.host_id
WHERE fls.price > 0
GROUP BY dh.host_segment;


-- ── Q5: Top and bottom 10 neighbourhoods by listing supply and median price ───

(
    SELECT
        dn.neighbourhood,
        COUNT(*)            AS listing_count,
        MEDIAN(fls.price)   AS median_price,
        'top_supply'        AS category
    FROM fact_listing_snapshot fls
    JOIN dim_listing       dl ON fls.listing_id      = dl.listing_id
    JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
    GROUP BY dn.neighbourhood
    ORDER BY listing_count DESC
    LIMIT 10
)
UNION ALL
(
    SELECT
        dn.neighbourhood,
        COUNT(*)            AS listing_count,
        MEDIAN(fls.price)   AS median_price,
        'bottom_supply'     AS category
    FROM fact_listing_snapshot fls
    JOIN dim_listing       dl ON fls.listing_id      = dl.listing_id
    JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
    GROUP BY dn.neighbourhood
    ORDER BY listing_count ASC
    LIMIT 10
);


-- ── Q6: Distance to centre vs price (decile buckets) ─────────────────────────
-- Shows whether listings closer to Dam Square command higher prices.

SELECT
    FLOOR(dl.distance_to_centre_km)    AS distance_km_bucket,
    COUNT(*)                           AS listing_count,
    MEDIAN(fls.price)                  AS median_price,
    ROUND(AVG(fls.price), 2)           AS mean_price
FROM fact_listing_snapshot fls
JOIN dim_listing dl ON fls.listing_id = dl.listing_id
WHERE fls.price > 0
  AND dl.distance_to_centre_km IS NOT NULL
GROUP BY FLOOR(dl.distance_to_centre_km)
ORDER BY distance_km_bucket;


-- ── Q7: Listing-level review and price summary ────────────────────────────────

SELECT
    fls.listing_id,
    dl.room_type,
    dn.neighbourhood,
    fls.price,
    fls.number_of_reviews,
    fls.review_frequency        AS review_frequency_demand_proxy,
    fls.availability_rate,
    fls.occupancy_proxy,
    fls.revenue_proxy,
    dh.host_segment
FROM fact_listing_snapshot fls
JOIN dim_listing       dl ON fls.listing_id      = dl.listing_id
JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
JOIN dim_host          dh ON fls.host_id         = dh.host_id
WHERE fls.price > 0
ORDER BY fls.listing_id;
