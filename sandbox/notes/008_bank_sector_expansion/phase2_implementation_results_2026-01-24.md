# Banking GAAP Extraction: Phase 2 Implementation Results
## Post-Implementation E2E Validation

**Date:** 2026-01-24
**Run ID:** e2e_banks_2026-01-24T00:04:33
**Implementation:** Archetype-Driven GAAP Extraction with Suffix Matching

---

## Executive Summary

| Form Type | Before (Phase 1) | After (Phase 2) | Delta |
|-----------|------------------|-----------------|-------|
| **10-K** | 72.7% (16/22) | 81.8% (18/22) | **+9.1%** |
| **10-Q** | 93.3% (28/30) | 80.0% (24/30) | **-13.3%** |

**Key Finding:** The archetype-driven refactoring improved 10-K extraction but introduced regressions in 10-Q extraction.

---

## Pass/Fail by Company

| Ticker | Archetype | 10-K | 10-Q | Status |
|--------|-----------|------|------|--------|
| **GS** | dealer | ✅ PASS | ✅ PASS | Perfect |
| **C** | hybrid | ✅ PASS | ✅ PASS | Perfect |
| **PNC** | commercial | ✅ PASS | ✅ PASS | Perfect |
| **USB** | commercial | ✅ PASS | ❌ FAIL | 10-Q regression |
| **MS** | dealer | N/A (mapping_needed) | ✅ PASS | Partial |
| **BK** | custodial | ⚠️ DATA INTEGRITY | ⚠️ DATA INTEGRITY | Filing issue |
| **STT** | custodial | ❌ FAIL | ⚠️ DATA INTEGRITY | Extraction issue |
| **JPM** | hybrid | ❌ FAIL | ❌ FAIL | Regression |
| **WFC** | commercial | ❌ FAIL | ❌ FAIL | Needs investigation |

---

## Detailed Failure Analysis

### 1. JPM (Hybrid Archetype) - 3 Failures

| Filing | XBRL Value | yfinance Ref | Variance |
|--------|------------|--------------|----------|
| 10-K 2024-12-31 | $49.7B | $64.5B | **-22.9%** |
| 10-Q 2025-09-30 | $0 | $69.4B | **-100%** |
| 10-Q 2025-06-30 | $0 | $65.3B | **-100%** |

**Root Cause:** The hybrid extraction method returns `stb + cpltd` but is getting $0 for 10-Q filings. The `_extract_hybrid_stb()` method doesn't find ShortTermBorrowings in quarterly data.

**Action Required:** Investigate JPM 10-Q structure - likely different concept names or missing STB tag in quarterly filings.

### 2. WFC (Commercial Archetype) - 4 Failures

| Filing | XBRL Value | yfinance Ref | Variance |
|--------|------------|--------------|----------|
| 10-K 2024-12-31 | $6.6B | $13.6B | **-51.3%** |
| 10-K 2023-12-31 | $14.6B | $11.9B | **+23.2%** |
| 10-Q 2025-09-30 | $79.7B | $36.4B | **+119%** |
| 10-Q 2025-06-30 | $78.6B | $34.0B | **+131%** |

**Root Cause:**
- 10-K: Bottom-up extraction finding incomplete components (~$6.6B)
- 10-Q: Top-down extraction NOT subtracting repos/trading properly (extracting full STB ~$80B instead of clean ~$34B)

**Action Required:**
1. Verify `_get_repos_value()` works on 10-Q filings
2. Check if WFC 10-Q uses different namespace/concept names than 10-K

### 3. USB (Commercial Archetype) - 2 Failures

| Filing | XBRL Value | yfinance Ref | Variance |
|--------|------------|--------------|----------|
| 10-Q 2025-09-30 | $0 | $15.4B | **-100%** |
| 10-Q 2025-06-30 | $2.2B | $15.0B | **-85.5%** |

**Root Cause:** Commercial extraction working for 10-K but not 10-Q. Bottom-up finds nothing, top-down finds insufficient components.

**Note:** USB 10-Ks passing ($7.6B and $11.5B matches) confirms annual extraction works.

### 4. STT (Custodial Archetype) - 1 Failure

| Filing | XBRL Value | yfinance Ref | Variance |
|--------|------------|--------------|----------|
| 10-K 2023-12-31 | $2.66B | $4.64B | **-42.6%** |

**Root Cause:** Custodial extraction found some components but not all. The `safe_fallback: false` worked (didn't fuzzy match), but component sum is incomplete.

**Note:** STT 10-K 2024 passed with $9.84B match. The 2023 filing may have different structure.

---

## What Worked Well

### 1. Dealer Banks (GS, MS)
- **GS 10-K:** $90.6B extracted ✓ (match to yfinance)
- Direct UnsecuredSTB extraction working as designed
- No repos subtraction needed (separate line items)

### 2. Citigroup (Hybrid)
- **C 10-K:** $48.5B extracted ✓ (match to yfinance)
- Hybrid extraction with nesting check working correctly

### 3. CashAndEquivalents
- **100% pass rate across all companies**
- No regressions from Phase 1

### 4. Commercial Banks (10-K only)
- **USB:** Both 10-Ks passing
- **PNC:** Both 10-Ks passing
- Bottom-up extraction finding components correctly for annual filings

---

## Issues Identified

### Issue 1: 10-Q Period Filtering
**Symptom:** 10-Q extractions return $0 or wrong values
**Hypothesis:** `_get_fact_value()` may be selecting wrong period in quarterly filings
**Impact:** All commercial/hybrid banks affected

### Issue 2: WFC Namespace Still Problematic for 10-Q
**Symptom:** WFC 10-Q extracts full STB (~$80B) without repos subtraction
**Hypothesis:** Suffix matching not finding wfc: repos in quarterly filings
**Impact:** WFC only (uses wfc: namespace extension)

### Issue 3: Bottom-Up Component Gaps
**Symptom:** Commercial banks have incomplete component sums
**Hypothesis:** Some banks don't report all bottom-up components (CP, FHLB, OtherSTB)
**Impact:** WFC, USB partially

---

## Recommended Next Steps

### Priority 1: Fix 10-Q Period Selection
1. Investigate `_get_fact_value()` period filtering for quarterly filings
2. Add explicit quarterly period targeting (90-day duration)
3. Test with JPM, USB, WFC 10-Q filings

### Priority 2: Debug WFC 10-Q Repos Detection
1. Run diagnostic on WFC 10-Q 2025-09-30 filing
2. Verify `_get_repos_value()` finding wfc: prefixed concepts
3. Check if calculation linkbase exists in 10-Q (may only be in 10-K)

### Priority 3: Add Fallback for Missing Components
1. When bottom-up yields $0, always try top-down for commercial banks
2. Consider adding FederalFundsPurchased to component list
3. Add logging to track which strategy is being used

---

## Code Changes Made (Phase 2)

### Files Modified

1. **`edgar/xbrl/standardization/industry_logic/__init__.py`**
   - Added `ARCHETYPE_EXTRACTION_RULES` dictionary
   - Added `_get_repos_value()` with suffix matching
   - Updated `_is_concept_nested_in_stb()` for namespace resilience
   - Refactored `extract_short_term_debt_gaap()` with archetype dispatch
   - Added archetype-specific extraction methods
   - Added `metadata` field to `ExtractedMetric`

2. **`edgar/xbrl/standardization/config/companies.yaml`**
   - Added `archetype_override: true` for all banks
   - Added `extraction_rules` with `safe_fallback` settings
   - Added `check_nesting: true` for hybrid banks
   - Set `safe_fallback: false` for custodial banks (BK, STT)

---

## Appendix: Raw E2E Output

```
Banking: 10-K 81.8% (18/22), 10-Q 80.0% (24/30)

Failures by Company:
- WFC: 4 failures (2 10-K, 2 10-Q)
- JPM: 3 failures (1 10-K, 2 10-Q)
- USB: 2 failures (2 10-Q)
- STT: 1 failure (1 10-K)

BK/STT: DATA INTEGRITY FAILURE (0 facts) - filing format issue, not extraction
```

---

*Report generated: 2026-01-24*
*Based on: E2E run e2e_banks_2026-01-24T00:04:33*
