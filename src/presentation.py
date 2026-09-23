import pandas as pd


WARNING_RULES = (
    ("product_metadata_missing", "Missing metadata"),
    ("moq_missing", "Missing MOQ"),
    ("current_stock_missing", "Missing stock"),
    ("sparse_history", "Sparse history"),
    ("outlier_quantity_removed", "Outlier-adjusted"),
    ("variability_insufficient", "Safety stock uncertain"),
    ("high_portfolio_impact", "High portfolio impact — review"),
)

ASSUMPTION_PRESETS = {
    "Standard": {
        "horizon_days": 45,
        "lead_time_days": 30,
        "service_factor": 1.28,
        "stockout_fraction": 0.35,
        "outlier_z": 5.0,
    },
    "Conservative": {
        "horizon_days": 30,
        "lead_time_days": 21,
        "service_factor": 1.0,
        "stockout_fraction": 0.20,
        "outlier_z": 4.0,
    },
    "Stress test": {
        "horizon_days": 60,
        "lead_time_days": 45,
        "service_factor": 1.65,
        "stockout_fraction": 0.50,
        "outlier_z": 6.0,
    },
}


def assumption_preset(name):
    return ASSUMPTION_PRESETS[name].copy()


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
        candidates["_metadata_complete"] = ~candidates.get(
            "product_metadata_missing", pd.Series(False, index=candidates.index)
        ).fillna(True)
        candidates["_valid_moq"] = ~candidates.get(
            "moq_missing", pd.Series(False, index=candidates.index)
        ).fillna(True)
        candidates["_supported_history"] = ~candidates.get(
            "sparse_history", pd.Series(False, index=candidates.index)
        ).fillna(True)
        chosen = candidates.sort_values(
            [
                "_metadata_complete",
                "_valid_moq",
                "_supported_history",
                "_score",
                "supplier",
                "sku",
            ],
            ascending=[False, False, False, False, True, True],
            kind="stable",
        ).iloc[0]
        examples[label] = f"{chosen.supplier} · {chosen.sku}"
    return examples


def display_value(value, decimals=1, missing="Not available"):
    if pd.isna(value):
        return missing
    return f"{float(value):,.{decimals}f}"
