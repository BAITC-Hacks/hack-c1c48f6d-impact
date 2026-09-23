import pandas as pd

from src.presentation import display_value, representative_examples, warning_labels


def test_warning_labels_are_concise_and_business_friendly():
    row = pd.Series(
        {
            "product_metadata_missing": True,
            "moq_missing": True,
            "current_stock_missing": False,
            "sparse_history": True,
            "outlier_quantity_removed": 12,
        }
    )
    assert warning_labels(row) == (
        "Missing metadata · Missing MOQ · Sparse history · Outlier-adjusted"
    )


def test_representative_examples_use_real_rows_deterministically():
    frame = pd.DataFrame(
        {
            "supplier": ["IEK", "SystemElectric"],
            "sku": ["001_", "002_"],
            "calculated_seasonality_coefficient": [1.2, 1.0],
            "calculated_growth_coefficient": [1.0, 1.3],
            "outlier_quantity_removed": [5, 0],
            "estimated_lost_demand": [0, 7],
            "in_transit_before_required_date": [9, 0],
            "recommended_order_qty": [0, 10],
            "product_metadata_missing": [False, False],
        }
    )
    examples = representative_examples(frame)
    assert examples["Seasonal SKU"] == "IEK · 001_"
    assert examples["SKU requiring reorder"] == "SystemElectric · 002_"
    assert set(examples.values()).issubset({"IEK · 001_", "SystemElectric · 002_"})


def test_representative_examples_prefer_complete_metadata():
    frame = pd.DataFrame(
        {
            "supplier": ["IEK", "IEK"],
            "sku": ["missing_", "complete_"],
            "calculated_seasonality_coefficient": [1.5, 1.2],
            "calculated_growth_coefficient": [1.5, 1.2],
            "outlier_quantity_removed": [50, 5],
            "estimated_lost_demand": [50, 5],
            "in_transit_before_required_date": [50, 5],
            "recommended_order_qty": [50, 5],
            "product_metadata_missing": [True, False],
        }
    )
    examples = representative_examples(frame)
    assert set(examples.values()) == {"IEK · complete_"}


def test_display_value_is_compact_and_handles_missing_values():
    assert display_value(8888.86) == "8,888.9"
    assert display_value(float("nan")) == "Not available"
