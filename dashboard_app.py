from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from airbnb_intelligence.dashboard import (
    PROPERTY_TYPE,
    filter_listings,
    filter_values,
    kpi_summary,
    load_dashboard_data,
    monthly_availability,
    price_histogram,
    room_type_price_table,
    supply_table,
)
from airbnb_intelligence.utils import COL_AVAILABILITY_RATE, COL_NEIGHBOURHOOD, COL_ROOM_TYPE

if TYPE_CHECKING:
    import pandas as pd


@st.cache_data
def _load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    data = load_dashboard_data("amsterdam")
    return data.listings, data.calendar


def main() -> None:
    st.set_page_config(page_title="Amsterdam Airbnb Market", layout="wide")
    listings, calendar = _load_data()

    st.title("Amsterdam Airbnb Market")
    st.caption("Snapshot: 2026-06-15. Built from generated processed Parquet outputs only.")

    neighbourhoods = st.sidebar.multiselect(
        "Neighbourhood",
        filter_values(listings, COL_NEIGHBOURHOOD),
    )
    room_types = st.sidebar.multiselect("Room type", filter_values(listings, COL_ROOM_TYPE))
    property_options = filter_values(listings, PROPERTY_TYPE)
    property_types = st.sidebar.multiselect(
        "Property type",
        property_options,
        disabled=not property_options,
        help=(
            "Property type is unavailable because it is not part of the processed dashboard input."
            if not property_options
            else None
        ),
    )

    filtered = filter_listings(listings, neighbourhoods, room_types, property_types)
    summary = kpi_summary(filtered)

    cols = st.columns(4)
    cols[0].metric("Listings", f"{summary['listing_count']:,.0f}")
    cols[1].metric("Median nightly price", f"{summary['median_price']:,.0f}")
    cols[2].metric("Availability rate", f"{summary['availability_rate']:.1f}%")
    cols[3].metric("Professional host share", f"{summary['professional_host_share']:.1f}%")

    if filtered.empty:
        st.warning("No listings match the selected filters.")
        return

    left, right = st.columns((2, 1))
    with left:
        st.subheader("Price distribution")
        histogram = price_histogram(filtered)
        st.bar_chart(histogram, x="price_bin", y="listing_count", width="stretch")
    with right:
        st.subheader("Interpretation")
        st.write(
            "The selected listings show the market level and spread for visible nightly prices. "
            "Availability rate is host-set availability, not confirmed occupancy."
        )

    st.subheader("Availability trend")
    trend = monthly_availability(calendar, filtered["listing_id"])
    st.line_chart(trend, x="month", y=COL_AVAILABILITY_RATE, width="stretch")

    table_left, table_right = st.columns(2)
    with table_left:
        st.subheader("Supply and price by neighbourhood")
        st.dataframe(supply_table(filtered), width="stretch", hide_index=True)
    with table_right:
        st.subheader("Price by room type")
        st.dataframe(room_type_price_table(filtered), width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
