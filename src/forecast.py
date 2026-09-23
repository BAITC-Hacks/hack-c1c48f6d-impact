import numpy as np
import pandas as pd
from .seasonality import seasonal_factor


def sustained_growth(values, cap_low=0.70, cap_high=1.50):
    x = pd.Series(values, dtype=float).dropna().clip(lower=0)
    if len(x) < 6 or x.iloc[-6:].mean() <= 0:
        return 1.0
    recent = x.iloc[-3:].median()
    prior = x.iloc[-6:-3].median()
    if prior <= 0:
        return 1.0
    return float(np.clip(recent / prior, cap_low, cap_high))


def forecast_one(
    history,
    target_month,
    supplier_seasonality=1.0,
    recent_months=6,
    trend_caps=(0.70, 1.50),
):
    series = history.sort_index().astype(float).fillna(0).clip(lower=0)
    nonzero = series[series > 0]
    baseline = float(nonzero.iloc[-recent_months:].median()) if len(nonzero) else 0.0
    trend = sustained_growth(series.iloc[-max(6, recent_months) :], *trend_caps)
    season, source = seasonal_factor(series, target_month, supplier_seasonality)
    return {
        "baseline_demand": baseline,
        "calculated_growth_coefficient": trend,
        "calculated_seasonality_coefficient": season,
        "seasonality_source": source,
        "forecast_monthly": baseline * trend * season,
    }
