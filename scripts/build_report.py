from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
TABLES = REPORTS / "tables"
FIGURES = REPORTS / "figures"
DOCX_PATH = REPORTS / "Airbnb_Market_Intelligence_Report.docx"
MD_PATH = REPORTS / "final_report.md"
CITY = "Amsterdam"
SNAPSHOT = "2026-06-15"


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)


def money(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):,.2f}"


def ratio(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def number(value: Any, digits: int = 3) -> str:
    if pd.isna(value):
        return "n/a"
    value = float(value)
    if abs(value) >= 100:
        return f"{value:,.2f}"
    return f"{value:.{digits}f}"


def add_page_number(doc: Document) -> None:
    for section in doc.sections:
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer.add_run("Page ")
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        footer._p.append(field)


def add_toc(doc: Document) -> None:
    paragraph = doc.add_paragraph()
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), 'TOC \\o "1-3" \\h \\z \\u')
    paragraph._p.append(field)


def set_styles(doc: Document) -> None:
    styles = doc.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(10.5)
    for name, size in {
        "Title": 26,
        "Heading 1": 18,
        "Heading 2": 14,
        "Heading 3": 12,
    }.items():
        styles[name].font.name = "Aptos"
        styles[name].font.size = Pt(size)


def paragraph(doc: Document, text: str = "", style: str | None = None) -> None:
    item = doc.add_paragraph(text, style=style)
    item.paragraph_format.space_after = Pt(6)


def bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        paragraph(doc, item, "List Bullet")


def numbered(doc: Document, items: list[str]) -> None:
    for item in items:
        paragraph(doc, item, "List Number")


def table(doc: Document, data: pd.DataFrame, title: str, source: str, rows: int = 12) -> None:
    paragraph(doc, title, "Heading 3")
    shown = data.head(rows)
    grid = doc.add_table(rows=1, cols=len(shown.columns))
    grid.style = "Table Grid"
    grid.autofit = True
    for index, column in enumerate(shown.columns):
        grid.rows[0].cells[index].text = str(column)
    for _, row in shown.iterrows():
        cells = grid.add_row().cells
        for index, column in enumerate(shown.columns):
            value = row[column]
            cells[index].text = number(value, 4) if isinstance(value, float) else str(value)
    for row in grid.rows:
        for cell in row.cells:
            for item in cell.paragraphs:
                for run in item.runs:
                    run.font.size = Pt(8)
    paragraph(doc, f"Source: {source}. Showing {len(shown)} of {len(data)} rows.")


def figure(doc: Document, figure_no: int, filename: str, title: str, caption: str) -> None:
    path = FIGURES / filename
    if path.exists():
        doc.add_picture(str(path), width=Inches(6.3))
    else:
        paragraph(doc, f"[Missing generated figure: {filename}]")
    paragraph(doc, f"Figure {figure_no}. {title}. {caption}", "Caption")


def clean_text(value: str) -> str:
    return (
        value.replace("not a causal effect", "not causal evidence")
        .replace("not causal effects", "not causal evidence")
        .replace("not causal.", "not causal evidence.")
    )


def issue_summary(issues: pd.DataFrame) -> pd.DataFrame:
    return (
        issues.groupby(["finding_type", "rule_id"])
        .size()
        .reset_index(name="issue_count")
        .sort_values("issue_count", ascending=False)
    )


def build() -> None:
    room = read_csv("eda_room_type_summary.csv")
    neighbourhood = read_csv("eda_neighbourhood_summary.csv")
    host = read_csv("eda_host_segment_summary.csv")
    monthly = read_csv("eda_monthly_availability.csv")
    review = read_csv("eda_review_score_summary.csv")
    hypothesis = read_csv("hypothesis_tests.csv")
    ols = read_csv("ols_price_model.csv")
    vif = read_csv("ols_price_model_vif.csv")
    ols_limits = read_csv("ols_price_model_limitations.csv")
    ml = read_csv("ml_experiment_results.csv")
    importance = read_csv("ml_feature_importance.csv")
    ml_room = read_csv("ml_error_by_room_type.csv")
    ml_neighbourhood = read_csv("ml_error_by_neighbourhood.csv")
    coverage = read_csv("eda_coverage.csv")
    q_rows = {
        "Q1": len(read_csv("Q1_median_nightly_price_by_neighbourhood_an.csv")),
        "Q2": len(read_csv("Q2_listing_supply_and_host_concentration_by.csv")),
        "Q3": len(read_csv("Q3_availability_rate_and_occupancy_proxy_by.csv")),
        "Q4": len(read_csv("Q4_host_segment_comparison_(casual_vs_profe.csv")),
        "Q5": len(read_csv("Q5_top_and_bottom_10_neighbourhoods_by_list.csv")),
        "Q6": len(read_csv("Q6_distance_to_centre_vs_price_(decile_buck.csv")),
        "Q7": len(read_csv("Q7_listing-level_review_and_price_summary.csv")),
    }
    issues = read_csv("data_quality_issues.csv")
    listings = pd.read_parquet(ROOT / "data/processed/amsterdam/listings_master.parquet")
    quarantine = pd.read_parquet(ROOT / "data/processed/amsterdam/listings_quarantine.parquet")
    profile = json.loads((REPORTS / "profiles/amsterdam/2026-06-15/profile.json").read_text())

    file_inventory = pd.DataFrame(
        [
            {
                "file_key": key,
                "row_count": value["row_count"],
                "column_count": value["column_count"],
            }
            for key, value in profile["files"].items()
        ]
    ).sort_values("file_key")
    price_usable = int(listings["is_price_usable"].sum())
    missing_price = int((~listings["is_price_usable"]).sum())
    missing_share = missing_price / len(listings)
    entire = room[room["room_type"] == "entire home/apt"].iloc[0]
    private = room[room["room_type"] == "private room"].iloc[0]
    hotel = room[room["room_type"] == "hotel room"].iloc[0]
    shared = room[room["room_type"] == "shared room"].iloc[0]
    top_neighbourhoods = neighbourhood.sort_values("median_price", ascending=False).head(3)
    casual = host[host["host_segment"] == "casual"].iloc[0]
    professional = host[host["host_segment"] == "professional"].iloc[0]
    overall_score = review[review["score_column"] == "review_scores_rating"].iloc[0]
    value_score = review[review["score_column"] == "review_scores_value"].iloc[0]
    low_avail = monthly.sort_values("mean_availability_rate").iloc[0]
    high_avail = monthly.sort_values("mean_availability_rate", ascending=False).iloc[0]
    completed_tests = hypothesis[hypothesis["status"] == "completed"]
    unavailable_tests = hypothesis[hypothesis["status"] != "completed"]
    ols_meta = ols.iloc[0]
    max_vif = vif[vif["term"] != "Intercept"].sort_values("vif", ascending=False).iloc[0]
    best_ml = ml.sort_values("mae_original").iloc[0]
    baseline = ml[ml["model_id"] == "M0"].iloc[0]
    top_importance = importance.iloc[0]
    summary_rows = pd.DataFrame(
        [
            {
                "assessment_area": "Source code and README",
                "status": "completed",
                "evidence": "src/, tests/, README.md",
            },
            {
                "assessment_area": "Reproducible execution",
                "status": "completed",
                "evidence": "airbnb-pipeline run; pytest and ruff verified",
            },
            {
                "assessment_area": "Engineering artifacts",
                "status": "completed",
                "evidence": "manifest, profile, validation, Parquet, DuckDB, SQL outputs",
            },
            {
                "assessment_area": "Statistical and ML analysis",
                "status": "completed",
                "evidence": "hypothesis, OLS, and ML result tables",
            },
            {
                "assessment_area": "Optional dashboard",
                "status": "completed locally",
                "evidence": "dashboard_app.py over processed Parquet outputs",
            },
            {
                "assessment_area": "Cross-city analysis",
                "status": "not claimed",
                "evidence": "Amsterdam only; second city remains a configuration extension",
            },
            {
                "assessment_area": "Final PDF submission",
                "status": "owner action",
                "evidence": "Update DOCX fields, inspect pages, export PDF",
            },
        ]
    )

    doc = Document()
    set_styles(doc)
    add_page_number(doc)
    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    title = doc.add_paragraph("Airbnb Market Intelligence Pipeline", "Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for text in [
        "Expernetic Talent Assessment Program - Technical Assignment",
        "Role: Data Engineer Intern",
        "Assignment: Real-World Data Challenge",
        "Amsterdam market analysis and reproducible data product",
        f"City: {CITY}",
        f"Snapshot date: {SNAPSHOT}",
        f"Report generated: {date.today().isoformat()}",
        "Source: Inside Airbnb configured snapshot files",
    ]:
        item = doc.add_paragraph(text)
        item.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph(
        doc,
        "Editable DOCX draft. Update the table of contents in Word and inspect every page "
        "before exporting the PDF.",
    )
    doc.add_page_break()

    paragraph(doc, "Table of Contents", "Heading 1")
    add_toc(doc)
    paragraph(doc, "In Word: right-click the table above and choose Update Field.")
    doc.add_page_break()

    paragraph(doc, "Executive Summary", "Heading 1")
    exec_text = [
        (
            "This report evaluates the Amsterdam Inside Airbnb snapshot as a reproducible "
            "market-intelligence data product rather than as a one-off notebook analysis. "
            "The work starts from configured official source URLs, records provenance and "
            "checksums, profiles and validates staged files, standardises listing records "
            "into Parquet, builds a DuckDB star schema, and then produces exploratory, "
            "statistical, regression, and predictive outputs."
        ),
        (
            "Five conclusions matter for decision-making. First, Amsterdam price structure "
            "is strongly segmented by accommodation type. Second, neighbourhood is a real "
            "market segment, but it should be interpreted alongside room type and property "
            "mix. Third, host structure is broad and fragmented, with many single-listing "
            "hosts and a smaller professional segment. Fourth, guest-rating fields are "
            "concentrated near the top of the scale, so review scores are useful but weak "
            "as a sole quality discriminator. Fifth, the predictive model improves over "
            "the median baseline, but it remains a one-snapshot predictive benchmark and "
            "not evidence of causal price mechanisms or production readiness."
        ),
        (
            "The practical recommendation is to use this pipeline as a defensible analytical "
            "foundation: keep configuration-driven ingestion and lineage controls, report "
            "proxy measures with their caveats, quote medians and confidence intervals "
            "instead of raw averages, and treat model outputs as prioritisation signals. "
            "The optional dashboard is useful for review, but the core deliverable remains "
            "the reproducible batch pipeline and its traceable outputs."
        ),
    ]
    for text in exec_text:
        paragraph(doc, text)
    paragraph(doc, "Key Recommendations", "Heading 2")
    bullets(
        doc,
        [
            "Use room type and neighbourhood together when discussing price bands.",
            (
                "Keep availability_rate separate from confirmed demand. Where occupancy_proxy "
                "appears, state: Derived from host-set availability; not equivalent to "
                "confirmed booked nights."
            ),
            (
                "Treat review_frequency as a demand signal proxy only: Reviews per month "
                "as reported by Inside Airbnb; used as a demand signal proxy only."
            ),
            (
                "Use statistical results for practical prioritisation, not causal claims. "
                "OLS coefficients and ML feature rankings are associations."
            ),
            "Add multi-snapshot or multi-city evidence before production claims.",
        ],
    )
    doc.add_page_break()

    paragraph(doc, "Objectives, Scope, and City Selection", "Heading 1")
    paragraph(
        doc,
        f"The objective is to create a reproducible market-intelligence pipeline for {CITY} "
        f"using the configured Inside Airbnb snapshot dated {SNAPSHOT}. One city is "
        "analysed deeply so the reviewer can trace a result from official source URL "
        "through ingestion, profiling, cleaning, database loading, analysis, and "
        "interpretation.",
    )
    paragraph(
        doc,
        "Amsterdam was selected because the configured source contains the required listing, "
        "calendar, review, neighbourhood, and GeoJSON files. A second city can be added "
        "through configs/cities.yml without changing Python code, but cross-city conclusions "
        "are not made because only Amsterdam has been processed.",
    )
    paragraph(doc, "Assessment Alignment and Prioritisation", "Heading 2")
    paragraph(
        doc,
        "The assessment is intentionally broader than a one-week build. This submission "
        "therefore prioritises defensible depth: source-backed ingestion, validation, "
        "cleaning, a queryable model, tested analysis code, and business-readable reporting. "
        "Optional work was added only where it stayed isolated from the core pipeline.",
    )
    table(
        doc,
        summary_rows,
        "Table 1. Submission readiness summary",
        "Repository files and verification commands",
        10,
    )

    paragraph(doc, "Dataset Overview, Provenance, and Relationships", "Heading 1")
    paragraph(
        doc,
        f"The configured snapshot contains seven official Inside Airbnb files. The profile "
        f"reports {int(file_inventory['row_count'].sum()):,} rows across the file inventory, "
        "including the large calendar and review files. Source: "
        "reports/profiles/amsterdam/2026-06-15/profile.json.",
    )
    table(doc, file_inventory, "Table 2. Configured file inventory", "profile.json", 10)
    paragraph(
        doc,
        "The business entities are listing, host, calendar record, review, and neighbourhood. "
        "Listing is the accommodation offer observed in the snapshot; host is the account "
        "linked to listings; calendar rows record listing-date availability observations "
        "before monthly aggregation; reviews provide listing-level review history; "
        "neighbourhood defines the geographic grouping used by the source.",
    )

    paragraph(doc, "Methodology and Decision Framework", "Heading 1")
    paragraph(
        doc,
        "The methodology favours traceability over breadth. Each material transformation "
        "writes an auditable artifact: manifests record source provenance and checksums, "
        "profiling records schema and missingness, validation writes issue rows, cleaning "
        "writes quarantine records, DuckDB writes query outputs, and analysis writes figures "
        "and tables.",
    )
    paragraph(
        doc,
        "The decision framework is conservative. Unknown values remain null unless a "
        "downstream method explicitly requires a filtered complete-case view. Plausible "
        "extremes are flagged rather than deleted. Proxy measures are labelled as proxies, "
        "and regression or ML outputs are never described as causal evidence.",
    )

    paragraph(doc, "Engineering Architecture and Ingestion Pipeline", "Heading 1")
    paragraph(
        doc,
        "The architecture uses Python, pandas, PyArrow, DuckDB, SciPy, statsmodels, "
        "scikit-learn, Matplotlib, and Streamlit for the optional dashboard. The stack is "
        "intentionally local: no cloud service, orchestration framework, or distributed "
        "system is required for the current scope.",
    )
    paragraph(
        doc,
        "Ingestion downloads configured files to data/raw/<city>/<snapshot>/, stages extracted "
        "CSV/GeoJSON files, records SHA-256 checksums in a manifest, and skips files whose "
        "checksum already matches. The design supports another city by configuration only.",
    )

    paragraph(doc, "Profiling, Validation, Missingness, Duplicates, and Cleaning", "Heading 1")
    paragraph(
        doc,
        f"Profiling and validation found {len(issues):,} row-level issue records. The largest "
        f"visible category is missing listing price: {missing_price:,} listings are not "
        f"price-usable out of {len(listings):,} canonical listing rows ({missing_share:.1%}). "
        "Cleaning retained these listings with null price fields rather than deleting them. "
        "Source: reports/tables/data_quality_issues.csv and listings_master.parquet.",
    )
    paragraph(
        doc,
        f"Cleaning produced {len(listings):,} canonical listing rows and {len(quarantine):,} "
        "quarantined rows. The zero-row quarantine means no listing rows met the hard "
        "exclusion rules after deterministic cleaning; missing price remains null rather "
        "than treated as invalid.",
    )
    table(
        doc, issue_summary(issues), "Table 3. Validation issue summary", "data_quality_issues.csv"
    )

    paragraph(doc, "Star Schema, SQL Queries, and Lineage", "Heading 1")
    paragraph(
        doc,
        "DuckDB loads processed Parquet outputs into a star schema with listing, host, "
        "neighbourhood, date, listing snapshot, and monthly calendar tables. The schema "
        "rebuild is idempotent and query outputs are exported to reports/tables/. Lineage "
        "for every Parquet output and DuckDB table is documented in docs/lineage.md.",
    )
    table(
        doc,
        pd.DataFrame([{"query_output": key, "rows": value} for key, value in q_rows.items()]),
        "Table 4. Business SQL output row counts",
        "reports/tables/Q*.csv",
        10,
    )

    paragraph(doc, "EDA Findings and Business Interpretations", "Heading 1")
    paragraph(
        doc,
        f"Among price-usable listings, entire homes have median nightly price "
        f"{money(entire.median_price)}, private rooms have {money(private.median_price)}, "
        f"hotel rooms have {money(hotel.median_price)}, and shared rooms have "
        f"{money(shared.median_price)}. Population: {price_usable:,} price-usable listings, "
        f"snapshot {SNAPSHOT}. Source: reports/tables/eda_room_type_summary.csv.",
    )
    top_text = ", ".join(
        f"{row.neighbourhood_cleansed} ({money(row.median_price)})"
        for row in top_neighbourhoods.itertuples()
    )
    paragraph(
        doc,
        "The highest median-price neighbourhoods with sufficient sample size are "
        f"{top_text}. Source: reports/tables/eda_neighbourhood_summary.csv.",
    )
    table(doc, room, "Table 5. Price by room type", "eda_room_type_summary.csv", 10)
    table(
        doc,
        neighbourhood[
            [
                "neighbourhood_cleansed",
                "listing_count",
                "median_price",
                "mean_review_score",
                "mean_availability_rate",
            ]
        ],
        "Table 6. Neighbourhood summary excerpt",
        "eda_neighbourhood_summary.csv",
        10,
    )

    figures = [
        ("eda_price_distribution.png", "Price distribution and log-price distribution"),
        ("eda_price_by_room_type.png", "Price by room type"),
        ("eda_price_by_property_type.png", "Price by property type"),
        ("eda_price_by_neighbourhood.png", "Median price by neighbourhood"),
        ("eda_host_portfolio_concentration.png", "Host portfolio concentration"),
        ("eda_host_portfolio_ccdf.png", "Listing count per host"),
        ("eda_review_score_distribution.png", "Review-score distribution"),
        ("eda_review_score_subdimensions.png", "Review-score subdimensions"),
        ("eda_monthly_availability.png", "Monthly availability_rate"),
        ("eda_listing_supply_map.png", "Listing supply map"),
        ("eda_property_type_geography.png", "Geographic mix of property types"),
        ("eda_price_vs_distance.png", "Price versus distance to centre"),
        ("eda_monthly_minimum_nights.png", "Monthly minimum-night policy"),
        ("eda_host_segment_performance.png", "Host segment price and availability"),
        ("eda_superhost_performance.png", "Superhost performance profile"),
        ("eda_review_frequency_relationships.png", "Review frequency relationships"),
        ("eda_review_volume_trend.png", "Review volume trend"),
        ("price_model_residuals_vs_fitted.png", "Residuals versus fitted values"),
        ("price_model_lowess_distance-to-centre-km.png", "LOWESS distance and log price"),
        ("price_model_lowess_minimum-nights.png", "LOWESS minimum nights and log price"),
        ("price_model_lowess_review-scores-rating.png", "LOWESS review score and log price"),
    ]
    figure_captions = {
        "eda_price_distribution.png": (
            f"{CITY}, snapshot {SNAPSHOT}; N={price_usable:,} price-usable listings. "
            "Histogram and log-price view show a right-skewed market, so medians and "
            "log-price statistics are more defensible than raw means for business comparison."
        ),
        "eda_price_by_room_type.png": (
            f"{CITY}, snapshot {SNAPSHOT}; N={price_usable:,} price-usable listings. "
            "Room type is the clearest first split for price bands and should be used before "
            "neighbourhood-level comparisons."
        ),
        "eda_price_by_property_type.png": (
            f"{CITY}, snapshot {SNAPSHOT}; generated from listings_master.parquet. "
            "Property type adds detail inside room-type segments, but sparse categories should "
            "be interpreted as directional rather than definitive."
        ),
        "eda_price_by_neighbourhood.png": (
            f"{CITY}, snapshot {SNAPSHOT}; neighbourhoods pass the minimum sample rule. "
            "Neighbourhood price differences are useful for local strategy, but the mix of "
            "room types and property types must be checked before treating an area as premium."
        ),
        "eda_host_portfolio_concentration.png": (
            f"{CITY}, snapshot {SNAPSHOT}; N={len(listings):,} canonical listings. "
            "Most supply is distributed across many hosts, while a smaller professional segment "
            "still matters for operating patterns and availability."
        ),
        "eda_host_portfolio_ccdf.png": (
            f"{CITY}, snapshot {SNAPSHOT}; host-listing counts shown on a concentration view. "
            "The long tail supports separate handling of casual and multi-listing hosts."
        ),
        "eda_review_score_distribution.png": (
            f"{CITY}, snapshot {SNAPSHOT}; N={int(overall_score.listing_count):,} scored listings. "
            "Scores cluster near the top of the scale, so review score alone is a weak ranking "
            "signal without review volume and price context."
        ),
        "eda_review_score_subdimensions.png": (
            f"{CITY}, snapshot {SNAPSHOT}; scored listing subdimensions from Inside Airbnb. "
            "Value is the more useful warning signal when headline ratings are compressed near 5.0."
        ),
        "eda_monthly_availability.png": (
            f"{CITY}, snapshot {SNAPSHOT}; listing-month records from calendar aggregation. "
            "Availability varies by month, but occupancy_proxy is derived from host-set "
            "availability; not equivalent to confirmed booked nights."
        ),
        "eda_listing_supply_map.png": (
            f"{CITY}, snapshot {SNAPSHOT}; anonymised coordinates rounded for analysis. "
            "The map shows spatial concentration of supply and should be read as approximate "
            "geographic grouping, not exact property location."
        ),
        "eda_property_type_geography.png": (
            f"{CITY}, snapshot {SNAPSHOT}; generated from canonical listing coordinates. "
            "Property mix is geographically uneven, which can explain part of local price "
            "variation without implying location alone drives price."
        ),
        "eda_price_vs_distance.png": (
            f"{CITY}, snapshot {SNAPSHOT}; distance measured from Dam Square. "
            "The central price gradient is visible as an association; it is not a causal location premium."
        ),
        "eda_monthly_minimum_nights.png": (
            f"{CITY}, snapshot {SNAPSHOT}; calendar-derived monthly aggregation. "
            "Minimum-night patterns support operational planning, but event-level claims are not made."
        ),
        "eda_host_segment_performance.png": (
            f"{CITY}, snapshot {SNAPSHOT}; host segments are based on listing count. "
            "Casual and professional hosts show different price and availability profiles, so they "
            "should not be evaluated with one blended benchmark."
        ),
        "eda_superhost_performance.png": (
            f"{CITY}, snapshot {SNAPSHOT}; listings with available superhost flag. "
            "Superhost comparisons are associations and should be interpreted alongside property mix."
        ),
        "eda_review_frequency_relationships.png": (
            f"{CITY}, snapshot {SNAPSHOT}; reviews_per_month from Inside Airbnb. "
            "Review frequency is used as a demand signal proxy only, not observed booking demand."
        ),
        "eda_review_volume_trend.png": (
            f"{CITY}, snapshot {SNAPSHOT}; review dates from staged review records. "
            "Review volume is a lagged demand signal and can be affected by guest review behaviour."
        ),
        "price_model_residuals_vs_fitted.png": (
            f"{CITY}, snapshot {SNAPSHOT}; complete-case OLS rows N={int(ols_meta.n_obs):,}. "
            "Residual spread shows the transparent model is explanatory, not a production pricing engine."
        ),
        "price_model_lowess_distance-to-centre-km.png": (
            f"{CITY}, snapshot {SNAPSHOT}; LOWESS smoother over complete-case OLS rows. "
            "The smoother highlights association between distance and log price without claiming causality."
        ),
        "price_model_lowess_minimum-nights.png": (
            f"{CITY}, snapshot {SNAPSHOT}; LOWESS smoother over complete-case OLS rows. "
            "The shape is useful for diagnostics, but minimum-night policy may be confounded by host type."
        ),
        "price_model_lowess_review-scores-rating.png": (
            f"{CITY}, snapshot {SNAPSHOT}; LOWESS smoother over complete-case OLS rows. "
            "Compressed review scores limit how much rating alone can explain price differences."
        ),
    }
    for index, (filename, title) in enumerate(figures, start=1):
        figure(
            doc,
            index,
            filename,
            title,
            figure_captions[filename],
        )

    paragraph(doc, "Geographic and Temporal Analysis", "Heading 1")
    paragraph(
        doc,
        f"Mean availability_rate is lowest in {low_avail.month} at "
        f"{ratio(low_avail.mean_availability_rate)} and highest in {high_avail.month} "
        f"at {ratio(high_avail.mean_availability_rate)}. The occupancy_proxy is derived "
        "from host-set availability; not equivalent to confirmed booked nights. Source: "
        "reports/tables/eda_monthly_availability.csv.",
    )
    table(
        doc, monthly, "Table 7. Monthly availability summary", "eda_monthly_availability.csv", 13
    )

    paragraph(doc, "Host, Supply, Review, and Demand Signal Proxy Analysis", "Heading 1")
    paragraph(
        doc,
        f"The host table classifies {int(casual.listing_count):,} listings as casual-host "
        f"listings and {int(professional.listing_count):,} as professional-host listings. "
        f"Casual-host listings have median price {money(casual.median_price)}, compared "
        f"with {money(professional.median_price)} for professional-host listings. Source: "
        "reports/tables/eda_host_segment_summary.csv.",
    )
    paragraph(
        doc,
        f"Overall review_scores_rating has mean {number(overall_score['mean'], 2)}, "
        f"median {number(overall_score['median'], 2)}, and "
        f"{ratio(overall_score.share_at_5)} of scored listings at exactly 5.0. Value has "
        f"a lower median of {number(value_score['median'], 2)}. Source: "
        "reports/tables/eda_review_score_summary.csv.",
    )
    table(doc, host, "Table 8. Host segment summary", "eda_host_segment_summary.csv", 5)
    table(doc, review, "Table 9. Review score summary", "eda_review_score_summary.csv", 10)

    paragraph(doc, "Statistical Methodology and Assumption Checks", "Heading 1")
    paragraph(
        doc,
        f"The planned statistical table contains {len(hypothesis):,} rows. "
        f"{len(completed_tests):,} tests were completed and {len(unavailable_tests):,} row "
        "was recorded as unavailable because the staged calendar data lacks a calendar price "
        "field. Benjamini-Hochberg adjusted p-values are reported for completed tests, and "
        "Bonferroni values are included as conservative sensitivity checks.",
    )
    paragraph(
        doc,
        "Welch tests use log price where price is right-skewed. Spearman tests are used for "
        "rank associations. The neighbourhood comparison uses Kruskal-Wallis because there "
        "are many groups and skewed price distributions. Repeated calendar rows were not "
        "treated as independent listing price observations.",
    )
    table(
        doc,
        hypothesis[
            [
                "hypothesis_id",
                "status",
                "sample_size",
                "selected_test",
                "test_statistic",
                "raw_p_value",
                "bh_adjusted_p_value",
                "effect_size_name",
                "effect_size",
            ]
        ],
        "Table 10. Hypothesis result summary",
        "hypothesis_tests.csv",
        7,
    )

    paragraph(doc, "Hypothesis Results and Practical Significance", "Heading 1")
    for row in hypothesis.itertuples(index=False):
        paragraph(doc, f"Finding {row.hypothesis_id}", "Heading 3")
        if row.status == "completed":
            paragraph(
                doc,
                f"Population and context: {row.unit_of_analysis} level analysis with "
                f"N={int(row.sample_size):,}, snapshot {SNAPSHOT}.",
            )
            paragraph(doc, f"Method: {row.selected_test}. {row.test_rationale}")
            paragraph(
                doc,
                f"Result: {row.test_statistic_name}={number(row.test_statistic, 4)}, "
                f"raw p={number(row.raw_p_value, 6)}, BH adjusted p="
                f"{number(row.bh_adjusted_p_value, 6)}, {row.effect_size_name}="
                f"{number(row.effect_size, 4)}, 95% interval: "
                f"{row.confidence_interval_95}.",
            )
            paragraph(doc, f"Caveat: {row.limitation_or_sensitivity}")
            paragraph(doc, f"Business interpretation: {clean_text(row.plain_english_interpretation)}")
        else:
            paragraph(
                doc,
                f"This question is recorded as unavailable. Reason: {row.exclusion_rules} "
                "The report does not substitute listing-level quote price for missing "
                "listing-day calendar prices.",
            )

    paragraph(doc, "OLS Price Association Analysis", "Heading 1")
    paragraph(
        doc,
        f"The transparent statsmodels OLS model uses {int(ols_meta.n_obs):,} complete-case "
        f"rows from {len(listings):,} listings. The model uses log nightly price as the "
        "target and reports HC3 robust standard errors. R-squared is "
        f"{number(ols_meta.r_squared, 3)} and adjusted R-squared is "
        f"{number(ols_meta.adjusted_r_squared, 3)}. Coefficients are marginal associations "
        "in a cross-sectional observational dataset, not causal evidence.",
    )
    paragraph(
        doc,
        f"The largest non-intercept VIF warning is {max_vif.term} with VIF "
        f"{number(max_vif.vif, 2)}. This indicates multicollinearity risk in the encoded "
        "design matrix and should temper coefficient-level interpretation.",
    )
    table(
        doc,
        ols[
            [
                "term",
                "marginal_association",
                "std_error_hc3",
                "p_value",
                "ci_lower",
                "ci_upper",
            ]
        ],
        "Table 11. OLS coefficient excerpt",
        "ols_price_model.csv",
        12,
    )
    table(doc, vif[["term", "vif", "warning"]], "Table 12. VIF diagnostics", "vif.csv", 12)
    table(doc, ols_limits, "Table 13. OLS limitations", "ols_price_model_limitations.csv", 8)

    paragraph(doc, "ML Problem Framing and Feature Engineering", "Heading 1")
    paragraph(
        doc,
        f"The ML experiment estimates price_log for {price_usable:,} price-usable listing "
        f"rows, using {int(best_ml.n_train):,} training rows and {int(best_ml.n_test):,} "
        "test rows. Features exclude identifiers, raw price, parsed price, log price as a "
        "feature, revenue_proxy, occupancy_proxy, availability_rate, and review_frequency. "
        "Source: reports/ml_model_card.md and reports/tables/ml_experiment_results.csv.",
    )
    paragraph(
        doc,
        "The feature set includes room type, property type, bedrooms, bathrooms, accommodates, "
        "capped minimum nights, long-stay flag, distance to centre, superhost flag, "
        "neighbourhood, amenity count, and six amenity flags. Numeric imputation and "
        "categorical encoding occur inside scikit-learn pipelines fitted on training data.",
    )

    paragraph(doc, "ML Comparison and Error Analysis", "Heading 1")
    paragraph(
        doc,
        f"The best test MAE is {money(best_ml.mae_original)} from {best_ml.model_name}, "
        f"compared with {money(baseline.mae_original)} for the median baseline. Test RMSE "
        f"for the best model is {money(best_ml.rmse_original)} and log-scale R-squared is "
        f"{number(best_ml.r2_log, 3)}. Source: reports/tables/ml_experiment_results.csv.",
    )
    paragraph(
        doc,
        f"The top permutation-importance feature is {top_importance.feature} with mean "
        f"importance {number(top_importance.permutation_importance_mean, 4)}. Feature "
        "importance is predictive association, not causal evidence.",
    )
    table(
        doc,
        ml[
            [
                "model_id",
                "model_name",
                "n_train",
                "n_test",
                "cv_mae_log_mean",
                "cv_mae_log_std",
                "mae_original",
                "rmse_original",
                "r2_log",
            ]
        ],
        "Table 14. ML model comparison",
        "ml_experiment_results.csv",
        5,
    )
    table(
        doc,
        importance[
            [
                "model_id",
                "model_name",
                "feature",
                "permutation_importance_mean",
                "permutation_importance_std",
            ]
        ],
        "Table 15. ML feature importance",
        "ml_feature_importance.csv",
        10,
    )
    table(doc, ml_room, "Table 16. ML error by room type", "ml_error_by_room_type.csv", 8)
    table(
        doc,
        ml_neighbourhood,
        "Table 17. ML error by neighbourhood excerpt",
        "ml_error_by_neighbourhood.csv",
        10,
    )

    paragraph(doc, "Optional Dashboard and Responsible AI/ML Boundary", "Heading 1")
    paragraph(
        doc,
        "The optional Streamlit dashboard is a local review surface over generated processed "
        "Parquet outputs only. It includes neighbourhood and room-type filters, KPI cards, "
        "price distribution, supply and price tables, availability trend, and an "
        "interpretation panel. The property-type filter is documented as unavailable unless "
        "property_type becomes part of a generated processed output.",
    )
    paragraph(
        doc,
        "Responsible AI/ML boundaries are explicit: no external LLM interface is added, no "
        "model is described as production-ready, feature importance is not causal evidence, "
        "and leakage-prone fields are excluded from price prediction.",
    )

    paragraph(doc, "Business Recommendations", "Heading 1")
    numbered(
        doc,
        [
            "Segment pricing decisions by room type first, then neighbourhood.",
            "Use median, quartile, and log-price summaries for price communication.",
            "Treat professional hosts and casual hosts as different operating segments.",
            "Use review score cautiously and combine it with review count, location, and price.",
            "Use ML as a triage and scenario tool, not a final pricing engine.",
        ],
    )

    paragraph(doc, "Cross-City Extension and Harmonisation", "Heading 1")
    paragraph(
        doc,
        "Dublin has not been processed in this repository. The configuration file includes a "
        "commented template showing that a second city can be added without Python code "
        "changes. A future cross-city comparison must document dataset size, snapshot recency, "
        "coverage, renamed columns, type differences, missing fields, encoding differences, "
        "and the canonical schema before combining outputs.",
    )

    paragraph(doc, "Limitations and Caveats", "Heading 1")
    bullets(
        doc,
        [
            f"Single snapshot: all results describe {CITY} at snapshot {SNAPSHOT}.",
            (
                "Availability data is host-set availability. occupancy_proxy is derived "
                "from host-set availability; not equivalent to confirmed booked nights."
            ),
            "revenue_proxy is estimated from availability proxy and calendar price; not observed revenue.",
            (
                "review_frequency is reviews per month as reported by Inside Airbnb; used "
                "as a demand signal proxy only."
            ),
            "Coordinates are anonymised and rounded to five decimal places.",
            "OLS and ML are observational, cross-sectional analyses.",
            "Host tenure and host response-rate analyses are unavailable because fields are empty.",
            "The model is trained and evaluated on one city snapshot.",
        ],
    )

    paragraph(doc, "Future Improvements and 50+ City Scaling", "Heading 1")
    paragraph(
        doc,
        "For 50+ cities, the local design should evolve into partitioned object storage, "
        "city/snapshot partitioned Parquet, scheduled ingestion, data-quality gates, metadata "
        "tables, retries, alerting, and SLA tracking. A production system would store raw "
        "source bytes by city, snapshot date, file key, and checksum; build curated Parquet "
        "partitions; load analytical views into DuckDB or a warehouse; and serve dashboards "
        "from curated outputs only.",
    )
    paragraph(
        doc,
        "CDC strategy: compute stable row hashes for listing records by snapshot, compare "
        "listing_id plus snapshot_date across runs, mark inserted, changed, unchanged, and "
        "removed listings, and upsert only changed rows into curated tables. Calendar outputs "
        "should rebuild only affected listing-month or listing-date partitions.",
    )

    paragraph(doc, "Reflection on Prioritisation, Trade-offs, and AI Collaboration", "Heading 1")
    paragraph(
        doc,
        "The strongest prioritisation choice was to analyse one city deeply rather than create "
        "a shallow multi-city comparison. That allowed the project to build ingestion, "
        "validation, cleaning, SQL, statistics, ML, and dashboard outputs with traceable "
        "evidence. The main trade-off is narrower geographic coverage.",
    )
    paragraph(
        doc,
        "AI tools assisted with drafting, implementation, report assembly, and validation "
        "checks, but the developer set the scope, challenged leakage risks, required repeated "
        "verification, rejected weak shortcuts, and kept manual commit control.",
    )

    paragraph(doc, "Completed and Incomplete Work Summary", "Heading 1")
    table(doc, coverage, "Table 18. Analysis coverage summary", "eda_coverage.csv", 25)
    paragraph(
        doc,
        "Completed work includes configuration-driven ingestion, profiling, validation, "
        "deterministic cleaning, enrichment, DuckDB loading, business SQL outputs, EDA figures "
        "and interpretations, hypothesis tests, OLS diagnostics, ML benchmark, optional "
        "dashboard, documentation, and this report draft. Remaining owner actions include "
        "PDF export inspection, private repository access verification, and the final "
        "submission email.",
    )

    paragraph(doc, "Appendix A: Evidence and Artifact Index", "Heading 1")
    table(
        doc,
        pd.DataFrame(
            [
                {
                    "artifact": "README and run order",
                    "path": "README.md",
                    "purpose": "Reviewer setup and reproduction entry point",
                },
                {
                    "artifact": "City configuration",
                    "path": "configs/cities.yml",
                    "purpose": "Official source URLs and snapshot date",
                },
                {
                    "artifact": "Data dictionary",
                    "path": "docs/data_dictionary.md",
                    "purpose": "Per-file schema, grain, and field interpretation",
                },
                {
                    "artifact": "Assumptions and decisions",
                    "path": "docs/assumptions.md; docs/decision_log.md",
                    "purpose": "Ambiguities, scope choices, and trade-offs",
                },
                {
                    "artifact": "Lineage",
                    "path": "docs/lineage.md",
                    "purpose": "Source-to-output traceability",
                },
                {
                    "artifact": "Quality reports",
                    "path": "reports/data_quality_report.md; reports/validation_report.json",
                    "purpose": "Profiling, validation, issues, duplicates, and outliers",
                },
                {
                    "artifact": "Business query outputs",
                    "path": "reports/tables/Q*.csv",
                    "purpose": "SQL-backed business summaries",
                },
                {
                    "artifact": "Analysis outputs",
                    "path": "reports/tables/*.csv; reports/figures/*.png",
                    "purpose": "EDA, statistics, OLS, and ML evidence",
                },
                {
                    "artifact": "Dashboard",
                    "path": "dashboard_app.py",
                    "purpose": "Local optional review dashboard over processed outputs",
                },
            ]
        ),
        "Table 19. Evidence and artifact index",
        "Repository files",
        20,
    )

    paragraph(doc, "Appendix B: AI Usage Disclosure", "Heading 1")
    paragraph(
        doc,
        "This appendix is sourced from docs/ai_usage_disclosure.md. It records AI-assisted "
        "sections, validation steps, modifications, rejected suggestions, and the developer's "
        "active scope and acceptance decisions.",
    )
    disclosure = (ROOT / "docs/ai_usage_disclosure.md").read_text(encoding="utf-8")
    for block in disclosure.split("\n\n"):
        text = block.strip()
        if not text:
            continue
        if text.startswith("### "):
            paragraph(doc, text.removeprefix("### ").strip(), "Heading 3")
        elif text.startswith("## "):
            paragraph(doc, text.removeprefix("## ").strip(), "Heading 2")
        elif text.startswith("# "):
            paragraph(doc, text.removeprefix("# ").strip(), "Heading 2")
        else:
            paragraph(doc, text.replace("\n", " "))

    paragraph(doc, "Appendix C: Interview Preparation Notes", "Heading 1")
    numbered(
        doc,
        [
            "One city was analysed deeply to maximise traceability and reviewer confidence.",
            "DuckDB was selected because it scans Parquet efficiently on a local machine.",
            "Availability is not called occupancy because the source records host-set availability.",
            "Duplicate detection uses exact identifiers and conservative blocked fuzzy candidates.",
            "Missing values remain null unless a method uses an explicit complete-case filter.",
            "Repeated calendar rows are not treated as independent listing price rows.",
            "Log price was used because nightly price is right-skewed.",
            "ML leakage was prevented by excluding price-derived and future-calendar fields.",
            "For 50+ cities, add partitioning, snapshot hashes, quality gates, and monitoring.",
            "Rejected AI suggestions included invented fields, broad frameworks, and leakage-prone features.",
            "The strongest business finding is segmentation by room type and neighbourhood.",
            "The biggest confidence limitation is the single-snapshot design.",
        ],
    )

    paragraph(doc, "References", "Heading 1")
    bullets(
        doc,
        [
            "Inside Airbnb configured Amsterdam source URLs in configs/cities.yml.",
            "Generated profile: reports/profiles/amsterdam/2026-06-15/profile.json.",
            "Generated validation output: reports/validation_report.json.",
            "Generated tables: reports/tables/*.csv.",
            "Generated figures: reports/figures/*.png.",
            "Project documentation under docs/.",
        ],
    )

    DOCX_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(DOCX_PATH)

    markdown = [
        "# Airbnb Market Intelligence Pipeline",
        "",
        f"City: {CITY}",
        f"Snapshot date: {SNAPSHOT}",
        f"Report generated: {date.today().isoformat()}",
        "",
        "This Markdown source accompanies `reports/Airbnb_Market_Intelligence_Report.docx`.",
        "",
        "## Executive Summary",
        "",
        *exec_text,
        "",
        "## Core Evidence",
        "",
        f"- Canonical listings: {len(listings):,}",
        f"- Price-usable listings: {price_usable:,}",
        f"- Quarantined rows: {len(quarantine):,}",
        f"- Completed statistical tests: {len(completed_tests):,}",
        f"- Best ML MAE: {money(best_ml.mae_original)}",
        f"- OLS R-squared: {number(ols_meta.r_squared, 3)}",
        "",
        "## Figure Register",
        "",
        *[f"- Figure {index}: `{filename}`" for index, (filename, _) in enumerate(figures, 1)],
    ]
    MD_PATH.write_text("\n".join(markdown), encoding="utf-8")

    with zipfile.ZipFile(DOCX_PATH) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
    print(f"docx={DOCX_PATH}")
    print(f"markdown={MD_PATH}")
    print(f"embedded_media={len(media)}")
    print(f"paragraphs={len(doc.paragraphs)}")
    print(f"tables={len(doc.tables)}")


if __name__ == "__main__":
    build()
