import numpy as np


def supplier_seasonal_factors(aggregate):
    return (
        aggregate.groupby(["supplier", "month_number"], as_index=False)[
            "seasonal_index"
        ]
        .median()
        .rename(columns={"seasonal_index": "supplier_seasonality"})
    )


def seasonal_factor(history, target_month, supplier_fallback=1.0, min_observations=18):
    values = history.dropna().astype(float)
    if len(values) >= min_observations and values.index.month.nunique() >= 9:
        month_means = values.groupby(values.index.month).median()
        overall = values.median()
        if overall > 0 and target_month in month_means:
            return float(np.clip(month_means[target_month] / overall, 0.5, 1.75)), "sku"
    return float(np.clip(supplier_fallback, 0.5, 1.75)), (
        "supplier" if supplier_fallback != 1 else "neutral"
    )
