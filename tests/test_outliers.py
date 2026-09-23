import pandas as pd
from src.transactions import normalize_sales_sign
from src.outliers import detect_one_off_orders, build_clean_monthly_demand


def sample_tx(qty, dates=None):
    dates = dates or pd.date_range("2026-01-01", periods=len(qty))
    return pd.DataFrame(
        {
            "supplier": "IEK",
            "sku": "A_",
            "date": dates,
            "document_type": "Расходная накладная 1",
            "raw_quantity": qty,
        }
    )


def test_audited_sales_sign_normalization_not_absolute_value():
    frame = sample_tx(
        [10, -5, -7],
        [
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-01-02"),
            pd.Timestamp("2024-01-01"),
        ],
    )
    got = normalize_sales_sign(frame)
    assert got.normalized_sales_qty.tolist() == [10, 0, 7]


def test_non_sales_document_is_excluded():
    frame = sample_tx([10])
    frame.loc[0, "document_type"] = "Приходная накладная"
    assert normalize_sales_sign(frame).normalized_sales_qty.iloc[0] == 0


def test_per_sku_giant_one_off_is_retained_but_excluded_from_clean_demand():
    frame = sample_tx([10] * 20 + [10000])
    frame = normalize_sales_sign(frame)
    out = detect_one_off_orders(frame, z_threshold=5)
    assert out.iloc[-1].is_one_off_order
    monthly = build_clean_monthly_demand(frame, out)
    assert monthly.cleaned_quantity.sum() == 200
    assert monthly.quantity.sum() == 10200
