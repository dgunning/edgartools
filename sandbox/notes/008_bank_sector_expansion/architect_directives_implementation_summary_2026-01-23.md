# Architect Directives Implementation Summary
## Banking GAAP Extraction Improvements
**Date:** 2026-01-23
**Status:** Implemented (Pending Refinement)

---

## Overview

Following the Principal Financial Systems Architect's review of the Code Red remediation, we implemented 5 directives to address ShortTermDebt failures and establish robust infrastructure for future development.

### Pre-Implementation State
- 10-K Pass Rate: 81.8% (18/22)
- 10-Q Pass Rate: 90.0% (27/30)
- ShortTermDebt Failures: 7 (GS: 1, STT: 1, USB: 1, WFC: 4)

### Post-Implementation State
- 10-K Pass Rate: 72.7% (16/22)
- 10-Q Pass Rate: 93.3% (28/30)
- ShortTermDebt Failures: 8

---

## Directives Implemented

### Directive #1: Data Integrity Gate (P0)

**File:** `edgar/xbrl/standardization/reference_validator.py`

**Implementation:**
Added validation at the start of `_try_industry_extraction()`:
- Checks if facts_df is None or empty (0 facts)
- Logs `DATA INTEGRITY FAILURE` warning
- Checks if facts count < 100 (minimum threshold)
- Logs `DATA INTEGRITY WARNING` for low-fact filings

**Code Added:**
```python
# DATA INTEGRITY GATE (P0)
MIN_FACTS_THRESHOLD = 100  # Typical 10-K has 1000+ facts
if facts_df is None or len(facts_df) == 0:
    logger.warning(f"DATA INTEGRITY FAILURE: {ticker} filing has 0 facts - corrupt or unsupported format")
    return None

if len(facts_df) < MIN_FACTS_THRESHOLD:
    logger.warning(f"DATA INTEGRITY WARNING: {ticker} filing has only {len(facts_df)} facts...")
```

**Verification:** Successfully catching STT and BK zero-fact filings in E2E test.

---

### Directive #2: Dual-Check Strategy for Repos (P0)

**File:** `edgar/xbrl/standardization/industry_logic/__init__.py`

**Implementation:**
Added `_is_concept_nested_in_stb()` method to BankingExtractor:
1. Check Calculation Linkbase for parent/child relationship
2. Check Presentation Linkbase for visual indentation
3. Default to SIBLING if not found in either

**Code Added:** ~80 lines for linkbase tree traversal

**Modified:** `extract_short_term_debt_gaap()` to use structural check instead of magnitude heuristic:
```python
# OLD (fragile): contamination < stb * 1.5
# NEW (structural): Check linkbase trees for nested relationship
repos_nested = self._is_concept_nested_in_stb(xbrl, 'SecuritiesSoldUnderAgreementsToRepurchase')
trading_nested = self._is_concept_nested_in_stb(xbrl, 'TradingLiabilities')
```

**Issue Discovered:** The structural check is not working as expected for WFC - returns "sibling" when repos/trading should be subtracted. See failure analysis for details.

---

### Directive #3: Hybrid Archetype Configuration (P1)

**Files:**
- `edgar/xbrl/standardization/config/companies.yaml`
- `edgar/xbrl/standardization/industry_logic/__init__.py`

**Implementation:**

1. **Updated companies.yaml** for JPM, BAC, C:
```yaml
JPM:
  bank_archetype: "hybrid"
  archetype_override: true  # Prevents dynamic detection
  extraction_rules:
    subtract_repos_from_stb: false  # Repos are separate line items
    cash_includes_ib_deposits: true
    street_debt_includes_net_repos: true
```

2. **Added BankingExtractor methods:**
- `_get_company_config(ticker)` - YAML config lookup
- `_get_archetype(facts_df, ticker)` - Config-based or dynamic detection
- `_get_extraction_rules(ticker)` - Company-specific extraction rules

**Verification:** JPM 10-K ShortTermDebt now PASSES with hybrid archetype.

---

### Directive #4: Dimensional Fallback (P1)

**File:** `edgar/xbrl/standardization/industry_logic/__init__.py`

**Implementation:**
Added methods for handling dimensional breakdowns:

1. `_get_dimensional_sum(facts_df, concept, axis)`:
   - Sums dimensional facts when consolidated value is missing
   - Filters by axis (e.g., ShortTermDebtTypeAxis)
   - Logs dimension breakdown for audit

2. `_should_use_dimensional_fallback(consolidated, dim_sum)`:
   - Returns True if consolidated is None/0
   - Returns True if consolidated < 50% of dimensional sum

**Modified:** `extract_short_term_debt_gaap()` to check dimensional fallback after component aggregation.

**Issue Discovered:** Fallback not triggering for STT because consolidated value exists (even if incorrect).

---

### Directive #5: BGS-20 Schema Foundation (P2)

**File Created:** `edgar/xbrl/standardization/config/golden_set/banking_bgs20.yaml`

**Implementation:**
Created Banking Golden Set schema with:
- Ground truth values from 10-K/10-Q PDF footnotes
- `logic_trace` fields documenting extraction methodology
- `methodology_deviation` flags for known differences from yfinance
- `data_quality_issue` flags for corrupt filings
- Extraction patterns by archetype (commercial, dealer, custodial, hybrid)

**Sample Entry:**
```yaml
WFC:
  company_name: "Wells Fargo & Company"
  archetype: "commercial"
  periods:
    - period: "2024-12-31"
      form: "10-K"
      metrics:
        ShortTermDebt:
          value: 6603000000
          display_value: "$6.6B"
          logic_trace:
            - "Short-Term Borrowings (Face): $108.8B"
            - "Less: Trading Liabilities: $48.0B"
            - "Less: Repos: $54.2B"
            - "Result: $6.6B"
          notes: "yfinance shows $13.6B - methodology difference"
```

---

## Files Modified Summary

| File | Lines Changed | Purpose |
|------|---------------|---------|
| `reference_validator.py` | +30 | Data integrity gate |
| `industry_logic/__init__.py` | +374 | Structural check, archetype, dimensional |
| `config/companies.yaml` | +36 | Hybrid archetype for JPM/BAC/C |
| `config/golden_set/banking_bgs20.yaml` | +200 (new) | Ground truth schema |

---

## Verification Results

### Syntax Checks
- `reference_validator.py` - OK
- `industry_logic/__init__.py` - OK
- `companies.yaml` - OK
- `banking_bgs20.yaml` - OK

### Unit Tests
- BankingExtractor instantiation - PASS
- JPM config lookup - PASS
- JPM archetype from config = "hybrid" - PASS
- JPM extraction rules - PASS
- Industry extractor registry - PASS
- ReferenceValidator instantiation - PASS

### E2E Test Results
- Data Integrity Gate working (catching 0-fact filings)
- Hybrid archetype working (JPM passes)
- CashAndEquivalents 100% pass rate
- Structural linkbase check NOT working for WFC

---

## Known Issues

### 1. Structural Linkbase Check Regression
The `_is_concept_nested_in_stb()` method returns "sibling" for WFC repos/trading, causing massive over-extraction.

**Root Cause:** WFC's XBRL linkbase trees may not have standard structure, or namespace handling is incorrect.

**Recommended Fix:** Add magnitude heuristic as fallback for commercial banks.

### 2. STT Dimensional Fallback Not Triggering
The dimensional fallback checks exist but aren't being triggered because a (wrong) consolidated value is found first.

**Recommended Fix:** Adjust trigger condition to compare against yfinance reference when available.

---

## Next Steps

1. **Immediate (P0):** Add magnitude fallback for commercial banks when structural check returns "sibling" for both repos and trading
2. **Short-term (P1):** Debug WFC linkbase structure to understand why structural check fails
3. **Medium-term (P2):** Populate BGS-20 with additional ground truth values from PDF extraction
4. **Long-term:** Consider ML-based approach for concept relationship detection

---

## Conclusion

The implementation establishes important infrastructure:
- Data integrity validation catches corrupt filings early
- Config-based archetype overrides enable company-specific handling
- Dimensional fallback provides alternative extraction path
- BGS-20 schema enables ground truth validation

However, the **structural linkbase check needs refinement** before it can replace the magnitude heuristic for all commercial banks. The immediate recommendation is to restore the magnitude heuristic as a fallback while investigating why WFC's linkbase structure doesn't match expectations.
