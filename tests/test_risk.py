import pandas as pd

from src.pipeline import apply_sparse_history_safeguard
from src.presentation import assumption_preset
from src.risk import add_recommendation_risk


def recommendation_rows():
    return pd.DataFrame(
        {
            "recommended_order_qty": [80.0, 20.0],
            "history_observation_count": [1, 6],
            "sparse_history": [True, False],
            "current_stock_missing": [False, False],
            "moq_missing": [False, False],
            "variability_insufficient": [True, False],
        }
    )


def test_sparse_history_is_flagged_and_quantity_is_not_modified():
    source = recommendation_rows()
    result, summary = add_recommendation_risk(source, 0.20)
    assert result.loc[0, "recommendation_confidence"] == "REVIEW REQUIRED"
    assert result["recommended_order_qty"].tolist() == [80.0, 20.0]
    assert result.loc[0, "high_portfolio_impact"]
    assert summary["largest_sku_share"] == 0.8
    assert summary["top_five_share"] == 1.0


def test_insufficient_variability_does_not_masquerade_as_high_confidence():
    result, _ = add_recommendation_risk(recommendation_rows(), 0.90)
    assert result.loc[0, "variability_insufficient"]
    assert result.loc[0, "recommendation_confidence"] == "REVIEW REQUIRED"


def test_sparse_forecast_uses_neutral_robust_baseline():
    metric = {
        "baseline_demand": 210000.0,
        "calculated_growth_coefficient": 1.5,
        "calculated_seasonality_coefficient": 2.1,
        "forecast_monthly": 661500.0,
    }
    protected = apply_sparse_history_safeguard(metric, 1)
    assert protected["forecast_monthly"] == 210000.0
    assert protected["calculated_growth_coefficient"] == 1.0
    assert metric["forecast_monthly"] == 661500.0


def test_supported_forecast_is_unchanged_by_sparse_safeguard():
    metric = {
        "baseline_demand": 100.0,
        "calculated_growth_coefficient": 1.2,
        "calculated_seasonality_coefficient": 1.1,
        "forecast_monthly": 132.0,
    }
    assert apply_sparse_history_safeguard(metric, 3) is metric


def test_standard_preset_restores_original_assumptions():
    assert assumption_preset("Standard") == {
        "horizon_days": 45,
        "lead_time_days": 30,
        "service_factor": 1.28,
        "stockout_fraction": 0.35,
        "outlier_z": 5.0,
    }
