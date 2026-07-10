-- Business SQL queries for the Inside Airbnb analytical database.
-- All queries are written against the star schema defined in schema.sql.
-- Each query is named and documented so it can be executed from database.py
-- and referenced in the report with a traceable source.
--
-- Column aliases use plain English so results are self-explanatory to
-- business stakeholders without additional documentation.

-- ── Q1: Median nightly price by neighbourhood and room type ───────────────────
-- Restricted to neighbourhoods with at least 10 listings to avoid misleading
-- aggregates from very small samples. Threshold documented in assumptions.md.

SELECT
    dn.neighbourhood,
    dl.room_type,
    COUNT(*)                                AS listing_count,
    MEDIAN(fls.price)                       AS median_nightly_price,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY fls.price) AS price_p25,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY fls.price) AS price_p75
FROM fact_listing_snapshot fls
JOIN dim_listing    dl  ON fls.listing_id      = dl.listing_id
JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
WHERE fls.price > 0
GROUP BY dn.neighbourhood, dl.room_type
HAVING COUNT(*) >= 10
ORDER BY median_nightly_price DESC;


-- ── Q2: Listing supply and host concentration by neighbourhood ────────────────
-- Shows supply concentration: what share of listings each neighbourhood holds,
-- and how many unique hosts operate there.

SELECT
    dn.neighbourhood,
    COUNT(DISTINCT fls.listing_id)  AS total_listings,
    COUNT(DISTINCT fls.host_id)     AS unique_hosts,
    ROUND(
        COUNT(DISTINCT fls.listing_id) * 100.0
        / SUM(COUNT(DISTINCT fls.listing_id)) OVER (),
        2
    )                               AS share_of_total_listings_pct
FROM fact_listing_snapshot fls
JOIN dim_listing    dl  ON fls.listing_id      = dl.listing_id
JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
GROUP BY dn.neighbourhood
ORDER BY total_listings DESC;


-- ── Q3: Calendar availability rate and revenue proxy by month ─────────────────
-- availability_rate = share of days marked available by the host.
-- revenue_proxy    = (1 - availability_rate) * median_calendar_price * days_in_month.
-- Both are labelled as proxies; see docs/assumptions.md for caveats.

SELECT
    dd.year,
    dd.month,
    dd.month_name,
    ROUND(AVG(CASE WHEN fc.available THEN 1.0 ELSE 0.0 END), 4) AS avg_availability_rate,
    ROUND(1 - AVG(CASE WHEN fc.available THEN 1.0 ELSE 0.0 END), 4) AS avg_occupancy_proxy,
    MEDIAN(fc.price)                                                  AS median_calendar_price
FROM fact_calendar fc
JOIN dim_date dd ON fc.date_id = dd.date_id
WHERE fc.price > 0
GROUP BY dd.year, dd.month, dd.month_name
ORDER BY dd.year, dd.month;


-- ── Q4: Superhost versus non-superhost comparison ─────────────────────────────

SELECT
    dh.host_is_superhost,
    COUNT(DISTINCT fls.listing_id)  AS listing_count,
    MEDIAN(fls.price)               AS median_price,
    AVG(fls.review_score_rating)    AS avg_review_score,
    AVG(fls.number_of_reviews)      AS avg_review_count
FROM fact_listing_snapshot fls
JOIN dim_host dh ON fls.host_id = dh.host_id
WHERE fls.price > 0
GROUP BY dh.host_is_superhost;


-- ── Q5: Top and bottom 10 neighbourhoods by listing supply and median price ───

(
    SELECT
        dn.neighbourhood,
        COUNT(*)        AS listing_count,
        MEDIAN(fls.price) AS median_price,
        'top_supply'    AS category
    FROM fact_listing_snapshot fls
    JOIN dim_listing    dl  ON fls.listing_id      = dl.listing_id
    JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
    GROUP BY dn.neighbourhood
    ORDER BY listing_count DESC
    LIMIT 10
)
UNION ALL
(
    SELECT
        dn.neighbourhood,
        COUNT(*)        AS listing_count,
        MEDIAN(fls.price) AS median_price,
        'bottom_supply' AS category
    FROM fact_listing_snapshot fls
    JOIN dim_listing    dl  ON fls.listing_id      = dl.listing_id
    JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
    GROUP BY dn.neighbourhood
    ORDER BY listing_count ASC
    LIMIT 10
);


-- ── Q6: Weekday versus weekend calendar price comparison ──────────────────────
-- Used as input for the weekday/weekend hypothesis test.
-- Weekend defined as Saturday (day_of_week = 5) and Sunday (day_of_week = 6).

SELECT
    dd.is_weekend,
    COUNT(*)            AS observation_count,
    MEDIAN(fc.price)    AS median_price,
    AVG(fc.price)       AS mean_price,
    STDDEV(fc.price)    AS stddev_price
FROM fact_calendar fc
JOIN dim_date dd ON fc.date_id = dd.date_id
WHERE fc.price > 0
GROUP BY dd.is_weekend;


-- ── Q7: Listing-level review and price summary ────────────────────────────────

SELECT
    fls.listing_id,
    dl.room_type,
    dn.neighbourhood,
    fls.price,
    fls.number_of_reviews,
    fls.review_score_rating,
    fls.review_frequency        AS review_frequency_demand_proxy,
    dh.host_is_superhost,
    dh.host_segment
FROM fact_listing_snapshot fls
JOIN dim_listing    dl  ON fls.listing_id      = dl.listing_id
JOIN dim_neighbourhood dn ON dl.neighbourhood_id = dn.neighbourhood_id
JOIN dim_host       dh  ON fls.host_id         = dh.host_id
WHERE fls.price > 0
ORDER BY fls.listing_id;
