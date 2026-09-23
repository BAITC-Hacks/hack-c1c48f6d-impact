def estimate_stockout_demand(demand, stock, fraction=0.35):
    """Estimate, never assert, lost demand using up to six nearby regular months."""
    merged = demand.merge(
        stock[["supplier", "sku", "month", "stock_level"]],
        on=["supplier", "sku", "month"],
        how="left",
    )
    base = merged.get("cleaned_quantity", merged["quantity"]).clip(lower=0)
    merged["potential_stockout"] = (
        merged["stock_level"].le(0) & merged["stock_level"].notna()
    )
    merged["stockout_reference_demand"] = 0.0
    for _, indexes in merged.groupby(["supplier", "sku"]).groups.items():
        group = merged.loc[indexes]
        regular = group.loc[
            ~group["potential_stockout"] & base.loc[indexes].gt(0), ["month"]
        ].copy()
        regular["demand"] = base.loc[regular.index]
        for index in group.index[group["potential_stockout"] & base.loc[indexes].eq(0)]:
            nearby = regular.assign(
                distance=(regular["month"] - merged.at[index, "month"]).abs()
            ).nsmallest(6, "distance")
            if not nearby.empty:
                merged.at[index, "stockout_reference_demand"] = float(
                    nearby["demand"].median()
                )
    expected = base.where(base.gt(0), merged["stockout_reference_demand"])
    merged["estimated_lost_demand"] = expected.where(
        merged["potential_stockout"], 0
    ) * max(0, float(fraction))
    merged["adjusted_quantity"] = base + merged["estimated_lost_demand"]
    return merged
