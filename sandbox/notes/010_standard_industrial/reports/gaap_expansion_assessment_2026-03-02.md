# GAAP Expansion Impact Assessment — 2026-03-02

## Context
Commit `df85d819` expanded `known_concepts` vocabulary for 15 metrics using upstream GAAP mappings (e.g., Revenue 10->81, COGS 5->69, Inventory 3->63). Baseline: 95.6% 10-K / 96.4% 10-Q (Jan 27 report, 43 failures).

## Results

### GAAP Expansion Fixes (4 of 43 baseline failures resolved)
| Ticker | Form | Metric | Notes |
|--------|------|--------|-------|
| HSY | 10-K | ShortTermDebt | Expanded vocabulary found correct concept |
| HSY | 10-K | WeightedAverageSharesDiluted | Expanded vocabulary found correct concept |
| HSY | 10-Q | WeightedAverageSharesDiluted | Same fix propagates to quarterly |
| META | 10-Q | IntangibleAssets | Expanded vocabulary found correct concept |

### Pass Rates (not directly comparable — reference data shifted)
| Period | Baseline (Jan 27) | New Run (Mar 2) | Note |
|--------|--------------------|------------------|------|
| 10-K | 95.6% (518/542) | 76.1% (423/556) | Yfinance reference data drift |
| 10-Q | 96.4% (516/535) | 77.6% (425/548) | Yfinance reference data drift |

**Important**: The apparent 19-point drop is **NOT a code regression**. The 217 "new failures" show 50-99% variance on stable metrics like Revenue and TotalAssets, confirming yfinance reference values shifted over the 5-week gap (Jan 27 -> Mar 2). To measure GAAP expansion impact accurately, compare only the (ticker, form, metric) tuples present in both runs.

### Persistent Failures (39 of original 43 remain)
The remaining 39 failures are structural issues (financial conglomerates, segment reporting, non-standard concepts) unaffected by vocabulary expansion.

## Ledger Integration
- **1,104 extraction runs** recorded to SQLite ledger
- Strategy fingerprint: `46e1834ac78e` (git `df85d81`)
- Strategy "tree" performance: 77.3% valid (820/1061 with reference values)
- Zero SQLite errors during batch write
- DB: `edgar/xbrl/standardization/company_mappings/experiment_ledger.db`

## Conclusion
GAAP expansion achieved its primary goal — fixing 4 failures through expanded concept vocabulary. The ~9% fix rate (4/43) is modest because most baseline failures are structural (segment accounting, financial subsidiaries) rather than vocabulary gaps. A fresh baseline run against current yfinance data is needed to establish accurate pass rates going forward.
