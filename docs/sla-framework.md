# SLA Framework: Subscription-Grade Quality Contract

## Overview

This document defines what "subscription-grade" means for EdgarTools' standardized financial data. It establishes measurable quality tiers, refresh commitments, and compliance monitoring.

## Quality Tiers

### Tier 1: Headline Metrics
**Target: >= 99% Extraction Fidelity (EF)**

| Metric | Description | Refresh SLA |
|--------|-------------|-------------|
| Revenue | Total revenues | 48 hours after 10-K filing |
| NetIncome | Bottom line earnings | 48 hours after 10-K filing |
| TotalAssets | Sum of all assets | 48 hours after 10-K filing |
| OperatingCashFlow | Cash from operations | 48 hours after 10-K filing |
| StockholdersEquity | Total shareholder equity | 48 hours after 10-K filing |
| OperatingIncome | Operating earnings | 48 hours after 10-K filing |
| EPS (Diluted) | Earnings per share | 48 hours after 10-K filing |
| TotalLiabilities | Sum of all liabilities | 48 hours after 10-K filing |

**Quality requirements:**
- Extraction fidelity >= 99% across all covered companies
- Multi-period validated (3+ annual periods)
- Evidence tier: `sec_confirmed` or `yfinance_confirmed`
- Publish confidence: `high`
- Golden master promoted

### Tier 2: Secondary Metrics
**Target: >= 95% Extraction Fidelity (EF)**

All 29 remaining standardized metrics (COGS, SGA, Capex, etc.)

**Quality requirements:**
- Extraction fidelity >= 95% across all covered companies
- At least single-period validated
- Evidence tier: `sec_confirmed`, `yfinance_confirmed`, or `self_validated`
- Publish confidence: `high` or `medium`
- 72-hour refresh SLA after 10-K filing

### Tier 3: Deep/Experimental Metrics
**Target: >= 90% Extraction Fidelity (EF)**

Industry-specific and derived metrics not yet in the standard set.

**Quality requirements:**
- Best-effort extraction
- May include `unverified` evidence tier
- No refresh SLA guaranteed
- Clearly labeled as experimental in API responses

## Evidence Hierarchy

Evidence tiers determine how a metric's value was validated:

1. **`sec_confirmed`**: Value validated against SEC Company Facts API (data.sec.gov). This is the gold standard — SEC-native data is the authoritative source.

2. **`yfinance_confirmed`**: Value validated against Yahoo Finance. Useful for corroboration but not primary truth (yfinance may reformat or derive values differently).

3. **`self_validated`**: Value passed internal accounting equation checks but has no external reference confirmation. Capped at `medium` publish confidence.

4. **`unverified`**: No reference data available. Value is extracted but cannot be independently confirmed.

**Key principle**: SEC-native evidence is first-class. You cannot charge for data that is merely a derivative of Yahoo Finance.

## Publish Confidence Levels

Each metric carries a `publish_confidence` level:

- **`high`**: Known concept + reference match + internal equations pass. Safe for production use. (Never assigned to `self_validated` evidence — that's capped at `medium`.)
- **`medium`**: Reference match OR internal equations pass. Generally reliable but may have edge cases.
- **`low`**: Mapped but unvalidated, or high variance between extraction and reference.
- **`unverified`**: No reference data available. Should not be used in production without disclaimer.

## SLA Compliance Monitoring

The auto-eval dashboard reports SLA compliance:

```
EF-CQS:     0.9500  [TARGET: >= 0.95]
Headline EF: 0.9900  [TARGET: >= 0.99]
RFA Rate:    0.9200
SMA Rate:    0.8800
```

### Compliance Checks

1. **Overall EF-CQS >= 0.95**: Measured on the full evaluation cohort
2. **Headline EF >= 0.99**: Measured on the 8 headline metrics only
3. **Zero regressions**: No previously-golden metric should regress
4. **Multi-period stability**: Golden masters must hold across 3+ annual periods

## Company Coverage

### Current Coverage
- **100-company cohort**: Production-quality extraction for S&P 100 equivalent
- Sectors: Tech, Banking, Energy, Consumer, Healthcare, Industrial, Finance

### Expansion Path
- **500-company cohort** (EXPANSION_COHORT_500): Full S&P 500 scale
- Requires: yfinance snapshot generation + SEC facts cache for all companies
- 10-Q quarterly derivation is a **separate future milestone** (YTD subtraction + restatement handling)

## Operational Cadence

1. **Overnight auto-eval**: Runs nightly to improve extraction quality
2. **LIS-gated changes**: Single-metric fixes use Localized Impact Score, not global CQS
3. **Circuit breakers**: 10 consecutive failures or CQS drop > 0.02 stops the session
4. **Golden master promotion**: Only after 3+ consistent extraction runs
5. **Convergence target**: Log "TARGET MET" when headline_ef >= 0.99 AND ef_cqs >= 0.95
