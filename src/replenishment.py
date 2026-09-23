import math
import numpy as np
import pandas as pd


def round_up_to_multiple(requirement, multiple):
    multiple = 1 if pd.isna(multiple) or multiple <= 0 else float(multiple)
    return math.ceil(max(0, float(requirement)) / multiple) * multiple


def calculate_recommendation(
    forecast_monthly,
    demand_std,
    available_stock,
    reserved_stock,
    inbound_eligible,
    order_multiple,
    horizon_days=45,
    lead_time_days=30,
    service_factor=1.28,
):
    forecast = max(0, float(forecast_monthly or 0))
    available = max(0, float(available_stock or 0))
    inbound = max(0, float(inbound_eligible or 0))
    horizon = forecast * horizon_days / 30
    safety = (
        max(0, float(service_factor))
        * max(0, float(demand_std or 0))
        * math.sqrt(max(lead_time_days, 1) / 30)
    )
    raw = max(0, horizon + safety - available - inbound)
    recommended = round_up_to_multiple(raw, order_multiple)
    daily = forecast / 30
    days_supply = available / daily if daily > 0 else np.inf
    days_supply_display = (
        f"{days_supply:.1f}" if np.isfinite(days_supply) else "No current demand"
    )
    if available <= 0 and forecast > 0:
        urgency = "CRITICAL"
    elif days_supply < lead_time_days:
        urgency = "CRITICAL"
    elif days_supply < horizon_days:
        urgency = "HIGH"
    elif raw > 0:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"
    return {
        "demand_during_horizon": horizon,
        "safety_stock": safety,
        "recommended_raw_qty": raw,
        "recommended_order_qty": recommended,
        "days_of_supply": days_supply,
        "days_of_supply_display": days_supply_display,
        "urgency": urgency,
    }
