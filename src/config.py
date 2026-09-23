from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_DIR = ROOT / "Systeme electric" / "Systeme electric"
IEK_DIR = ROOT / "IEK" / "IEK"
AS_OF_DATE = "2026-09-22"

FILES = {
    "system_moq": SYSTEM_DIR / "MOQ SystemElectric.xlsx",
    "system_transactions": SYSTEM_DIR
    / "Динамика продаж_Syseme Electric_2025-2026.xlsx",
    "system_stock": SYSTEM_DIR / "Ежемесячные остатки SystemElectric 2024-2026.xlsx",
    "system_monthly_sales": SYSTEM_DIR
    / "Ежемесячные продажи в кол-м выражении SystemElectric 2024-2026.xlsx",
    "system_seasonality": SYSTEM_DIR / "Сезонность SystemElectric 2024-2026.xlsx",
    "system_inventory": SYSTEM_DIR / "Товар в пути_SystemElectric на 22.09.2026.xlsx",
    "iek_moq": IEK_DIR / "MOQ  ИЭК.xlsx",
    "iek_transactions": IEK_DIR / "Динамика продаж_2025-2026.xlsx",
    "iek_stock": IEK_DIR
    / "Ежемесячные остатки продукции за последние 2 года  ИЭК.xlsx",
    "iek_monthly_sales": IEK_DIR
    / "Ежемесячные продажи в количественном выражении за последние 2 года.xlsx",
    "iek_inbound": IEK_DIR / "Путь ИЭК 22.09.2026.xlsx",
    "iek_seasonality": IEK_DIR / "Сезонность ИЭК.xlsx",
}


@dataclass(frozen=True)
class Settings:
    horizon_days: int = 45
    lead_time_days: int = 30
    service_factor: float = 1.28
    stockout_fraction: float = 0.35
    outlier_z: float = 5.0
    recent_months: int = 6
    trend_cap_low: float = 0.70
    trend_cap_high: float = 1.50
