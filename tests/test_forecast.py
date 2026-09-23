import pandas as pd
from src.forecast import forecast_one, sustained_growth
from src.stockouts import estimate_stockout_demand
from src.outliers import detect_one_off_orders, build_clean_monthly_demand
from src.pipeline import reconcile_monthly_demand


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


def test_transaction_and_monthly_sources_are_not_double_counted():
    source = pd.DataFrame(
        {
            "supplier": ["IEK"],
            "sku": ["001_"],
            "month": [pd.Timestamp("2026-01-01")],
            "quantity": [100],
        }
    )
    transactions = pd.DataFrame(
        {
            "supplier": ["IEK"],
            "sku": ["001_"],
            "month": [pd.Timestamp("2026-01-01")],
            "quantity": [90],
            "cleaned_quantity": [80],
            "anomaly_count": [1],
        }
    )
    got = reconcile_monthly_demand(source, transactions).iloc[0]
    assert got.quantity == 90
    assert got.cleaned_quantity == 80


def test_extreme_one_off_sale_does_not_dominate_forecast():
    tx = pd.DataFrame(
        {
            "supplier": ["IEK"] * 7,
            "sku": ["A_"] * 7,
            "date": pd.date_range("2026-01-01", periods=7, freq="D"),
            "normalized_sales_qty": [10, 9, 11, 10, 12, 8, 210000],
        }
    )
    anomalies = detect_one_off_orders(tx)
    monthly = build_clean_monthly_demand(tx, anomalies)
    assert anomalies.iloc[-1].is_one_off_order
    assert monthly.iloc[0].cleaned_quantity == 60
    forecast = forecast_one(monthly.set_index("month")["cleaned_quantity"], 2)
    assert forecast["forecast_monthly"] < 100
