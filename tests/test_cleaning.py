from __future__ import annotations

import pandas as pd

from airbnb_intelligence.cleaning import (
    clean_listings_frame,
    normalise_boolean,
    normalise_category,
    normalise_place_text,
    parse_date,
    parse_price,
)


def test_parse_price_strips_currency_and_thousands_separator() -> None:
    assert parse_price(" $1,075.50 ") == 1075.50


def test_parse_price_returns_none_for_missing_and_invalid_values() -> None:
    assert parse_price(None) is None
    assert parse_price("") is None
    assert parse_price("not a price") is None


def test_parse_price_never_imputes_zero() -> None:
    assert parse_price(None) != 0


def test_parse_date_uses_explicit_format() -> None:
    assert parse_date("2026-06-15").isoformat() == "2026-06-15"
    assert parse_date("15/06/2026") is None


def test_normalise_boolean_maps_source_flags() -> None:
    assert normalise_boolean("t") is True
    assert normalise_boolean("f") is False
    assert normalise_boolean(None) is None
    assert normalise_boolean("yes") is None


def test_normalise_category_and_place_text_preserve_expected_unknowns() -> None:
    assert normalise_category(" Entire home/apt ") == "entire home/apt"
    assert normalise_category(None) is None
    assert normalise_place_text(" Centrum-West ") == "Centrum-West"
    assert normalise_place_text("") == "Unknown"


def test_clean_listings_preserves_missing_price_as_null() -> None:
    master, quarantine = clean_listings_frame(
        _listing_fixture(price=None),
        city_name="Amsterdam",
        snapshot_date="2026-06-15",
    )

    assert len(master) == 1
    assert pd.isna(master.loc[0, "price"])
    assert master.loc[0, "price_raw"] is pd.NA or pd.isna(master.loc[0, "price_raw"])
    assert quarantine.empty


def test_clean_listings_quarantines_failed_price_parse() -> None:
    master, quarantine = clean_listings_frame(
        _listing_fixture(price="bad"),
        city_name="Amsterdam",
        snapshot_date="2026-06-15",
    )

    assert master.empty
    assert quarantine.columns.tolist() == [
        "source_file",
        "source_row_index",
        "listing_id",
        "reason",
        "raw_value",
        "snapshot_date",
    ]
    assert quarantine.loc[0, "source_row_index"] == 0
    assert quarantine.loc[0, "reason"] == "price_parse_failed"
    assert quarantine.loc[0, "raw_value"] == "bad"


def test_clean_listings_quarantines_invalid_coordinates() -> None:
    master, quarantine = clean_listings_frame(
        _listing_fixture(latitude=95.0, longitude=4.89),
        city_name="Amsterdam",
        snapshot_date="2026-06-15",
    )

    assert master.empty
    assert quarantine["reason"].tolist() == ["latitude_out_of_range"]


def test_clean_listings_sets_traceable_canonical_columns() -> None:
    master, quarantine = clean_listings_frame(
        _listing_fixture(
            price="$125.00", room_type=" Private room ", neighbourhood=" Centrum-West "
        ),
        city_name="Amsterdam",
        snapshot_date="2026-06-15",
    )

    assert quarantine.empty
    assert master.loc[0, "listing_id"] == 123
    assert master.loc[0, "price_raw"] == "$125.00"
    assert master.loc[0, "price"] == 125.0
    assert master.loc[0, "room_type_raw"] == " Private room "
    assert master.loc[0, "room_type"] == "private room"
    assert master.loc[0, "neighbourhood_raw"] == " Centrum-West "
    assert master.loc[0, "neighbourhood_cleansed"] == "Centrum-West"
    assert master.loc[0, "latitude"] == 52.36775
    assert master.loc[0, "latitude_raw"] == 52.367751


def _listing_fixture(
    *,
    price: object = "$100.00",
    latitude: float = 52.367751,
    longitude: float = 4.890921,
    room_type: str = "Entire home/apt",
    neighbourhood: str = "Centrum-West",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [123],
            "host_id": [456],
            "price": [price],
            "room_type": [room_type],
            "neighbourhood_cleansed": [neighbourhood],
            "latitude": [latitude],
            "longitude": [longitude],
            "minimum_nights": [2],
            "availability_365": [120],
            "number_of_reviews": [10],
            "reviews_per_month": [1.25],
            "host_since": ["2020-01-01"],
            "last_review": ["2026-06-01"],
        }
    )
