import numpy as np
import pandas as pd


def detect_one_off_orders(transactions, z_threshold=5.0, customer_id_column=None):
    """Flag high daily demand relative to the SKU itself; customer hook is reserved."""
    tx = transactions.copy()
    tx["day"] = tx["date"].dt.normalize()
    daily = (
        tx.groupby(["supplier", "sku", "day"], as_index=False)["normalized_sales_qty"]
        .sum()
        .rename(columns={"normalized_sales_qty": "daily_demand"})
    )

    def score(group):
        x = group["daily_demand"].astype(float)
        med = x.median()
        mad = (x - med).abs().median()
        if mad > 0:
            robust_z = 0.6745 * (x - med) / mad
            flag = robust_z > z_threshold
            reason = "daily demand exceeds per-SKU MAD threshold"
        else:
            q1, q3 = x.quantile([0.25, 0.75])
            iqr = q3 - q1
            threshold = q3 + 3 * iqr if iqr > 0 else max(med * 5, med + 1)
            robust_z = pd.Series(np.nan, index=x.index)
            flag = x > threshold
            reason = "daily demand exceeds per-SKU IQR/ratio fallback"
        group = group.copy()
        group["robust_z"] = robust_z
        group["is_one_off_order"] = flag
        group["outlier_reason"] = np.where(flag, reason, "")
        return group

    if daily.empty:
        return daily.assign(
            robust_z=pd.Series(dtype=float),
            is_one_off_order=pd.Series(dtype=bool),
            outlier_reason=pd.Series(dtype=str),
        )
    return (
        daily.groupby(["supplier", "sku"], group_keys=False)
        .apply(score)
        .reset_index(drop=True)
    )


def build_clean_monthly_demand(transactions, daily_outliers):
    tx = transactions.copy()
    tx["day"] = tx["date"].dt.normalize()
    tx["month"] = tx["date"].dt.to_period("M").dt.to_timestamp()
    flags = daily_outliers[["supplier", "sku", "day", "is_one_off_order"]]
    tx = tx.merge(flags, on=["supplier", "sku", "day"], how="left")
    tx["is_one_off_order"] = tx["is_one_off_order"].fillna(False)
    tx["cleaned_qty"] = tx["normalized_sales_qty"].where(~tx["is_one_off_order"], 0)
    return tx.groupby(["supplier", "sku", "month"], as_index=False).agg(
        quantity=("normalized_sales_qty", "sum"),
        cleaned_quantity=("cleaned_qty", "sum"),
        anomaly_count=("is_one_off_order", "sum"),
    )
