import pandas as pd


def data_quality_report(products, monthly_sales, inventory, inbound, transactions):
    p = set(products["sku"].dropna())
    s = set(monthly_sales["sku"].dropna())
    i = set(inventory["sku"].dropna())
    t = set(inbound["sku"].dropna())
    checks = {
        "sales_missing_moq": s - p,
        "moq_missing_sales": p - s,
        "missing_current_inventory": p - i,
        "missing_transit": p - t,
    }
    rows = [
        {"check": k, "count": len(v), "sample_skus": ", ".join(sorted(v)[:8])}
        for k, v in checks.items()
    ]
    rows += [
        {
            "check": "duplicate_product_skus",
            "count": int(products.duplicated(["supplier", "sku"]).sum()),
            "sample_skus": "",
        },
        {
            "check": "invalid_transaction_dates",
            "count": int(transactions["date"].isna().sum()),
            "sample_skus": "",
        },
        {
            "check": "invalid_transaction_quantities",
            "count": int(transactions["raw_quantity"].isna().sum()),
            "sample_skus": "",
        },
    ]
    return pd.DataFrame(rows)
