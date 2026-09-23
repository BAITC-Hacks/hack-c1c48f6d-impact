

def estimate_stockout_demand(demand, stock, fraction=0.35):
    merged = demand.merge(
        stock[["supplier", "sku", "month", "stock_level"]],
        on=["supplier", "sku", "month"],
        how="left",
    )
    base = merged.get("cleaned_quantity", merged["quantity"]).clip(lower=0)
    merged["potential_stockout"] = (
        merged["stock_level"].le(0) & merged["stock_level"].notna()
    )
    merged["estimated_lost_demand"] = (
        base.where(merged["potential_stockout"], 0) * fraction
    )
    merged["adjusted_quantity"] = base + merged["estimated_lost_demand"]
    return merged
