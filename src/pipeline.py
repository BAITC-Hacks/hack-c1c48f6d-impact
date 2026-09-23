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


def _dedupe_products(products):
    return products.sort_values("order_multiple", ascending=False).drop_duplicates(
        ["supplier", "sku"]
    )


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
    supplied = data["monthly_sales"].rename(columns={"quantity": "source_quantity"})
    combined = supplied.merge(tx_monthly, on=["supplier", "sku", "month"], how="outer")
    # Transaction detail is preferred wherever that source has valid rows; monthly source is fallback, never added.
    combined["quantity"] = combined["cleaned_quantity"].combine_first(
        combined["source_quantity"]
    )
    combined["cleaned_quantity"] = combined["quantity"]
    combined["anomaly_count"] = combined["anomaly_count"].fillna(0)
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
    base = data["products"].merge(
        inv, on=["supplier", "sku"], how="outer", suffixes=("", "_inventory")
    )
    for col in ["supplier_article", "product_name", "category"]:
        alt = col + "_inventory"
        if alt in base:
            base[col] = base[col].combine_first(base[alt])
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
        std = (
            float(series.iloc[-settings.recent_months :].std(ddof=0))
            if len(series)
            else 0
        )
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
        values["rationale"] = build_rationale(values)
        rows.append(values)
    recommendations = pd.DataFrame(rows)
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
        }
    )
    return data
