---
name: standard-industrial-test
description: "Run E2E validation for 30 standard industrial companies across 6 sectors against yfinance. Use for testing Archetype A (Standard Industrial) extraction strategies."
---

# Standard Industrial E2E Test

## Overview
This skill runs a standardized End-to-End (E2E) validation test for 33 major industrial companies across 6 sectors. It verifies XBRL concept mappings against yfinance data for:

- **MAG7**: AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA (7 companies)
- **Industrial Manufacturing**: CAT, GE, HON, DE, MMM, EMR, RTX, ASTE (8 companies)
- **Consumer Staples**: PG, KO, PEP, WMT, COST, HSY (6 companies)
- **Energy**: XOM, CVX, COP, SLB, PBF (5 companies)
- **Healthcare/Pharma**: JNJ, UNH, LLY, PFE (4 companies)
- **Transportation**: UPS, FDX, BA (3 companies)

**Scope**: 2 years of 10-Ks, 2 quarters of 10-Qs
**Target Metrics** (17 total):
- Income Statement: Revenue, COGS, SGA, OperatingIncome, PretaxIncome, NetIncome
- Cash Flow: OperatingCashFlow, Capex
- Balance Sheet: TotalAssets, Goodwill, IntangibleAssets, ShortTermDebt, LongTermDebt, CashAndEquivalents
- Derived: FreeCashFlow, TangibleAssets, NetDebt

## When to Use This Skill
- After modifying core extraction logic in `standardization/` for non-banking companies.
- After updating `metrics.yaml` with new concept mappings.
- Before merging changes that affect standard industrial companies.
- To verify that banking-specific changes haven't regressed standard companies.
- To establish baseline pass rates for Archetype A companies.

## How to Run

From the project root:

```bash
# Run standard industrial test (all 33 companies)
// turbo
python run_industrial_e2e.py

# Run for specific sector only
// turbo
python run_industrial_e2e.py --sector MAG7
python run_industrial_e2e.py --sector Energy

# Run for specific tickers
// turbo
python run_industrial_e2e.py --tickers AAPL,XOM,CAT

# Run for specific metrics only
// turbo
python run_industrial_e2e.py --metrics ShortTermDebt,Capex
```

## Sectors

| Sector | Companies | Notes |
|--------|-----------|-------|
| MAG7 | AAPL, MSFT, GOOG, AMZN, META, NVDA, TSLA | Tech benchmark (Archetype C in config) |
| Industrial_Manufacturing | CAT, GE, HON, DE, MMM, EMR, RTX, ASTE | Pure Archetype A baseline |
| Consumer_Staples | PG, KO, PEP, WMT, COST, HSY | Retail/food patterns |
| Energy | XOM, CVX, COP, SLB, PBF | Capex-heavy patterns |
| Healthcare_Pharma | JNJ, UNH, LLY, PFE | R&D capitalization |
| Transportation | UPS, FDX, BA | Asset-heavy operations |

## Reports
Reports are generated in: `sandbox/notes/010_standard_industrial/reports/`

1. **`e2e_industrial_YYYY-MM-DD_HHMM.json`**: Detailed failure log with sector breakdowns.
2. **`e2e_industrial_YYYY-MM-DD_HHMM.md`**: Markdown summary with pass rates by sector.

### Analyzing Failures

Use the `analyze_failures.py` script to get a detailed breakdown of failures:

```bash
# Analyze most recent report (auto-detects latest JSON)
python analyze_failures.py

# Analyze specific report
python analyze_failures.py sandbox/notes/010_standard_industrial/reports/e2e_industrial_2026-01-25_1430.json
```

**Sample Output:**
```
Report: e2e_industrial_2026-01-25_1430.json
Total failures: 24

============================================================
Pass Rates by Sector
============================================================
  MAG7:                    10-K 92.5% (12/13) | 10-Q 88.0% (22/25)
  Industrial_Manufacturing: 10-K 95.0% (19/20) | 10-Q 90.0% (36/40)
  Energy:                  10-K 100.0% (8/8)  | 10-Q 93.8% (15/16)
  ...

============================================================
ShortTermDebt Failures (8)
============================================================
  NVDA  (10-K): XBRL=   2.5B, Ref=   1.8B, Variance=  38.9% [OVER]
  TSLA  (10-Q): XBRL=   1.2B, Ref=   0.9B, Variance=  33.3% [OVER]
  ...
```

## Troubleshooting

- **High MAG7 variance**: MAG7 companies are Archetype C (Intangible Digital) but tested with Archetype A strategies. Some variance is expected.
- **Capex mismatches in Energy**: Check `PaymentsToAcquireProductiveAssets` vs `PaymentsToAcquirePropertyPlantAndEquipment` concept usage.
- **R&D issues in Pharma**: Some pharma companies capitalize R&D differently; check for `ResearchAndDevelopmentInProcess` concepts.
- **Lease-related variances in Retail**: Operating vs. finance lease classification can cause Asset/Liability mismatches.
