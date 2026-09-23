import pandas as pd


def build_rationale(row):
    multiple = row.get("order_multiple", 1)
    moq_missing = bool(row.get("moq_missing", False))
    if pd.isna(multiple) or float(multiple) <= 0:
        multiple, moq_missing = 1, True
    safety_text = (
        "safety stock is unavailable because history is insufficient"
        if row.get("variability_insufficient", False)
        else f"safety stock is {row['safety_stock']:.1f}"
    )
    text = (
        f"Recommend {row['recommended_order_qty']:.0f} units. Forecast demand is "
        f"{row['demand_during_horizon']:.1f} units; {safety_text}; "
        f"free/current stock is {row['free_stock']:.1f}; reserved stock is {row.get('reserved_stock', 0):.1f}; "
        f"eligible inbound is {row['in_transit_before_required_date']:.1f}. Raw requirement is "
        f"{row['recommended_raw_qty']:.1f}; MOQ is {float(multiple):.0f}; final rounded recommendation is "
        f"{row['recommended_order_qty']:.0f} units."
    )
    context = []
    if row.get("calculated_growth_coefficient", 1) > 1.05:
        context.append("sustained growth increases demand")
    if row.get("calculated_seasonality_coefficient", 1) > 1.05:
        context.append("seasonal uplift applied")
    elif row.get("calculated_seasonality_coefficient", 1) < 0.95:
        context.append("seasonal reduction applied")
    if row.get("estimated_lost_demand", 0) > 0:
        context.append("conservative stockout lost-demand estimate included")
    if row.get("anomaly_count", 0) > 0:
        context.append(
            f"{int(row['anomaly_count'])} quantity anomaly day(s) excluded from regular demand"
        )
    if moq_missing:
        context.append("MOQ unavailable; fallback multiple 1 used")
    if row.get("current_stock_missing", False):
        context.append("current stock unavailable; zero used")
    if row.get("variability_insufficient", False):
        context.append(
            "safety stock unavailable because history is insufficient; no variability was invented"
        )
    return text + (" Context: " + "; ".join(context) + "." if context else "")
