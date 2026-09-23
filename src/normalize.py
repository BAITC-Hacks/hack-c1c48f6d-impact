import re
import pandas as pd

RU_MONTHS = {
    "янв": 1,
    "январь": 1,
    "фев": 2,
    "февраль": 2,
    "март": 3,
    "мар": 3,
    "апр": 4,
    "апрель": 4,
    "май": 5,
    "июнь": 6,
    "июн": 6,
    "июль": 7,
    "июл": 7,
    "авг": 8,
    "август": 8,
    "сен": 9,
    "сент": 9,
    "сентябрь": 9,
    "окт": 10,
    "октябрь": 10,
    "ноя": 11,
    "нояб": 11,
    "ноябрь": 11,
    "дек": 12,
    "декабрь": 12,
}


def normalize_sku(value):
    if pd.isna(value):
        return pd.NA
    value = str(value).strip()
    if not value or value.lower() == "nan":
        return pd.NA
    if re.fullmatch(r"\d+\.0", value):
        value = value[:-2]
    return value


def parse_russian_month(value):
    text = str(value).lower().replace("ё", "е").replace("г.", " ").strip()
    match = re.search(r"([а-я]+)\.?\s+(20\d{2})", text)
    if not match:
        return None
    token = match.group(1).rstrip(".")
    month = next(
        (
            number
            for name, number in RU_MONTHS.items()
            if token == name or token.startswith(name)
        ),
        None,
    )
    return pd.Timestamp(int(match.group(2)), month, 1) if month else None


def numeric(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )


def wide_months_to_long(frame, sku_col, value_name, supplier, id_columns=()):
    month_map = {column: parse_russian_month(column) for column in frame.columns}
    month_map = {
        column: month for column, month in month_map.items() if month is not None
    }
    ids = [sku_col, *[c for c in id_columns if c in frame.columns]]
    out = frame.melt(
        id_vars=ids,
        value_vars=list(month_map),
        var_name="source_month",
        value_name=value_name,
    )
    out["month"] = out["source_month"].map(month_map)
    out["sku"] = out[sku_col].map(normalize_sku)
    out[value_name] = numeric(out[value_name])
    out["supplier"] = supplier
    return out[
        [
            "supplier",
            "sku",
            "month",
            value_name,
            *[c for c in id_columns if c in out.columns],
        ]
    ].dropna(subset=["sku"])
