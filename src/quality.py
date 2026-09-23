import pandas as pd


def data_quality_report(products, monthly_sales, inventory, inbound, transactions):
    def keys(frame):
        return set(map(tuple, frame[["supplier", "sku"]].dropna().to_numpy()))

    def samples(values):
        return ", ".join(f"{supplier}:{sku}" for supplier, sku in sorted(values)[:8])

    p, s, i, t = map(keys, (products, monthly_sales, inventory, inbound))
    checks = {
        "sales_missing_moq": s - p,
        "moq_missing_sales": p - s,
        "missing_current_inventory": p - i,
        "missing_transit": p - t,
    }
    invalid_moq = (
        keys(products[products["moq_missing"]]) if "moq_missing" in products else set()
    )
    missing_moq = (s - p) | invalid_moq
    rows = [
        {"check": k, "count": len(v), "sample_skus": samples(v)}
        for k, v in checks.items()
    ]
    rows += [
        {
            "check": "missing_or_invalid_moq",
            "count": len(missing_moq),
            "sample_skus": samples(missing_moq),
        },
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
