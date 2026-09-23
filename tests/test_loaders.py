import pandas as pd
from src.normalize import normalize_sku, parse_russian_month, wide_months_to_long
from src.loaders import parse_arrival_date


def test_sku_normalization_preserves_underscore():
    assert normalize_sku(" 081100768_ ") == "081100768_"


def test_sku_normalization_preserves_leading_zero_for_joins():
    left = pd.DataFrame({"sku": [normalize_sku(" 00123_ ")]})
    right = pd.DataFrame({"sku": [normalize_sku("00123_")], "name": ["product"]})
    assert left.merge(right, on="sku").iloc[0]["name"] == "product"


def test_russian_month_parser_and_wide_conversion():
    assert parse_russian_month("Сентябрь 2026 г.") == pd.Timestamp("2026-09-01")
    frame = pd.DataFrame(
        {
            "Номенклатура.Код": [" A_ "],
            "янв. 2024": [3],
            "февр. 2024": [4],
            "Итого": [7],
        }
    )
    got = wide_months_to_long(frame, "Номенклатура.Код", "quantity", "IEK")
    assert got["quantity"].tolist() == [3, 4] and got["sku"].unique().tolist() == ["A_"]


def test_iek_arrival_date_uses_expected_not_document_date():
    header = "РФ УТ-7583 от 31 августа 2026 г. (поступление до 10.10.2026)"
    assert parse_arrival_date(header) == pd.Timestamp("2026-10-10")
