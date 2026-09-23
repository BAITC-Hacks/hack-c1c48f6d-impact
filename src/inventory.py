import pandas as pd


def latest_iek_inventory(stock):
    valid = (
        stock.dropna(subset=["stock_level"])
        .sort_values("month")
        .groupby(["supplier", "sku"], as_index=False)
        .tail(1)
    )
    return valid.rename(
        columns={"stock_level": "current_stock", "month": "stock_snapshot_date"}
    ).assign(
        reserved_stock=0.0,
        free_stock=lambda x: x.current_stock,
        inventory_source="latest_available_stock_snapshot",
    )


def summarize_inbound(inbound, required_date):
    if inbound.empty:
        return pd.DataFrame(
            columns=[
                "supplier",
                "sku",
                "total_in_transit",
                "in_transit_before_required_date",
            ]
        )
    x = inbound.copy()
    x["eligible"] = x["quantity"].where(
        x["expected_arrival_date"].le(pd.Timestamp(required_date)), 0
    )
    return x.groupby(["supplier", "sku"], as_index=False).agg(
        total_in_transit=("quantity", "sum"),
        in_transit_before_required_date=("eligible", "sum"),
    )
