---
name: bank-sector-test
description: "Run standardized E2E validation for banking sector companies (GSIBs) against yfinance. Use when refining industry logic or verifying banking-specific fixes."
---

# Bank Sector E2E Test

## Overview
This skill runs a standardized End-to-End (E2E) validation test for a predefined list of major banking institutions. It verifies XBRL concept mappings against yfinance data for:
- **Banks**: BK, C, GS, JPM, MS, PNC, STT, USB, WFC
- **Scope**: 2 years of 10-Ks, 2 quarters of 10-Qs
- **Metrics**: All metrics defined in `metrics.yaml` (unless filtered)

## When to Use This Skill
- After modifying `industry_logic/` for banking extraction.
- After updating `industry_metrics.yaml`.
- Before merging changes that affect financial sector companies.
- To verify "Street View" logic (ShortTermDebt, CashAndEquivalents) for banks.

## How to Run

From the project root:

```bash
# Run standard bank test
// turbo
python run_bank_e2e.py

# Run for specific metrics only
// turbo
python run_bank_e2e.py --metrics ShortTermDebt,CashAndEquivalents
```

## Reports
Reports are generated in: `sandbox/notes/008_bank_sector_expansion/reports/`

1. **`e2e_banks_YYYY-MM-DD_HHMM.json`**: Detailed failure log.
2. **`e2e_banks_YYYY-MM-DD_HHMM.md`**: Markdown summary with pass rates and top failure stats.

### Analyzing Failures

Use the `analyze_failures.py` script to get a detailed breakdown of failures:

```bash
# Analyze most recent report (auto-detects latest JSON)
python analyze_failures.py

# Analyze specific report
python analyze_failures.py sandbox/notes/008_bank_sector_expansion/reports/e2e_banks_2026-01-22_1119.json
```

**Sample Output:**
```
Report: e2e_banks_2026-01-22_1119.json
Total failures: 16

============================================================
ShortTermDebt Failures (13)
============================================================
  BK    (10-K): XBRL=   3.3B, Ref=   0.3B, Variance= 996.3% [OVER]
  GS    (10-K): XBRL=   4.6B, Ref=  90.6B, Variance=  94.9% [UNDER]
  WFC   (10-K): XBRL=  24.8B, Ref=  13.6B, Variance=  82.4% [OVER]
  ...

============================================================
Failures by Company
============================================================
  USB: 5 failures
  WFC: 4 failures
  GS: 3 failures
```

## Troubleshooting
- **Execution Path Error**: Check if `fallback_to_tree` is correctly set in `industry_metrics.yaml`.
- **High Variance in Debt**: Check strict deduction logic or "Economic View" consistency (e.g., NetRepos inclusion).
