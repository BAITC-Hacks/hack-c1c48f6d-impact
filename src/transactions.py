import pandas as pd


def normalize_sales_sign(transactions, legacy_cutoff="2025-01-01"):
    """Normalize audited sign convention; never takes absolute values indiscriminately."""
    out = transactions.copy()
    date = out["date"]
    qty = out["raw_quantity"]
    expense = out["document_type"].str.startswith("Расходная накладная", na=False)
    current = date >= pd.Timestamp(legacy_cutoff)
    valid = date.notna() & out["sku"].notna() & qty.notna()
    demand = pd.Series(0.0, index=out.index)
    demand.loc[valid & expense & current & qty.gt(0)] = qty
    demand.loc[valid & expense & ~current & qty.lt(0)] = -qty
    out["normalized_sales_qty"] = demand
    out["sign_rule_status"] = "excluded_non_sale_or_correction"
    out.loc[demand.gt(0), "sign_rule_status"] = "outbound_sale"
    return out
