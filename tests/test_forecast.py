import pandas as pd
from src.forecast import forecast_one, sustained_growth
from src.stockouts import estimate_stockout_demand


def test_seasonality_affects_forecast():
    history = pd.Series(
        [10] * 6, index=pd.date_range("2026-01-01", periods=6, freq="MS")
    )
    neutral = forecast_one(history, 10, 1.0)
    seasonal = forecast_one(history, 10, 1.3)
    assert seasonal["forecast_monthly"] > neutral["forecast_monthly"]


def test_sustained_growth_uses_multi_month_windows():
    assert sustained_growth([10, 10, 10, 20, 20, 20]) > 1


def test_stockout_adjustment_raises_demand_conservatively():
    demand = pd.DataFrame(
        {
            "supplier": ["IEK"],
            "sku": ["A_"],
            "month": [pd.Timestamp("2026-01-01")],
            "quantity": [10],
            "cleaned_quantity": [10],
        }
    )
    stock = pd.DataFrame(
        {
            "supplier": ["IEK"],
            "sku": ["A_"],
            "month": [pd.Timestamp("2026-01-01")],
            "stock_level": [0],
        }
    )
    got = estimate_stockout_demand(demand, stock, 0.35).iloc[0]
    assert got.adjusted_quantity == 13.5 and got.estimated_lost_demand == 3.5
