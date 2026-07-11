-- Star schema DDL for the Inside Airbnb analytical database.
-- Executed by database.py before each load. All tables use CREATE OR REPLACE
-- so the load is fully idempotent: safe to re-run from the same Parquet inputs.
--
-- Grain and foreign keys are documented in docs/lineage.md.
-- A production SCD implementation would replace the drop-and-recreate pattern
-- with upserts; that is deferred and documented in docs/decision_log.md.

-- Drop in reverse dependency order so foreign key constraints do not block.
DROP TABLE IF EXISTS fact_calendar;
DROP TABLE IF EXISTS fact_listing_snapshot;
DROP TABLE IF EXISTS dim_listing;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_host;
DROP TABLE IF EXISTS dim_neighbourhood;



CREATE OR REPLACE TABLE dim_neighbourhood (
    neighbourhood_id    INTEGER PRIMARY KEY,
    neighbourhood       VARCHAR NOT NULL,
    listing_count       INTEGER,       -- listings in this snapshot
    median_price        DOUBLE         -- median nightly price; null for small neighbourhoods
);

CREATE OR REPLACE TABLE dim_host (
    host_id             BIGINT PRIMARY KEY,
    host_since          DATE,
    host_tenure_years   DOUBLE,        -- null when host_since is null in source
    portfolio_size      INTEGER,       -- count of listings this host has in snapshot
    host_segment        VARCHAR        -- 'casual' (1 listing) or 'professional' (2+)
);

CREATE OR REPLACE TABLE dim_listing (
    listing_id          BIGINT PRIMARY KEY,
    host_id             BIGINT REFERENCES dim_host(host_id),
    neighbourhood_id    INTEGER REFERENCES dim_neighbourhood(neighbourhood_id),
    room_type           VARCHAR,
    minimum_nights      INTEGER,
    latitude            DOUBLE,
    longitude           DOUBLE,
    distance_to_centre_km DOUBLE       -- Haversine km from Dam Square; see docs/assumptions.md
);

CREATE OR REPLACE TABLE dim_date (
    date_id     INTEGER PRIMARY KEY,   -- YYYYMMDD integer key
    date        DATE NOT NULL,
    year        INTEGER,
    month       INTEGER,
    month_name  VARCHAR,
    day_of_week INTEGER,               -- 0=Monday, 6=Sunday
    is_weekend  BOOLEAN
);

-- ── Facts ────────────────────────────────────────────────────────────────────

CREATE OR REPLACE TABLE fact_listing_snapshot (
    listing_id              BIGINT PRIMARY KEY REFERENCES dim_listing(listing_id),
    host_id                 BIGINT REFERENCES dim_host(host_id),
    neighbourhood_id        INTEGER REFERENCES dim_neighbourhood(neighbourhood_id),
    snapshot_date           DATE NOT NULL,
    price                   DOUBLE,    -- parsed nightly price; null when source is empty
    price_raw               VARCHAR,   -- original string preserved for auditability
    availability_365        INTEGER,
    number_of_reviews       INTEGER,
    review_frequency        DOUBLE,    -- reviews per month; demand proxy only
    availability_rate       DOUBLE,    -- share of calendar days host marked available
    occupancy_proxy         DOUBLE,    -- 1 - availability_rate; not confirmed bookings
    revenue_proxy           DOUBLE     -- price * occupancy_proxy * days_observed; not observed revenue
);

-- fact_calendar stores monthly aggregates from calendar_agg.parquet.
-- The source calendar file is day-level but is pre-aggregated to month-level
-- before loading to stay within the 8 GB memory constraint.
-- A day-level fact_calendar would require DuckDB direct parquet scan; deferred.
CREATE OR REPLACE TABLE fact_calendar (
    listing_id          BIGINT REFERENCES dim_listing(listing_id),
    month               VARCHAR NOT NULL,          -- YYYY-MM
    days_observed       INTEGER,
    days_available      DOUBLE,
    availability_rate   DOUBLE,
    occupancy_proxy     DOUBLE,
    snapshot_date       DATE,
    PRIMARY KEY (listing_id, month)
);
