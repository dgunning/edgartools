# XBRL Concept Mapping Progress Tracker

This document tracks data coverage improvements over time.

---

## Latest Run: 2026-01-20 (Multi-Period Validation)

| Test Set | 10-K Pass Rate | 10-Q Pass Rate | Notes |
|----------|----------------|----------------|-------|
| **S&P25** | **86.9%** (741/853) | **72.1%** (782/1084) | 5 Years + 6 Quarters |
| **S&P50** | **85.8%** (1704/1986) | **70.7%** (1641/2321) | 5 Years + 6 Quarters |

### Changes Since Last Run

1. **Multi-Period E2E Test Expansion**
   - Now tests 5 years of 10-K + 6 quarters of 10-Q per company
   - Date-aware validation in `ReferenceValidator`
   - Quarterly yfinance data support

2. **LLY Capex Fix** (JSON Override)
   - Confirmed robust across 3 years (2022-2024)
   - Consistently uses `OtherPPE`

3. **LLY ShortTermDebt** (Hybrid Logic)
   - Confirmed robust across 3 years
   - Validates correctly against composite sums

---

## Current Status (by Metric)

### OperatingIncome ✓ RESOLVED
All 7 companies pass.

### IntangibleAssets ✓ RESOLVED  
All 7 companies pass.

### Capex ✓ RESOLVED
All 7 companies pass.

### ShortTermDebt - Pending Re-Evaluation

| Ticker | Status | Components |
|--------|--------|------------|
| **LLY** | Valid | DebtCurrent ($5.12B) |
| **KO** | **FAIL** | Reverted fixes |
| **CVX** | **FAIL** | Reverted documentation |
| **NVDA** | Accepted | Definition Mismatch |
| **GOOG** | Accepted | Definition Mismatch |

---

## Historical Progress

| Date | S&P25 | Key Changes |
|------|-------|-------------|
| 2026-01-20 (v3) | ~96% | **Systematic debugging**: CVX Capex, KO IntangibleAssets, ShortTermDebt docs |
| 2026-01-20 (v2) | ~94% | OperatingIncome complete fix: calculated fallback |
| 2026-01-20 | 91.4% | KO OperatingIncome fix: yfinance GAAP field |
| 2026-01-10 (v2) | 91.6% | Sprint 1+2: DimensionalAggregator, PiT, Industry Extractors |
| 2026-01-10 | 93.6% | Phase 6: Bank dual-track, D&A fix |
| 2026-01-09 | 93.2% | Phase 5: Industry logic module |

---

## Architecture Components

| Component | Status | Location |
|-----------|--------|----------|
| DimensionalAggregator | ✓ NEW | `layers/dimensional_aggregator.py` |
| PiT Filing Handler | ✓ NEW | `reference_validator.py` |
| SaaSExtractor | ✓ NEW | `industry_logic/__init__.py` |
| InsuranceExtractor | ✓ NEW | `industry_logic/__init__.py` |
| Signage Normalization | ✓ NEW | `layers/tree_parser.py` |
| Internal Validator | ✓ NEW | `internal_validator.py` |
| Industry Logic Module | ✓ | `industry_logic/__init__.py` |
| BankingExtractor | ✓ | Dual-track debt extraction |
| DefaultExtractor | ✓ | Capex+intangibles, OpIncome calc |
