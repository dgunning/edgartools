# XBRL Concept Mapping Progress Tracker

This document tracks data coverage improvements over time.

---

## Latest Run: 2026-01-10

| Test Set | Coverage | Matched | Notes |
|----------|----------|---------|-------|
| **S&P25** | 93.6% (294/314) | 275 | BAC exact match |
| **S&P50** | 92.9% (616/663) | 576 | Phase 6 complete |

### Changes Since Last Run

1. **Bank ShortTermDebt** - BAC now matches yfinance exactly (43.39B)
   - Implemented dual-track: yfinance-aligned + economic views
   
2. **OperatingIncome Formula** - Corrected formula (NO D&A)
   - yfinance uses: `GrossProfit - R&D - SGA` (no depreciation)
   
3. **Capex Expanded** - Added intangibles for pharma/tech

---

## Historical Progress

| Date | S&P25 | S&P50 | Key Changes |
|------|-------|-------|-------------|
| 2026-01-10 | 93.6% | 92.9% | Phase 6: Bank dual-track, D&A fix |
| 2026-01-09 | 93.2% | 92.9% | Phase 5: Industry logic module |
| 2026-01-08 | 92.9% | 90.5% | Phase 4: SIC classifications |
| 2026-01-07 | 89.3% | 88.0% | Phase 3: Value validation |

---

## Remaining Gaps (Common Patterns)

| Pattern | Companies | Root Cause |
|---------|-----------|------------|
| ShortTermDebt validation | JPM, GS, C, WFC | Bank composite vs yfinance single-concept |
| OperatingIncome missing | LLY, PFE, MRK | No XBRL tag, calculation uses different revenue |
| Capex validation | V, MA, CVX | Different component aggregation |

---

## Architecture Components

| Component | Status | Location |
|-----------|--------|----------|
| Industry Logic Module | ✓ | `edgar/xbrl/standardization/industry_logic/` |
| Industry Metrics Config | ✓ | `config/industry_metrics.yaml` |
| BankingExtractor | ✓ | Dual-track debt extraction |
| DefaultExtractor | ✓ | Capex+intangibles, OpIncome calc |
