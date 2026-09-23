# Source workbook audit (23 September 2026)

The workbooks were inspected directly before transformation. Header rows below are zero-based for `pandas`.

| Workbook | Sheets / dimensions | Header | Key observations |
|---|---|---:|---|
| MOQ SystemElectric | `Лист_1`, A1:E557 | 0 | Blank physical row 2; 1C codes retain `_`; multiples include zero and require fallback 1. |
| SystemElectric transactions | `Лист_1`, H77314 | 0 | 77,300 numeric movements; 566 distinct non-null codes; 76,998 positive / 302 negative; one `Итого` footer is invalid as a transaction. |
| SystemElectric stock | `Лист_1`, A1:AK704 | 0 | Two blank rows after header; 33 Russian month columns Jan-2024–Sep-2026. |
| SystemElectric monthly sales | `Лист_1`, A1:AL557; `Лист1`, A1:O35 | 0 | First sheet is SKU-level; second is company aggregation. Negative monthly corrections exist. |
| SystemElectric seasonality | `Лист1`, A1:O35 | 2 | Year rows 2024–2026; supplied seasonal calculation below row 10. |
| SystemElectric current/inbound | `TDSheet`, A1:BR499; `Лист1`, A3:O23 | 1 | Inventory header is physical row 2; current, reserved, free stock and supplied coefficients are separate. |
| IEK MOQ | `Лист7`, A1:E1939 | 0 | 1C codes commonly end in `_`; shipment multiple in `Мин. разр. к отгр.`. |
| IEK transactions | `Лист_1`, H171605 | 0 | 171,586 numeric movements; 2,151 distinct non-null codes; 171,471 positive / 115 negative; one `Итого` footer. |
| IEK stock | `Лист_1`, AK2857 | 0 | Two subordinate header rows (`Количество`, `нач. остаток`); 33 Russian month columns. |
| IEK monthly sales | `Лист_1`, AJ2466 | 0 | One subordinate `Количество` row; 33 Russian month columns. |
| IEK inbound | `Лист4`, A1:I2642 | 0 | Six shipment columns; expected dates encoded in headers (30-Sep, 1-Oct, 10-Oct, 15-Oct 2026). |
| IEK seasonality | `Сезонность`, A1:O41 | 2 | Aggregate year rows 2024–2026 and calculated sections below. |

## Sign convention found

`Расходная накладная` records are negative in the small 2023–2024 legacy tail, but overwhelmingly positive in 2025–2026. SystemElectric has 76,997 positive and 299 negative expense-invoice rows; IEK has 171,470 positive and 109 negative. The current-period normalization therefore counts positive expense invoices as demand, treats opposite-sign current movements as returns/corrections (zero regular demand), and supports an explicit legacy cutoff that reverses pre-2025 negative expense invoices. Non-expense documents and invalid/footer rows are not demand. This is not `abs(quantity)`.

Large values are real transaction candidates as well as footer totals: invalid footer quantities are 6,837,478 and 3,846,998, while valid expense invoices include 90,000 (SystemElectric) and 210,000 (IEK). They must remain raw and undergo per-SKU robust one-off detection.

## Limitations

No customer identifier exists. Customer concentration cannot be evaluated. Monthly stock values are snapshots and cannot establish full-month stockout duration. Explicit supplier lead times are absent.

## Key nulls and duplicates

A full key scan (after the detected header) found:

| Source | Null-key rows | Unique keys | Duplicate keys |
|---|---:|---:|---:|
| SystemElectric MOQ | 2 (blank rows) | 554 | 0 |
| IEK MOQ | 0 | 1,937 | 1 |
| SystemElectric stock | 2 (blank rows) | 701 | 0 |
| IEK stock | 3 (subordinate header rows) | 2,853 | 0 |
| SystemElectric monthly sales | 2 | 554 | 0 |
| IEK monthly sales | 2 | 2,463 | 0 |
| SystemElectric current inventory | 0 | 497 | 0 |
| IEK inbound | 18 | 2,616 | 7 |

Duplicate rows are not assumed interchangeable: normalized inbound remains shipment-granular; product duplicates are surfaced in quality reporting and deterministically collapsed only for the one-row-per-SKU recommendation view. Transaction SKU repetition is expected (many movements per SKU), while invalid `Итого` footer rows have null SKU/date metadata and are retained as excluded raw records for auditability.
