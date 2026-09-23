import pandas as pd

from src.diagnostics import calculation_diagnostics


def test_missing_history_sku_is_handled_cleanly():
    data = {
        "recommendations": pd.DataFrame(
            [
                {
                    "supplier": "IEK",
                    "sku": "001_",
                    "baseline_demand": 0,
                    "adjusted_demand": 0,
                    "calculated_growth_coefficient": 1,
                    "calculated_seasonality_coefficient": 1,
                    "stockout_adjustment": 0,
                    "forecast_monthly": 0,
                    "forecast_horizon_days": 45,
                    "lead_time_days": 30,
                    "safety_stock": 0,
                    "free_stock": 0,
                    "in_transit_before_required_date": 0,
                    "recommended_raw_qty": 0,
                    "order_multiple": 1,
                    "recommended_order_qty": 0,
                }
            ]
        ),
        "demand_adjusted": pd.DataFrame(
            columns=[
                "supplier",
                "sku",
                "month",
                "quantity",
                "cleaned_quantity",
                "adjusted_quantity",
            ]
        ),
    }
    diagnostic = calculation_diagnostics(data, "IEK", "001_")
    assert diagnostic["monthly_demand_series"].empty
    assert diagnostic["final_forecast"] == 0
