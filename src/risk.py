import numpy as np


def add_recommendation_risk(recommendations, concentration_threshold=0.20):
    """Add review signals without changing any calculated recommendation quantity."""
    out = recommendations.copy()
    total = float(out["recommended_order_qty"].clip(lower=0).sum())
    out["recommendation_share"] = (
        out["recommended_order_qty"].clip(lower=0) / total if total > 0 else 0.0
    )
    out["high_portfolio_impact"] = out["recommendation_share"].gt(
        concentration_threshold
    )
    insufficient = out["history_observation_count"].eq(0)
    review = (
        out["sparse_history"]
        | out["current_stock_missing"]
        | out["moq_missing"]
        | out["variability_insufficient"]
        | out["high_portfolio_impact"]
    )
    out["recommendation_confidence"] = np.select(
        [insufficient, review],
        ["INSUFFICIENT DATA", "REVIEW REQUIRED"],
        default="HIGH CONFIDENCE",
    )
    top_five_share = (
        float(out["recommended_order_qty"].nlargest(5).sum()) / total
        if total > 0
        else 0.0
    )
    impact_count = int(out["high_portfolio_impact"].sum())
    summary = {
        "total_recommended_units": total,
        "top_five_share": top_five_share,
        "high_impact_sku_count": impact_count,
        "largest_sku_share": float(out["recommendation_share"].max())
        if len(out)
        else 0.0,
    }
    return out, summary
