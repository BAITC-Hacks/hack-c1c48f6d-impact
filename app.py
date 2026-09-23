import pandas as pd
import streamlit as st
from src.config import Settings
from src.pipeline import run_pipeline
from src.export import to_csv_bytes, to_excel_bytes
from src.diagnostics import calculation_diagnostics
from src.presentation import display_value, representative_examples, warning_labels

st.set_page_config(page_title="Supplier Replenishment", page_icon="📦", layout="wide")
st.title("📦 Explainable supplier replenishment")
st.caption(
    "Deterministic recommendations from the supplied partner Excel workbooks — no LLM quantity calculation."
)
st.warning(
    "Customer-specific bulk-order detection is supported by the architecture but cannot currently be evaluated because customer identifiers are not present in the supplied datasets."
)
with st.sidebar:
    st.header("Planning settings")
    demo_mode = st.checkbox(
        "Demo mode",
        help="Offers representative examples selected from the current calculated results.",
    )
    with st.expander("Forecast & replenishment", expanded=True):
        horizon = st.slider("Replenishment horizon (days)", 15, 120, 45)
        lead = st.slider(
            "Lead time assumption (days)",
            7,
            90,
            30,
            help="No explicit supplier lead time is present; this is a configurable demo assumption.",
        )
        service = st.slider("Safety-stock service factor", 0.0, 2.5, 1.28, 0.05)
        stockout = st.slider(
            "Estimated stockout-month fraction",
            0.0,
            1.0,
            0.35,
            0.05,
            help="Monthly snapshots do not prove a full-month stockout.",
        )
        outlier = st.slider("One-off robust z threshold", 3.0, 10.0, 5.0, 0.5)


@st.cache_data(show_spinner="Loading and normalizing real workbooks…")
def load_dashboard(horizon, lead, service, stockout, outlier):
    return run_pipeline(
        Settings(
            horizon_days=horizon,
            lead_time_days=lead,
            service_factor=service,
            stockout_fraction=stockout,
            outlier_z=outlier,
        )
    )


data = load_dashboard(horizon, lead, service, stockout, outlier)
rec = data["recommendations"].copy()
demo_examples = representative_examples(rec) if demo_mode else {}
demo_selected = None
if demo_mode:
    st.sidebar.subheader("Representative examples")
    if demo_examples:
        demo_label = st.sidebar.selectbox("Example", list(demo_examples))
        demo_selected = demo_examples[demo_label]
        st.sidebar.caption(f"Selected from calculated data: {demo_selected}")
    else:
        st.sidebar.info("No representative examples match the current calculations.")
st.subheader("Filters")
c1, c2, c3, c4 = st.columns(4)
supplier = c1.selectbox("Supplier", ["All", "SystemElectric", "IEK"])
search = c2.text_input("SKU / product search")
categories = sorted(rec["category"].dropna().astype(str).unique())
category = c3.selectbox("Category", ["All", *categories])
urgencies = c4.multiselect(
    "Urgency",
    ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
    default=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
)
filtered = rec.copy()
if supplier != "All":
    filtered = filtered[filtered.supplier.eq(supplier)]
if search:
    filtered = filtered[
        filtered.sku.astype(str).str.contains(search, case=False, na=False)
        | filtered.product_name.astype(str).str.contains(search, case=False, na=False)
    ]
if category != "All":
    filtered = filtered[filtered.category.astype(str).eq(category)]
filtered = filtered[filtered.urgency.isin(urgencies)]
metrics = st.columns(6)
vals = [
    len(filtered),
    (filtered.recommended_order_qty > 0).sum(),
    filtered.urgency.eq("CRITICAL").sum(),
    filtered.recommended_order_qty.sum(),
    filtered.anomaly_count.sum(),
    (filtered.estimated_lost_demand > 0).sum(),
]
labels = [
    "SKUs analyzed",
    "SKUs to order",
    "Critical",
    "Recommended units",
    "Anomaly days",
    "Stockout-adjusted SKUs",
]
for box, label, value in zip(metrics, labels, vals):
    box.metric(label, f"{value:,.0f}")
show = pd.DataFrame(
    {
        "Supplier": filtered.supplier,
        "SKU": filtered.sku,
        "Article": filtered.supplier_article.fillna("Not available"),
        "Product": filtered.product_name.fillna("Not available"),
        "Category": filtered.category.fillna("Not available"),
        "Forecast": filtered.forecast_monthly,
        "Available": filtered.free_stock.mask(filtered.current_stock_missing),
        "Inbound": filtered.in_transit_before_required_date,
        "Raw need": filtered.recommended_raw_qty,
        "MOQ": filtered.order_multiple,
        "Order": filtered.recommended_order_qty,
        "Urgency": filtered.urgency,
        "Warnings": filtered.apply(warning_labels, axis=1),
    }
)
st.subheader("Recommendations")
st.dataframe(
    show.sort_values(["Urgency", "Order"], ascending=[True, False]).style.format(
        {
            "Forecast": "{:,.1f}",
            "Available": "{:,.1f}",
            "Inbound": "{:,.1f}",
            "Raw need": "{:,.1f}",
            "MOQ": "{:,.0f}",
            "Order": "{:,.0f}",
        },
        na_rep="Not available",
    ),
    use_container_width=True,
    hide_index=True,
)
e1, e2 = st.columns(2)
e1.download_button(
    "Download CSV", to_csv_bytes(filtered), "recommendations.csv", "text/csv"
)
e2.download_button(
    "Download Excel",
    to_excel_bytes(filtered),
    "recommendations.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
st.subheader("SKU detail")
detail_rows = rec if demo_selected else filtered
options = (detail_rows.supplier + " · " + detail_rows.sku.astype(str)).tolist()
default_index = options.index(demo_selected) if demo_selected in options else 0
selected = st.selectbox("Select SKU", options, index=default_index) if options else None
if selected:
    supp, sku = selected.split(" · ", 1)
    row = detail_rows[(detail_rows.supplier == supp) & (detail_rows.sku == sku)].iloc[0]
    missing = []
    if row.product_metadata_missing:
        missing.append("Product metadata is incomplete for this SKU.")
    if row.current_stock_missing:
        missing.append("Current stock is unavailable; zero is used in the calculation.")
    if row.moq_missing:
        missing.append("MOQ is unavailable; fallback multiple 1 is used.")
    for message in missing:
        st.warning(message)
    st.info(row.rationale)
    a, b, c, d = st.columns(4)
    a.metric("Growth factor", f"{row.calculated_growth_coefficient:.2f}")
    b.metric("Seasonality", f"{row.calculated_seasonality_coefficient:.2f}")
    c.metric("Safety stock", f"{row.safety_stock:,.1f}")
    d.metric("Days of supply", row.days_of_supply_display)
    hist = data["demand_adjusted"]
    hist = hist[(hist.supplier == supp) & (hist.sku == sku)].set_index("month")
    if hist.empty:
        st.info("No historical demand series is available for this SKU.")
    elif (
        not hist[["quantity", "cleaned_quantity", "adjusted_quantity"]]
        .fillna(0)
        .gt(0)
        .any()
        .any()
    ):
        st.info("Historical demand is present but contains no positive regular demand.")
    else:
        st.markdown("#### Demand cleaning and stockout adjustment")
        st.caption("Monthly demand history")
        demand_chart = hist[
            ["quantity", "cleaned_quantity", "adjusted_quantity"]
        ].rename(
            columns={
                "quantity": "Raw demand",
                "cleaned_quantity": "Cleaned demand",
                "adjusted_quantity": "Stockout-adjusted demand",
            }
        )
        st.line_chart(demand_chart)
        st.caption(
            "Raw/reconciled monthly demand, anomaly-cleaned demand, and conservative stockout-adjusted demand."
        )
    stock = data["monthly_stock"]
    stock = stock[(stock.supplier == supp) & (stock.sku == sku)].set_index("month")
    if stock.empty:
        st.info("No monthly stock history is available for this SKU.")
    else:
        st.markdown("#### Monthly stock history")
        st.line_chart(stock["stock_level"])
    st.write("Inbound shipments")
    shipments = data["inbound"][
        (data["inbound"].supplier == supp) & (data["inbound"].sku == sku)
    ]
    shipments = shipments[shipments["quantity"].fillna(0).gt(0)]
    if shipments.empty:
        st.info("No inbound shipments found for this SKU.")
    else:
        st.dataframe(
            shipments.style.format({"quantity": "{:,.1f}"}, na_rep="Not available"),
            hide_index=True,
            use_container_width=True,
        )
    st.markdown("#### Business calculation")
    st.info(
        "**Target requirement** = forecast demand + safety stock − available stock "
        "− eligible inbound\n\n**Final order** = raw requirement rounded up to MOQ"
    )
    with st.expander("Why this recommendation?", expanded=demo_mode):
        trend = (
            "growth"
            if row.calculated_growth_coefficient > 1.05
            else ("decline" if row.calculated_growth_coefficient < 0.95 else "stable")
        )
        seasonality = (
            "uplift"
            if row.calculated_seasonality_coefficient > 1.05
            else (
                "reduction"
                if row.calculated_seasonality_coefficient < 0.95
                else "neutral"
            )
        )
        st.markdown(
            f"- **Anomaly adjustment:** {display_value(row.outlier_quantity_removed)} units removed\n"
            f"- **Trend:** {trend} ({row.calculated_growth_coefficient:.2f}×)\n"
            f"- **Seasonality:** {seasonality} ({row.calculated_seasonality_coefficient:.2f}×)\n"
            f"- **Stockout adjustment:** {display_value(row.estimated_lost_demand)} units\n"
            f"- **Current/free stock:** {display_value(row.free_stock) if not row.current_stock_missing else 'Not available (zero fallback)'}\n"
            f"- **Eligible inbound:** {display_value(row.in_transit_before_required_date)} units\n"
            f"- **Decision:** order **{display_value(row.recommended_order_qty, 0)} units** "
            f"from a raw need of {display_value(row.recommended_raw_qty)}."
        )
    with st.expander("Calculation diagnostics"):
        diagnostic = calculation_diagnostics(data, supp, sku)
        labels = {
            "raw_sales_total": "Raw sales total",
            "cleaned_sales_total": "Cleaned sales total",
            "baseline_demand": "Baseline demand",
            "adjusted_demand": "Adjusted demand",
            "outlier_quantity_removed": "Outlier adjustment",
            "stockout_adjustment": "Stockout adjustment",
            "growth_factor": "Growth factor",
            "seasonality_factor": "Seasonality factor",
            "forecast_horizon_days": "Forecast horizon (days)",
            "lead_time_days": "Lead-time assumption (days)",
            "safety_stock": "Safety stock",
            "available_stock": "Available stock",
            "eligible_inbound": "Eligible inbound",
            "raw_requirement": "Raw requirement",
            "moq": "MOQ",
            "rounded_order": "Rounded order",
        }
        factor_keys = {"growth_factor", "seasonality_factor"}
        whole_keys = {"forecast_horizon_days", "lead_time_days", "moq", "rounded_order"}
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Metric": label,
                        "Value": display_value(
                            diagnostic[key],
                            2
                            if key in factor_keys
                            else (0 if key in whole_keys else 1),
                        ),
                    }
                    for key, label in labels.items()
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
with st.expander("Data quality report"):
    st.dataframe(data["quality"], hide_index=True, use_container_width=True)
