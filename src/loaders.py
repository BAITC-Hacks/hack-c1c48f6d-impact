import re
from pathlib import Path
import pandas as pd
from .normalize import normalize_sku, numeric, wide_months_to_long


class WorkbookSchemaError(ValueError):
    pass


def sheet_names(path):
    return pd.ExcelFile(path, engine="openpyxl").sheet_names


def read_with_detected_header(path, required, sheet_name=0, max_rows=20):
    preview = pd.read_excel(
        path, sheet_name=sheet_name, header=None, nrows=max_rows, engine="openpyxl"
    )
    required = set(required)
    for row_index, row in preview.iterrows():
        values = {str(v).strip() for v in row.dropna()}
        if required <= values:
            return (
                pd.read_excel(
                    path,
                    sheet_name=sheet_name,
                    header=row_index,
                    engine="openpyxl",
                    dtype=object,
                ),
                row_index,
            )
    raise WorkbookSchemaError(
        f"Could not find header containing {sorted(required)} in {Path(path).name}"
    )


def _products(frame, supplier, sku, article, name, multiple):
    raw_multiple = numeric(frame[multiple])
    out = pd.DataFrame(
        {
            "supplier": supplier,
            "sku": frame[sku].map(normalize_sku),
            "supplier_article": frame[article].astype("string").str.strip(),
            "product_name": frame[name].astype("string").str.strip(),
            "category": pd.NA,
            "order_multiple": raw_multiple,
            "moq_missing": raw_multiple.isna() | raw_multiple.le(0),
        }
    )
    # Business fallback: ordering by individual units is the least-assumptive
    # behavior when the supplier workbook has no usable shipment multiple.
    out.loc[out["moq_missing"], "order_multiple"] = 1.0
    return out.dropna(subset=["sku"])


def load_moq(path, supplier):
    if supplier == "SystemElectric":
        f, _ = read_with_detected_header(path, ["Номенклатура.Код", "Кратность"])
        return _products(
            f, supplier, "Номенклатура.Код", "Артикул", "Номенклатура", "Кратность"
        )
    f, _ = read_with_detected_header(path, ["Код 1с", "Мин. разр. к отгр."])
    return _products(
        f,
        supplier,
        "Код 1с",
        "Артикул поставщика",
        "Наименование",
        "Мин. разр. к отгр.",
    )


def load_transactions(path, supplier):
    f, _ = read_with_detected_header(path, ["Дата", "Код", "Количество", "Документ"])
    out = pd.DataFrame(
        {
            "supplier": supplier,
            "date": pd.to_datetime(f["Дата"], dayfirst=True, errors="coerce"),
            "sku": f["Код"].map(normalize_sku),
            "warehouse": f["Склад"].astype("string").str.strip(),
            "document_number": f["Номер"].astype("string").str.strip(),
            "document_type": f["Документ"].astype("string").str.strip(),
            "product_name": f["Номенклатура"].astype("string").str.strip(),
            "raw_quantity": numeric(f["Количество"]),
        }
    )
    return out


def load_monthly(path, supplier, kind):
    required = ["Номенклатура.Код", "Номенклатура"]
    f, _ = read_with_detected_header(path, required)
    value = "stock_level" if kind == "stock" else "quantity"
    return wide_months_to_long(
        f, "Номенклатура.Код", value, supplier, ["Номенклатура"]
    ).rename(columns={"Номенклатура": "product_name"})


def load_system_inventory(path):
    f, _ = read_with_detected_header(
        path, ["Код 1с", "Свободный остаток", "СЭ в пути 24.09"], sheet_name="TDSheet"
    )
    out = pd.DataFrame(
        {
            "supplier": "SystemElectric",
            "sku": f["Код 1с"].map(normalize_sku),
            "supplier_article": f["Артикул поставщика"].astype("string").str.strip(),
            "product_name": f["Наименование"].astype("string").str.strip(),
            "category": f["Категория 2026"].astype("string").str.strip(),
            "current_stock": numeric(f["Остаток"]),
            "reserved_stock": numeric(f["Зарезервировано"]),
            "free_stock": numeric(f["Свободный остаток"]),
            "provided_growth_coefficient": numeric(f["Кэф. Роста"]),
            "provided_seasonality_coefficient": numeric(f["Кэф. Сез-ти"]),
            "inbound_quantity": numeric(f["СЭ в пути 24.09"]),
        }
    )
    return out.dropna(subset=["sku"])


def parse_arrival_date(header):
    matches = re.findall(r"(?:до\s*)?(\d{2}\.\d{2}\.20\d{2})", str(header))
    return (
        pd.to_datetime(matches[-1], dayfirst=True, errors="coerce")
        if matches
        else pd.NaT
    )


def load_iek_inbound(path):
    f, _ = read_with_detected_header(path, ["Код 1с", "Артикул ИЭК"])
    shipment_cols = [c for c in f.columns if pd.notna(parse_arrival_date(c))]
    long = f.melt(
        id_vars=["Код 1с", "Артикул ИЭК", " Наименование"],
        value_vars=shipment_cols,
        var_name="shipment_reference",
        value_name="quantity",
    )
    long["supplier"] = "IEK"
    long["sku"] = long["Код 1с"].map(normalize_sku)
    long["supplier_article"] = long["Артикул ИЭК"].astype("string").str.strip()
    long["expected_arrival_date"] = long["shipment_reference"].map(parse_arrival_date)
    long["quantity"] = numeric(long["quantity"])
    return long[
        [
            "supplier",
            "sku",
            "supplier_article",
            "shipment_reference",
            "expected_arrival_date",
            "quantity",
        ]
    ].dropna(subset=["sku", "quantity"])


def load_seasonality(path, supplier):
    f, _ = read_with_detected_header(path, ["год", "янв", "фев", "мар"])
    months = {
        "янв": 1,
        "фев": 2,
        "мар": 3,
        "апр": 4,
        "май": 5,
        "июн": 6,
        "июл": 7,
        "авг": 8,
        "сен": 9,
        "окт": 10,
        "ноя": 11,
        "дек": 12,
    }
    long = f[f["год"].astype(str).str.fullmatch(r"20\d{2}", na=False)].melt(
        id_vars="год",
        value_vars=list(months),
        var_name="month_name",
        value_name="sales",
    )
    long["sales"] = numeric(long["sales"])
    long["month_number"] = long["month_name"].map(months)
    long["supplier"] = supplier
    avg = long.groupby("год")["sales"].transform("mean")
    long["seasonal_index"] = long["sales"] / avg
    return long[["supplier", "год", "month_number", "sales", "seasonal_index"]]
