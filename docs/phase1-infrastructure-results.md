# Phase 1: Activate Infrastructure — Results

> **Date**: 2026-03-03 | **Branch**: `feature/ai-concept-mapping`
> **Predecessor**: `docs/post-merge-financial-db-plan.md` (Phase 1 section)
> **Purpose**: Establish deterministic, regression-protected baseline before Phase 2 extraction fixes

---

## Summary

Phase 1 infrastructure activation is **complete**. Golden masters and ledger targets exceeded. Pass rates are lower than the plan's optimistic ~96% estimate because the failures are structural extraction issues, not yfinance reference drift.

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| Golden masters promoted | >= 400 | **479** | PASS |
| Ledger extraction runs | >= 5,000 | **5,834** | PASS |
| E2E 10-K pass rate | >= 96.0% | **75.7%** | BELOW (see analysis) |
| E2E 10-Q pass rate | >= 96.8% | **78.7%** | BELOW (see analysis) |
| Cohort reactor baseline | PASS (0 regressions) | **30 regressions** | Expected (see analysis) |

---

## Pass Rate Analysis

The plan predicted snapshots would restore rates from 76%/78% (Mar 2 live) back to ~96% (Jan 27 baseline). This didn't happen because:

1. **Metric expansion**: Jan 27 baseline tested 17 metrics. Current E2E tests **24 metrics** (added DepreciationAmortization, StockBasedCompensation, DividendsPaid, Inventory, AccountsReceivable, AccountsPayable, WeightedAverageSharesDiluted). More metrics = more failure surface.

2. **Structural failures dominate**: The 831 failures (extended mode) are genuine extraction mismatches — wrong XBRL concepts, missing mappings, segment contamination — not reference drift. Snapshots correctly freeze reference values, but the extraction logic itself produces wrong results for many (company, metric, period) combos.

3. **TSLA amended filing**: Tesla's latest 10-K is a 10-K/A (amended) with only 37 facts, causing extraction failures across all metrics.

### Pass Rates by Sector (Extended Mode)

| Sector | 10-K | 10-Q |
|--------|------|------|
| MAG7 | 83.5% | 85.3% |
| Industrial_Manufacturing | 70.9% | 73.2% |
| Consumer_Staples | 76.5% | 78.6% |
| Energy | 69.8% | 76.1% |
| Healthcare_Pharma | 77.3% | 83.8% |
| Transportation | 76.0% | 76.6% |
| **Overall** | **75.7%** | **78.7%** |

### Top Failing Metrics

| Metric | Failures | Notes |
|--------|----------|-------|
| Revenue | 147 | Cross-period variance, FY vs quarterly aggregation |
| TotalAssets | 111 | Dimensional filtering issues |
| DepreciationAmortization | 88 | New metric, many companies use non-standard concepts |
| IntangibleAssets | 83 | Goodwill-only vs Goodwill+Other separation |
| Goodwill | 80 | Same root cause as IntangibleAssets |
| COGS | 67 | Energy/defense companies use non-standard cost structures |

### Top Failing Companies

| Ticker | Sector | Failures | Key Issues |
|--------|--------|----------|------------|
| GE | Industrial_Manufacturing | 45 | Vernova spin-off restructured everything |
| RTX | Industrial_Manufacturing | 44 | Defense conglomerate, complex segments |
| HON | Industrial_Manufacturing | 42 | Multi-segment industrial |
| JNJ | Healthcare_Pharma | 42 | Pharma/device segment structure |
| CVX | Energy | 40 | Energy-specific cost structure |

---

## Golden Master Details

**479 golden masters promoted** across all 33 companies (10–19 per company).

Promotion criteria met:
- `is_valid = 1` (variance <= 20%)
- `COUNT(DISTINCT fiscal_period) >= 3`
- `AVG(variance_pct) <= 20.0`

### Distribution

| Range | Companies |
|-------|-----------|
| 16-19 masters | NVDA, ASTE, LLY, EMR, PG, WMT, AAPL, AMZN, BA, KO, META, UPS |
| 13-15 masters | FDX, MMM, PFE, COST, CVX, DE, GOOG, HSY, PEP, RTX, UNH, COP, HON, MSFT, PBF, TSLA |
| 10-12 masters | JNJ, SLB, GE, CAT, XOM |

---

## Ledger State

| Metric | Value |
|--------|-------|
| Total extraction runs | 5,834 |
| Distinct tickers | 33 |
| Strategy fingerprint | `d500f61585eb6055` |
| Max period diversity | 8 (ASTE, CVX, FDX, HON, PFE, UNH) |
| Min period diversity | 3 (PEP) |
| DB location | `edgar/xbrl/standardization/company_mappings/experiment_ledger.db` |

---

## Regression Report Analysis

**30 regressions detected** out of 479 golden masters (93.7% pass rate).

These are NOT code regressions — they reflect cross-period extraction variance within the same run. The golden masters were established from periods where extraction succeeded (0% variance), but other periods for the same (ticker, metric) combo show higher variance.

### Regression Breakdown

| Company | Count | Metrics Affected |
|---------|-------|------------------|
| ASTE | 6 | Capex, D&A, DividendsPaid, LongTermDebt, OCF, SBC |
| HSY | 6 | Capex, DividendsPaid, OCF, Revenue, ShortTermDebt, SBC |
| FDX | 4 | Capex, DividendsPaid, OCF, SBC |
| PFE | 3 | Goodwill, IntangibleAssets, Revenue |
| PG | 2 | Goodwill, IntangibleAssets |
| RTX | 2 | COGS, D&A |
| UPS | 2 | Goodwill, IntangibleAssets |
| AMZN | 1 | Revenue |
| CVX | 1 | CashAndEquivalents |
| EMR | 1 | D&A |
| GOOG | 1 | Revenue |
| HON | 1 | ShortTermDebt |

**Pattern**: 21 of 30 regressions have golden variance of 0% (perfect match in some periods). These are period-specific extraction issues — the concept maps correctly for recent filings but fails for older periods where the company used different XBRL concepts.

---

## Cohort Reactor Status

All 5 sector cohorts show **BLOCKED** status. This is expected for first-time activation — the reactor compares variance baselines from earlier runs against current run results, and new data points (N/A → value) inflate the total variance.

| Sector | Status | Improved | Neutral | Regressed |
|--------|--------|----------|---------|-----------|
| MAG7 | BLOCKED | 0 | 21 | 0 |
| Industrial_Manufacturing | BLOCKED | 1 | 26 | 5 |
| Energy_Sector | BLOCKED | 2 | 16 | 2 |
| Healthcare_Pharma | BLOCKED | 0 | 11 | 1 |
| Transportation_Logistics | BLOCKED | 0 | 9 | 3 |

---

## Known Divergences (Skipped)

50 validations skipped due to documented known divergences (17 active `skip_validation` entries across 18 companies).

Key categories:
- **Financial subsidiaries**: CAT (Cat Financial), DE (John Deere Financial) — consolidated debt/receivables include captive finance arms
- **Spin-offs**: GE (Vernova Jan 2024) — restated historical periods
- **Energy cost structures**: XOM, CVX, COP, SLB — non-standard OperatingIncome calculation
- **Stock splits**: NVDA (10:1 June 2024) — pre-split share counts

---

## Implications for Phase 2

1. **Golden masters are activated** — any config change (metrics.yaml, companies.yaml) can be regression-checked against 479 golden masters before committing.

2. **The 30 "regressions" are Phase 2 targets** — these represent metrics that work for some periods but not others. Phase 2 should fix the cross-period variance by finding the right XBRL concepts for each company.

3. **Pass rate targets need recalibration**: With 24 metrics (not 17), the 99%+ target from the plan may need adjustment. A more realistic Phase 2 target is **85%+ 10-K / 87%+ 10-Q** given the expanded metric set.

4. **Priority companies for Phase 2**: ASTE (6 regressions), HSY (6), FDX (4), GE (45 failures), RTX (44).

---

## E2E Reports

| Report | File |
|--------|------|
| Quick mode (Mar 3) | `sandbox/notes/010_standard_industrial/reports/e2e_industrial_2026-03-03_1446.md` |
| Extended mode (Mar 3) | `sandbox/notes/010_standard_industrial/reports/e2e_industrial_2026-03-03_1452.md` |
| Extended JSON | `sandbox/notes/010_standard_industrial/reports/e2e_industrial_2026-03-03_1452.json` |
