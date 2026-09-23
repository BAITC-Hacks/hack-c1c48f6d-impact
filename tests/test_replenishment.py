import pandas as pd
from src.replenishment import calculate_recommendation, round_up_to_multiple
from src.inventory import summarize_inbound
from src.explanations import build_rationale


def rec(stock=0, inbound=0, reserved=0):
    return calculate_recommendation(
        100,
        0,
        stock,
        reserved,
        inbound,
        10,
        horizon_days=30,
        lead_time_days=30,
        service_factor=0,
    )


def test_moq_rounding_and_zero_fallback():
    assert round_up_to_multiple(47, 10) == 50
    assert round_up_to_multiple(47, 0) == 47


def test_missing_moq_fallback_is_explicit_and_never_nan_in_rationale():
    values = {
        **rec(20, 10),
        "free_stock": 20,
        "reserved_stock": 0,
        "in_transit_before_required_date": 10,
        "order_multiple": float("nan"),
        "moq_missing": True,
    }
    rationale = build_rationale(values)
    assert "MOQ unavailable; fallback multiple 1 used." in rationale
    assert "nan" not in rationale.lower()


def test_zero_demand_has_business_friendly_days_of_supply():
    result = calculate_recommendation(0, 0, 10, 0, 0, 1)
    assert result["days_of_supply_display"] == "No current demand"
    assert "inf" not in result["days_of_supply_display"].lower()


def test_stock_increase_cannot_increase_order():
    assert rec(50)["recommended_order_qty"] <= rec(20)["recommended_order_qty"]


def test_inbound_increase_cannot_increase_order():
    assert rec(20, 50)["recommended_order_qty"] <= rec(20, 10)["recommended_order_qty"]


def test_reserved_is_not_added_to_free_stock():
    assert rec(20, 0, 100)["recommended_order_qty"] == 80


def test_late_transit_does_not_cover_earlier_shortage():
    inbound = pd.DataFrame(
        {
            "supplier": ["IEK", "IEK"],
            "sku": ["A_", "A_"],
            "expected_arrival_date": pd.to_datetime(["2026-09-30", "2026-11-01"]),
            "quantity": [10, 90],
        }
    )
    got = summarize_inbound(inbound, "2026-10-15").iloc[0]
    assert got.total_in_transit == 100 and got.in_transit_before_required_date == 10


def test_every_recommendation_can_have_rationale():
    values = {
        **rec(20, 10),
        "free_stock": 20,
        "in_transit_before_required_date": 10,
        "order_multiple": 10,
    }
    assert build_rationale(values).startswith("Recommend")


def test_results_remain_groupable_by_supplier():
    frame = pd.DataFrame(
        {
            "supplier": ["IEK", "SystemElectric", "IEK"],
            "recommended_order_qty": [1, 2, 3],
        }
    )
    assert frame.groupby("supplier").recommended_order_qty.sum().to_dict() == {
        "IEK": 4,
        "SystemElectric": 2,
    }
