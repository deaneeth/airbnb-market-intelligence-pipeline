-- Star schema DDL for the Inside Airbnb analytical database.
-- This file is the single source of truth for table definitions.
-- The Python load step (database.py) executes this file to create or
-- replace the schema before loading data.
--
-- All tables are drop-and-recreate on each load run to ensure idempotency.
-- A production SCD implementation would replace this with upserts; that
-- is documented as a future enhancement in docs/decision_log.md.

-- ── Dimensions ──────────────────────────────────────────────────────────────

CREATE OR REPLACE TABLE dim_neighbourhood (
    neighbourhood_id    INTEGER PRIMARY KEY,
    neighbourhood       VARCHAR NOT NULL,
    neighbourhood_group VARCHAR,
    listing_count       INTEGER,
    median_price        DOUBLE,
    median_review_score DOUBLE
);

CREATE OR REPLACE TABLE dim_host (
    host_id             BIGINT PRIMARY KEY,
    host_name           VARCHAR,
    host_since          DATE,
    host_tenure_years   DOUBLE,
    host_is_superhost   BOOLEAN,
    host_response_rate  DOUBLE,
    portfolio_size      INTEGER,
    host_segment        VARCHAR   -- 'casual' (1 listing) or 'professional' (2+ listings)
);

CREATE OR REPLACE TABLE dim_listing (
    listing_id          BIGINT PRIMARY KEY,
    host_id             BIGINT REFERENCES dim_host(host_id),
    neighbourhood_id    INTEGER REFERENCES dim_neighbourhood(neighbourhood_id),
    room_type           VARCHAR,
    property_type       VARCHAR,
    bedrooms            DOUBLE,
    bathrooms           DOUBLE,
    accommodates        INTEGER,
    minimum_nights      INTEGER,
    latitude            DOUBLE,
    longitude           DOUBLE,
    distance_to_centre  DOUBLE  -- kilometres; reference point documented in assumptions.md
);

CREATE OR REPLACE TABLE dim_date (
    date_id     INTEGER PRIMARY KEY,  -- YYYYMMDD integer key
    date        DATE NOT NULL,
    year        INTEGER,
    month       INTEGER,
    month_name  VARCHAR,
    day_of_week INTEGER,  -- 0=Monday, 6=Sunday
    is_weekend  BOOLEAN
);

-- ── Facts ────────────────────────────────────────────────────────────────────

CREATE OR REPLACE TABLE fact_listing_snapshot (
    listing_id              BIGINT PRIMARY KEY REFERENCES dim_listing(listing_id),
    host_id                 BIGINT REFERENCES dim_host(host_id),
    neighbourhood_id        INTEGER REFERENCES dim_neighbourhood(neighbourhood_id),
    snapshot_date           DATE NOT NULL,
    price_raw               VARCHAR,           -- original string value preserved
    price                   DOUBLE,            -- parsed numeric price (nightly)
    price_per_bedroom       DOUBLE,            -- null when bedrooms is null or zero
    availability_365        INTEGER,
    number_of_reviews       INTEGER,
    review_score_rating     DOUBLE,
    review_score_accuracy   DOUBLE,
    review_score_cleanliness DOUBLE,
    review_score_checkin    DOUBLE,
    review_score_communication DOUBLE,
    review_score_location   DOUBLE,
    review_score_value      DOUBLE,
    reviews_per_month       DOUBLE,
    review_frequency        DOUBLE             -- reviews per month; labelled as demand proxy
);

CREATE OR REPLACE TABLE fact_calendar (
    listing_id              BIGINT REFERENCES dim_listing(listing_id),
    date_id                 INTEGER REFERENCES dim_date(date_id),
    available               BOOLEAN,           -- true = host-available; NOT confirmed-unbooked
    price                   DOUBLE,
    minimum_nights          INTEGER,
    PRIMARY KEY (listing_id, date_id)
);

-- fact_review is created when detailed reviews are available.
-- CREATE OR REPLACE TABLE fact_review (
--     review_id     BIGINT PRIMARY KEY,
--     listing_id    BIGINT REFERENCES dim_listing(listing_id),
--     reviewer_id   BIGINT,
--     review_date   DATE,
--     comments      VARCHAR
-- );
