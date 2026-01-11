# XBRL Concept Mapping Progress Tracker

This document tracks data coverage improvements over time.

---

## Latest Run: 2026-01-10 (Post-Architecture Improvements)

| Test Set | Coverage | Matched | Notes |
|----------|----------|---------|-------|
| **S&P25** | 91.6% (307/335) | 265 | +2 metrics resolved |
| **S&P50** | 91.5% (626/684) | 518 | +3 metrics resolved |

### Changes Since Last Run

1. **Architecture Improvements (Sprint 1+2)**
   - DimensionalAggregator: Handles JPM-style dimensional gaps
   - PiT Filing Handling: Uses most recent filing date for restatements
   - SaaS/Insurance Extractors: Industry-specific metric extraction
   - Signage Normalization: Balance type awareness (40+ concepts)
   - Internal Consistency Validator: Pre-yfinance accounting equation checks

2. **Metrics Resolved This Run**
   - BRK-B Revenue: us-gaap:Revenues (12.4% variance)
   - JPM LongTermDebt: us-gaap:LongTermDebt (3.0% variance)
   - PFE Revenue: us-gaap:Revenues (0.0% variance - exact match!)

3. **Coverage Note**
   - Coverage appears lower than previous (93.6% → 91.6%) due to stricter validation
   - Previous runs included mappings without value validation
   - Current runs require yfinance match within tolerance

---

## Historical Progress

| Date | S&P25 | S&P50 | Key Changes |
|------|-------|-------|-------------|
| 2026-01-10 (v2) | 91.6% | 91.5% | Sprint 1+2: DimensionalAggregator, PiT, Industry Extractors |
| 2026-01-10 | 93.6% | 92.9% | Phase 6: Bank dual-track, D&A fix |
| 2026-01-09 | 93.2% | 92.9% | Phase 5: Industry logic module |
| 2026-01-08 | 92.9% | 90.5% | Phase 4: SIC classifications |
| 2026-01-07 | 89.3% | 88.0% | Phase 3: Value validation |

---

## Remaining Gaps (Common Patterns)

| Pattern | Companies | Root Cause |
|---------|-----------|------------|
| ShortTermDebt validation | 15+ companies | yfinance composite vs XBRL single-concept |
| OperatingIncome | LLY, PFE, MRK, CVX, KO | Different calculation methodology |
| Capex | V, MA, HD, JNJ | PaymentsToAcquirePPE not matching yfinance |
| IntangibleAssets | TSLA, KO, PEP | Goodwill vs IntangibleAssets separation |
| COGS | XOM, VZ, GE | Energy/telecom industry-specific |

### Patterns Discovered (New Concept Candidates)

| Metric | Candidates Found |
|--------|------------------|
| ShortTermDebt | LongTermDebt, ShortTermInvestments, ShorttermDebtFairValue |
| OperatingIncome | OperatingIncomeLoss, NonoperatingIncomeExpense |
| IntangibleAssets | OtherIntangibleAssetsNet, FiniteLivedIntangibleAssetsNet |
| CashAndEquivalents | CashAndCashEquivalentsAtCarryingValue, RestrictedCashAndCashEquivalents |

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
