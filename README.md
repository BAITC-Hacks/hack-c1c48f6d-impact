# Explainable supplier replenishment MVP

A deterministic Streamlit application that recommends warehouse replenishment orders for **SystemElectric** and **IEK** from the partner-provided Excel workbooks. An LLM is not used anywhere in quantity calculation.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run tests with `pytest -q`. The app reads the original workbooks in place; it does not copy or modify them.

## Real input files and fields

The full sheet/header/shape and sign audit is in [`docs/DATA_AUDIT.md`](docs/DATA_AUDIT.md).

### SystemElectric

- `MOQ SystemElectric.xlsx`: `Номенклатура.Код`, `Артикул`, `Номенклатура`, `Кратность`.
- `Динамика продаж_Syseme Electric_2025-2026.xlsx`: `Дата`, `Номер`, `Документ`, `Код`, `Номенклатура`, `Склад`, `Количество`.
- `Ежемесячные остатки SystemElectric 2024-2026.xlsx`: SKU fields and Russian month/year stock columns.
- `Ежемесячные продажи в кол-м выражении SystemElectric 2024-2026.xlsx`: SKU fields, `Артикул`, `Кратность`, and Russian month/year quantity columns. `Лист_1` is used; the aggregate `Лист1` is not added to it.
- `Сезонность SystemElectric 2024-2026.xlsx`: company monthly history for fallback seasonality.
- `Товар в пути_SystemElectric на 22.09.2026.xlsx`, `TDSheet` physical row 2 header: `Код 1с`, category, total/reserved/free stock, supplied growth/seasonality coefficients, and `СЭ в пути 24.09`.

### IEK

- `MOQ  ИЭК.xlsx`: `Код 1с`, `Артикул поставщика`, `Наименование`, `Мин. разр. к отгр.`.
- `Динамика продаж_2025-2026.xlsx`: the shared transaction structure.
- Monthly stock and monthly sales workbooks: SKU plus Jan-2024–Sep-2026 Russian month columns. Extra subordinate header rows are read as data and discarded because they have no SKU.
- `Путь ИЭК 22.09.2026.xlsx`: `Код 1с`, `Артикул ИЭК`, product, and six shipment columns whose headers contain expected-arrival dates.
- `Сезонность ИЭК.xlsx`: aggregate company monthly history.

## Normalization and joins

All sources map to normalized `products`, `transactions`, `monthly_sales`, `monthly_stock`, `inventory`, and `inbound` frames. The key is the trimmed **1C code as a string** (`Код`, `Номенклатура.Код`, or `Код 1с`). Meaningful trailing underscores are preserved. Header rows are located by required field names rather than assumed blindly. Russian month columns are detected and melted dynamically; `Итого` is not treated as a month.

The data-quality panel reports sales without MOQ, MOQ without sales, missing inventory, missing transit, duplicate products, invalid dates, and invalid quantities. Unmatched records are not silently discarded.

## Demand cleaning

### Audited sign rule

The raw file evidence is not symmetric. `Расходная накладная` is negative in the small 2023–2024 legacy tail but overwhelmingly positive during 2025–2026. Therefore:

1. valid positive `Расходная накладная` quantities dated 2025 onward are outbound demand;
2. valid negative expense-invoice quantities before 2025 are legacy outbound demand and are sign-reversed;
3. opposite-sign movements are returns/corrections and contribute zero regular demand;
4. non-expense documents, footer totals, invalid dates, missing SKUs, and invalid quantities contribute zero.

`raw_quantity` is retained. The rule produces `normalized_sales_qty` and is deliberately **not** `abs(quantity)`. The cutoff is an explicit function parameter.

### Quantity-based one-off anomalies

Transactions are aggregated per supplier/SKU/day. A robust z-score based on that SKU's median absolute deviation (MAD) flags unusually high demand; when MAD is zero, a per-SKU IQR/ratio fallback is used. Raw demand remains available, while flagged days are excluded only from cleaned regular demand. The API reserves a future customer-field hook.

> **Data limitation:** Customer-specific bulk-order detection is supported by the architecture but cannot currently be evaluated because customer identifiers are not present in the supplied datasets. No customer IDs are fabricated.

### Reconciliation

Detailed transaction demand is preferred for months where it exists. The SKU monthly workbook is the fallback for other months. The sources are never added together, preventing double counting.

## Stockouts, growth, seasonality, and forecast

- A stock snapshot `<= 0` marks a **potential**, not proven full-month, stockout. The adjusted demand adds `cleaned demand × configurable stockout fraction` (default 35%) as `estimated_lost_demand`.
- The recent baseline is the median of up to six non-zero monthly observations.
- Sustained growth compares median demand across two three-month windows and is capped to 0.70–1.50 to avoid sparse-series explosions.
- With at least 18 observations and nine represented calendar months, SKU seasonal medians are used. Otherwise the hierarchy falls back to supplier aggregate seasonality, then neutral `1.0`. SystemElectric's supplied growth and seasonality coefficients remain separate audit fields and are not trusted as calculated inputs.
- The transparent monthly fallback is `baseline × capped trend × seasonal factor`. This is intentionally used consistently instead of forcing Holt-Winters onto sparse SKUs.

## Inventory and inbound treatment

SystemElectric uses `Свободный остаток` as available stock and keeps `Остаток` and `Зарезервировано` separate. Reserved units are **not** made available. IEK has no separate current-stock source, so its latest non-null monthly record becomes `latest_available_stock_snapshot` with `stock_snapshot_date`.

SystemElectric `СЭ в пути 24.09` is represented as a 24-Sep-2026 arrival. Each IEK shipment header is melted independently with its parsed expected date. The application displays total transit, but subtracts only `in_transit_before_required_date`; late transit cannot cover an earlier shortage, and transit is subtracted once.

## Replenishment formula

Explicit supplier lead times are absent. The sidebar therefore labels lead time as a configurable assumption (default 30 days). Horizon defaults to 45 days.

```text
demand_during_horizon = forecast_monthly × horizon_days / 30
safety_stock = service_factor × recent_monthly_std × sqrt(lead_time_days / 30)
net_requirement = demand_during_horizon + safety_stock
                  - free_stock - eligible_inbound
raw_requirement = max(0, net_requirement)
recommended_order = ceil(raw_requirement / order_multiple) × order_multiple
```

Missing or non-positive MOQ/order multiples safely become 1. Every result exposes raw requirement, multiple, final rounded quantity, measurable urgency, and a sentence-level calculation rationale. `CRITICAL` means no available stock with demand or coverage below lead time; `HIGH` is below the horizon; `MEDIUM` needs stock but is not yet high risk; otherwise `LOW`.

## Dashboard demo flow

1. Adjust horizon, explicit lead-time assumption, service factor, stockout fraction, or anomaly threshold.
2. Filter All/SystemElectric/IEK, SKU/product text, category, and urgency.
3. Review six KPI cards and the sortable recommendation table.
4. Select an SKU to inspect raw/cleaned/stockout-adjusted demand, stock history, factors, inbound shipments, and rationale.
5. Expand the data-quality report.
6. Export UTF-8 CSV or an Excel workbook with one supplier sheet per group.

Expensive workbook loading and transformation is cached with `@st.cache_data`.

## Tests

The test suite covers SKU preservation and joins, dynamic Russian month parsing, audited sign logic, non-sale exclusion, per-SKU outliers, giant-order removal from clean demand, stockout adjustment, growth, seasonality, inventory/transit monotonicity, reserved-stock isolation, MOQ rounding, shipment arrival parsing, late-inbound eligibility, rationale generation, supplier grouping, and data-quality mismatches.
