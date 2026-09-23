import pandas as pd


WARNING_RULES = (
    ("product_metadata_missing", "Missing metadata"),
    ("moq_missing", "Missing MOQ"),
    ("current_stock_missing", "Missing stock"),
    ("sparse_history", "Sparse history"),
    ("outlier_quantity_removed", "Outlier-adjusted"),
)


def warning_labels(row):
    labels = []
    for field, label in WARNING_RULES:
        value = row.get(field, False)
        active = value > 0 if field == "outlier_quantity_removed" else bool(value)
        if active:
            labels.append(label)
    return " · ".join(labels)


def representative_examples(recommendations):
    """Pick real, deterministic examples that best demonstrate each calculation path."""
    if recommendations.empty:
        return {}
    rules = (
        (
            "Seasonal SKU",
            recommendations["calculated_seasonality_coefficient"].sub(1).abs(),
            0.05,
        ),
        ("Growth SKU", recommendations["calculated_growth_coefficient"].sub(1), 0.05),
        ("Anomaly-adjusted SKU", recommendations["outlier_quantity_removed"], 0),
        ("Stockout-adjusted SKU", recommendations["estimated_lost_demand"], 0),
        ("Inbound-covered SKU", recommendations["in_transit_before_required_date"], 0),
        ("SKU requiring reorder", recommendations["recommended_order_qty"], 0),
    )
    examples = {}
    for label, score, threshold in rules:
        candidates = recommendations.loc[score.gt(threshold)].assign(_score=score)
        if candidates.empty:
            continue
        chosen = candidates.sort_values(
            ["_score", "supplier", "sku"],
            ascending=[False, True, True],
            kind="stable",
        ).iloc[0]
        examples[label] = f"{chosen.supplier} · {chosen.sku}"
    return examples


def display_value(value, decimals=1, missing="Not available"):
    if pd.isna(value):
        return missing
    return f"{float(value):,.{decimals}f}"
