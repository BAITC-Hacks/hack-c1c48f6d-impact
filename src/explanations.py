def build_rationale(row):
    text = (
        f"Recommend {row['recommended_order_qty']:.0f} units. Forecast demand for the replenishment horizon is "
        f"{row['demand_during_horizon']:.1f} units and safety stock is {row['safety_stock']:.1f}. Available/free stock is "
        f"{row['free_stock']:.1f}; {row['in_transit_before_required_date']:.1f} inbound units arrive by the required date. "
        f"Net requirement is {row['recommended_raw_qty']:.1f}, rounded up to shipment multiple {row['order_multiple']:.0f}."
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
    return text + (" Context: " + "; ".join(context) + "." if context else "")
