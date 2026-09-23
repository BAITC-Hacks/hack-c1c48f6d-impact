import pandas as pd


def calculation_diagnostics(data, supplier, sku):
    """Return an auditable forecast trace for one normalized supplier/SKU key."""
    rec = data["recommendations"]
    match = rec[rec["supplier"].eq(supplier) & rec["sku"].eq(sku)]
    if match.empty:
        return None
    row = match.iloc[0]
    history = data["demand_adjusted"]
    history = history[
        history["supplier"].eq(supplier) & history["sku"].eq(sku)
    ].sort_values("month")
    raw_sales_total = float(history.get("quantity", pd.Series(dtype=float)).sum())
    cleaned_sales_total = float(
        history.get("cleaned_quantity", pd.Series(dtype=float)).sum()
    )
    return {
        "raw_sales_total": raw_sales_total,
        "cleaned_sales_total": cleaned_sales_total,
        "outlier_quantity_removed": max(0.0, raw_sales_total - cleaned_sales_total),
        "monthly_demand_series": history[
            [
                column
                for column in (
                    "month",
                    "quantity",
                    "cleaned_quantity",
                    "adjusted_quantity",
                )
                if column in history
            ]
        ],
        "baseline_demand": row.baseline_demand,
        "adjusted_demand": row.adjusted_demand,
        "growth_factor": row.calculated_growth_coefficient,
        "seasonality_factor": row.calculated_seasonality_coefficient,
        "stockout_adjustment": row.stockout_adjustment,
        "final_forecast": row.forecast_monthly,
        "forecast_horizon_days": row.forecast_horizon_days,
        "lead_time_days": row.lead_time_days,
        "safety_stock": row.safety_stock,
        "available_stock": row.free_stock,
        "eligible_inbound": row.in_transit_before_required_date,
        "raw_requirement": row.recommended_raw_qty,
        "moq": row.order_multiple,
        "rounded_order": row.recommended_order_qty,
    }
