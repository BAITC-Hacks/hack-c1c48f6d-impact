import numpy as np
import pandas as pd
from .config import FILES, Settings, AS_OF_DATE
from .loaders import (
    load_moq,
    load_transactions,
    load_monthly,
    load_system_inventory,
    load_iek_inbound,
    load_seasonality,
)
from .transactions import normalize_sales_sign
from .outliers import detect_one_off_orders, build_clean_monthly_demand
from .stockouts import estimate_stockout_demand
from .forecast import forecast_one
from .inventory import latest_iek_inventory, summarize_inbound
from .replenishment import calculate_recommendation
from .quality import data_quality_report
from .explanations import build_rationale
from .risk import add_recommendation_risk


def _dedupe_products(products):
    ranked = products.assign(
        _metadata=products[["supplier_article", "product_name"]].notna().sum(axis=1)
    ).sort_values(
        ["supplier", "sku", "moq_missing", "_metadata", "order_multiple"],
        ascending=[True, True, True, False, False],
        kind="stable",
    )
    return ranked.drop_duplicates(["supplier", "sku"]).drop(columns="_metadata")


def _first_metadata(frame, columns):
    """Return one deterministic nonblank metadata row per normalized key."""
    available = [column for column in columns if column in frame]
    if not available:
        return pd.DataFrame(columns=["supplier", "sku", *columns])
    selected = frame[["supplier", "sku", *available]].copy()
    for column in available:
        selected[column] = (
            selected[column].astype("string").str.strip().replace("", pd.NA)
        )
    return selected.groupby(["supplier", "sku"], as_index=False, sort=False).first()


def _recommendation_base(data):
    """Build the complete SKU universe and enrich it in documented priority order."""
    sources = [
        data[name][["supplier", "sku"]]
        for name in (
            "products",
            "inventory",
            "monthly_sales",
            "transactions",
            "inbound",
        )
    ]
    base = pd.concat(sources, ignore_index=True).dropna().drop_duplicates()
    metadata_sources = [
        data["products"],  # supplier MOQ master is authoritative
        data["inventory"],  # then current inventory master
        data["monthly_sales"],  # then monthly sales labels
        data["transactions"],  # transaction label is the last fallback
    ]
    for priority, source in enumerate(metadata_sources):
        meta = _first_metadata(source, ["supplier_article", "product_name", "category"])
        rename = {
            column: f"{column}_{priority}"
            for column in meta
            if column not in ("supplier", "sku")
        }
        base = base.merge(
            meta.rename(columns=rename), on=["supplier", "sku"], how="left"
        )
    for column in ("supplier_article", "product_name", "category"):
        candidates = [
            f"{column}_{priority}"
            for priority in range(len(metadata_sources))
            if f"{column}_{priority}" in base
        ]
        base[column] = (
            base[candidates].bfill(axis=1).iloc[:, 0] if candidates else pd.NA
        )
        base = base.drop(columns=candidates)
    moq = data["products"][["supplier", "sku", "order_multiple", "moq_missing"]]
    base = base.merge(moq, on=["supplier", "sku"], how="left")
    base["moq_missing"] = base["moq_missing"].fillna(True).astype(bool)
    base["order_multiple"] = base["order_multiple"].fillna(1.0)
    base["product_metadata_missing"] = (
        base[["supplier_article", "product_name", "category"]].isna().any(axis=1)
    )
    return base


def reconcile_monthly_demand(monthly_sales, transaction_monthly):
    """Prefer transaction detail by month; never add it to workbook monthly totals."""
    supplied = (
        monthly_sales.groupby(["supplier", "sku", "month"], as_index=False)["quantity"]
        .sum(min_count=1)
        .rename(columns={"quantity": "source_quantity"})
    )
    transactions = transaction_monthly.rename(
        columns={"quantity": "transaction_quantity"}
    )
    combined = supplied.merge(
        transactions,
        on=["supplier", "sku", "month"],
        how="outer",
        validate="one_to_one",
    )
    combined["quantity"] = combined["transaction_quantity"].combine_first(
        combined["source_quantity"]
    )
    combined["cleaned_quantity"] = combined["cleaned_quantity"].combine_first(
        combined["source_quantity"]
    )
    combined["anomaly_count"] = combined["anomaly_count"].fillna(0)
    return combined


def load_normalized_sources():
    products = pd.concat(
        [
            load_moq(FILES["system_moq"], "SystemElectric"),
            load_moq(FILES["iek_moq"], "IEK"),
        ],
        ignore_index=True,
    )
    transactions = pd.concat(
        [
            load_transactions(FILES["system_transactions"], "SystemElectric"),
            load_transactions(FILES["iek_transactions"], "IEK"),
        ],
        ignore_index=True,
    )
    sales = pd.concat(
        [
            load_monthly(FILES["system_monthly_sales"], "SystemElectric", "sales"),
            load_monthly(FILES["iek_monthly_sales"], "IEK", "sales"),
        ],
        ignore_index=True,
    )
    stock = pd.concat(
        [
            load_monthly(FILES["system_stock"], "SystemElectric", "stock"),
            load_monthly(FILES["iek_stock"], "IEK", "stock"),
        ],
        ignore_index=True,
    )
    system_inventory = load_system_inventory(FILES["system_inventory"])
    iek_inventory = latest_iek_inventory(stock[stock.supplier.eq("IEK")])
    inventory = pd.concat(
        [system_inventory, iek_inventory], ignore_index=True, sort=False
    )
    iek_inbound = load_iek_inbound(FILES["iek_inbound"])
    system_inbound = (
        system_inventory[["supplier", "sku", "inbound_quantity"]]
        .rename(columns={"inbound_quantity": "quantity"})
        .assign(
            expected_arrival_date=pd.Timestamp("2026-09-24"),
            shipment_reference="СЭ в пути 24.09",
        )
    )
    inbound = pd.concat([system_inbound, iek_inbound], ignore_index=True, sort=False)
    seasonality = pd.concat(
        [
            load_seasonality(FILES["system_seasonality"], "SystemElectric"),
            load_seasonality(FILES["iek_seasonality"], "IEK"),
        ],
        ignore_index=True,
    )
    return {
        "products": _dedupe_products(products),
        "transactions": transactions,
        "monthly_sales": sales,
        "monthly_stock": stock,
        "inventory": inventory,
        "inbound": inbound,
        "seasonality": seasonality,
    }


def run_pipeline(settings=Settings()):
    data = load_normalized_sources()
    tx = normalize_sales_sign(data["transactions"])
    anomalies = detect_one_off_orders(tx, settings.outlier_z)
    tx_monthly = build_clean_monthly_demand(tx, anomalies)
    combined = reconcile_monthly_demand(data["monthly_sales"], tx_monthly)
    adjusted = estimate_stockout_demand(
        combined, data["monthly_stock"], settings.stockout_fraction
    )
    as_of = pd.Timestamp(AS_OF_DATE)
    required = as_of + pd.Timedelta(days=settings.lead_time_days)
    inbound_summary = summarize_inbound(data["inbound"], required)
    inv = (
        data["inventory"]
        .sort_values("free_stock", na_position="first")
        .drop_duplicates(["supplier", "sku"], keep="last")
    )
    base = _recommendation_base(data)
    base = base.merge(
        inv, on=["supplier", "sku"], how="left", suffixes=("", "_inventory")
    )
    base["current_stock_missing"] = base["current_stock"].isna()
    base = base.merge(inbound_summary, on=["supplier", "sku"], how="left")
    seasonal = (
        data["seasonality"]
        .groupby(["supplier", "month_number"])["seasonal_index"]
        .median()
    )
    agg = adjusted.groupby(["supplier", "sku"], as_index=False).agg(
        estimated_lost_demand=("estimated_lost_demand", "sum"),
        anomaly_count=("anomaly_count", "sum"),
    )
    base = base.merge(agg, on=["supplier", "sku"], how="left")
    rows = []
    for row in base.itertuples(index=False):
        hist = adjusted[
            (adjusted.supplier == row.supplier) & (adjusted.sku == row.sku)
        ].sort_values("month")
        series = (
            hist.set_index("month")["adjusted_quantity"]
            if not hist.empty
            else pd.Series(dtype=float)
        )
        sf = float(seasonal.get((row.supplier, required.month), 1.0))
        metric = forecast_one(
            series,
            required.month,
            sf,
            settings.recent_months,
            (settings.trend_cap_low, settings.trend_cap_high),
        )
        observation_count = int(series.gt(0).sum())
        metric = apply_sparse_history_safeguard(metric, observation_count)
        std = (
            float(series.iloc[-settings.recent_months :].std(ddof=0))
            if len(series)
            else 0
        )
        variability_insufficient = observation_count < 2
        free = getattr(row, "free_stock", np.nan)
        current = getattr(row, "current_stock", 0)
        free = current if pd.isna(free) else free
        rec = calculate_recommendation(
            metric["forecast_monthly"],
            std,
            free,
            0 if pd.isna(getattr(row, "reserved_stock", 0)) else row.reserved_stock,
            (
                0
                if pd.isna(getattr(row, "in_transit_before_required_date", 0))
                else row.in_transit_before_required_date
            ),
            getattr(row, "order_multiple", 1),
            settings.horizon_days,
            settings.lead_time_days,
            settings.service_factor,
        )
        values = row._asdict()
        values.update(metric)
        values.update(rec)
        values["free_stock"] = 0 if pd.isna(free) else float(free)
        values["current_stock"] = 0 if pd.isna(current) else float(current)
        values["reserved_stock"] = (
            0
            if pd.isna(getattr(row, "reserved_stock", 0))
            else float(row.reserved_stock)
        )
        values["total_in_transit"] = (
            0
            if pd.isna(getattr(row, "total_in_transit", 0))
            else float(row.total_in_transit)
        )
        values["in_transit_before_required_date"] = (
            0
            if pd.isna(getattr(row, "in_transit_before_required_date", 0))
            else float(row.in_transit_before_required_date)
        )
        values["estimated_lost_demand"] = (
            0
            if pd.isna(getattr(row, "estimated_lost_demand", 0))
            else float(row.estimated_lost_demand)
        )
        values["anomaly_count"] = (
            0 if pd.isna(getattr(row, "anomaly_count", 0)) else int(row.anomaly_count)
        )
        values["outlier_quantity_removed"] = (
            float((hist["quantity"] - hist["cleaned_quantity"]).clip(lower=0).sum())
            if not hist.empty
            else 0.0
        )
        values["stockout_adjustment"] = values["estimated_lost_demand"]
        values["adjusted_demand"] = metric["forecast_monthly"]
        values["forecast_horizon_days"] = settings.horizon_days
        values["lead_time_days"] = settings.lead_time_days
        values["sparse_history"] = int((series > 0).sum()) < 3
        values["rationale"] = build_rationale(values)
        rows.append(values)
    recommendations = pd.DataFrame(rows)
    recommendations, portfolio_risk = add_recommendation_risk(
        recommendations, settings.concentration_threshold
    )
    quality = data_quality_report(
        data["products"],
        data["monthly_sales"],
        data["inventory"],
        data["inbound"],
        data["transactions"],
    )
    data.update(
        {
            "transactions_clean": tx,
            "daily_anomalies": anomalies,
            "demand_adjusted": adjusted,
            "recommendations": recommendations,
            "quality": quality,
            "portfolio_risk": portfolio_risk,
        }
    )
    return data
