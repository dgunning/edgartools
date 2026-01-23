# Post-Implementation Failure Analysis
## Banking GAAP Extraction - Architect Directives Implementation
**Date:** 2026-01-23
**Test Run:** e2e_banks_2026-01-23_1209
**Author:** AI Implementation Team
**For Review By:** Principal Financial Systems Architect

---

## Executive Summary

We implemented the 5 Architect Directives. The 10-K pass rate **decreased from 81.8% to 72.7%** primarily due to **Directive #2 (Structural Linkbase Check)** not working as expected for Wells Fargo.

| Metric | Before Implementation | After Implementation | Change |
|--------|----------------------|---------------------|--------|
| 10-K Pass Rate | 81.8% (18/22) | 72.7% (16/22) | **-9.1%** |
| 10-Q Pass Rate | 90.0% (27/30) | 93.3% (28/30) | +3.3% |
| ShortTermDebt Failures | 7 | 8 | +1 |
| CashAndEquivalents Failures | 0 | 0 | No change |

---

## Root Cause: Directive #2 Regression

### What Changed

**BEFORE (Magnitude Heuristic):**
```python
# Old logic in extract_short_term_debt_gaap()
contamination = repos + trading_liab
should_subtract = (
    archetype != 'dealer' and
    stb > 0 and
    contamination > stb * 0.1 and      # Contamination is significant
    contamination < stb * 1.5          # Sanity check
)
```

For WFC with STB=$108.8B, Repos=$54B, TradingLiab=$48B:
- contamination = $102B
- $102B > $108.8B × 0.1 = $10.9B ✓
- $102B < $108.8B × 1.5 = $163.2B ✓
- **Result: should_subtract = True → Clean STB = $6.8B** ✓

**AFTER (Structural Linkbase Check):**
```python
# New logic per Directive #2
repos_nested = self._is_concept_nested_in_stb(xbrl, 'SecuritiesSoldUnderAgreementsToRepurchase')
trading_nested = self._is_concept_nested_in_stb(xbrl, 'TradingLiabilities')

# Only subtract if structurally nested
should_subtract = (
    archetype not in ['dealer', 'hybrid'] and
    contamination_to_subtract > 0
)
```

For WFC:
- `_is_concept_nested_in_stb()` returns **False** for both repos and trading
- contamination_to_subtract = 0
- **Result: should_subtract = False → Clean STB = $108.8B** ✗

### Why the Structural Check Returns False

The `_is_concept_nested_in_stb()` method checks:
1. **Calculation Linkbase** - Looking for parent/child relationships
2. **Presentation Linkbase** - Looking for visual indentation
3. **Default** - If not found in either, assume SIBLING (no subtraction)

For WFC, the check returns False because:
- WFC's XBRL may not have standard calculation/presentation linkbase trees
- The concept names may use different namespaces (wfc: vs us-gaap:)
- The tree lookup logic may not be finding the correct node structure

### Impact on Pass Rates

| Company | Before | After | Cause |
|---------|--------|-------|-------|
| WFC 10-K 2024 | PASS | **FAIL** (701.8% variance) | Structural check → no subtraction |
| WFC 10-K 2023 | PASS | **FAIL** (653.7% variance) | Structural check → no subtraction |
| WFC 10-Q Q3 2025 | FAIL | FAIL (worse) | Same issue |
| WFC 10-Q Q2 2025 | FAIL | FAIL (worse) | Same issue |
| USB 10-K 2024 | PASS | **FAIL** (103.5% variance) | Structural check behavior |
| USB 10-K 2023 | PASS | **FAIL** (33.4% variance) | Structural check behavior |

**Net Result:** 4 additional 10-K failures, 1 fewer 10-Q failure (JPM fixed by hybrid archetype)

---

## What's Working

### Directive #1: Data Integrity Gate ✓
Successfully catching zero-fact filings:
```
DATA INTEGRITY FAILURE: STT filing has 0 facts - corrupt or unsupported format
DATA INTEGRITY FAILURE: BK filing has 0 facts - corrupt or unsupported format
```
This is **new protection** that didn't exist before.

### Directive #3: Hybrid Archetype Configuration ✓
- JPM: Changed from `commercial` to `hybrid` with `subtract_repos_from_stb: false`
- **Before:** JPM 10-K failed due to incorrect repos subtraction
- **After:** JPM 10-K **PASSES** ($64.5B matches yfinance)

### Directive #4: Dimensional Fallback (Partial)
- Code implemented but not triggering for STT
- The 2023 STT filing still fails because a (wrong) consolidated value is found first

### Directive #5: BGS-20 Schema ✓
- Created ground truth schema for future validation
- No runtime impact on pass rates

---

## Detailed Failure Analysis

### Failures Caused by Directive #2 Change

| Ticker | Period | Form | XBRL Value | yfinance | Variance | Before Status |
|--------|--------|------|------------|----------|----------|---------------|
| WFC | 2024-12-31 | 10-K | $108.8B | $13.6B | 701.8% | **PASS** |
| WFC | 2023-12-31 | 10-K | $89.6B | $11.9B | 653.7% | **PASS** |
| WFC | 2025-09-30 | 10-Q | $230.6B | $36.4B | 533.5% | FAIL |
| WFC | 2025-06-30 | 10-Q | $188.0B | $34.0B | 453.2% | FAIL |
| USB | 2024-12-31 | 10-K | $15.5B | $7.6B | 103.5% | **PASS** |
| USB | 2023-12-31 | 10-K | $15.3B | $11.5B | 33.4% | **PASS** |

### Pre-Existing Failures (Unchanged)

| Ticker | Period | Form | XBRL Value | yfinance | Variance | Notes |
|--------|--------|------|------------|----------|----------|-------|
| GS | 2024-12-31 | 10-K | $69.7B | $90.6B | 23.1% | Methodology deviation |
| STT | 2023-12-31 | 10-K | $1.87B | $4.6B | 59.7% | Dimensional fallback needed |

---

## Recommendations

### Option A: Restore Magnitude Heuristic as Fallback (Recommended)

Add magnitude check when structural check returns "sibling" for commercial banks:

```python
# If structural check returns False for both repos and trading,
# fall back to magnitude heuristic for commercial banks
if archetype == 'commercial' and not repos_nested and not trading_nested:
    contamination = repos + trading_liab
    if contamination > stb * 0.1 and contamination < stb * 1.5:
        # Magnitude suggests nesting despite linkbase not showing it
        should_subtract = True
        notes += " [magnitude fallback]"
```

**Expected Impact:** Restore WFC and USB to passing status.

### Option B: Add WFC to Config Override

Add explicit extraction rules in companies.yaml:

```yaml
WFC:
  extraction_rules:
    subtract_repos_from_stb: true
    subtract_trading_from_stb: true
```

**Pros:** Deterministic, no heuristic
**Cons:** Requires manual config for each bank with this pattern

### Option C: Debug and Fix Linkbase Check

Investigate why WFC's linkbase doesn't match expected structure:
1. Log the actual calculation/presentation tree structure
2. Identify namespace or naming mismatches
3. Fix the tree traversal logic

**Pros:** Fixes root cause
**Cons:** Time-intensive, may reveal XBRL filing inconsistencies

---

## Decision Required

The Architect Directive #2 stated:
> "If absent in both [linkbases], assume SIBLING (Do Not Subtract)"

However, this default assumption is causing regressions for commercial banks like WFC where the XBRL linkbase structure doesn't explicitly show the nesting relationship.

**Question for Review:**
1. Should we add the magnitude heuristic as a fallback (Option A)?
2. Should we use config overrides for specific banks (Option B)?
3. Should we investigate the linkbase structure further (Option C)?

---

## Test Commands for Verification

```bash
# Full E2E test
python .claude/skills/bank-sector-test/scripts/run_bank_e2e.py --metrics ShortTermDebt,CashAndEquivalents

# WFC-specific debug to see structural check behavior
python -c "
from edgar import Company, set_identity
set_identity('test@example.com')
from edgar.xbrl.standardization.industry_logic import BankingExtractor

c = Company('WFC')
xbrl = c.get_filings(form='10-K').latest().xbrl()
facts_df = xbrl.facts.to_dataframe()

extractor = BankingExtractor()

# Test structural check
repos_nested = extractor._is_concept_nested_in_stb(xbrl, 'SecuritiesSoldUnderAgreementsToRepurchase')
trading_nested = extractor._is_concept_nested_in_stb(xbrl, 'TradingLiabilities')
print(f'WFC repos nested: {repos_nested}')      # Returns False (causing issue)
print(f'WFC trading nested: {trading_nested}')  # Returns False (causing issue)

result = extractor.extract_short_term_debt_gaap(xbrl, facts_df)
print(f'WFC result: \${result.value/1e9:.1f}B (expected ~\$13.6B)')
print(f'Notes: {result.notes}')
"
```

---

## Appendix: Code Changes Made

### Files Modified

| File | Lines | Change |
|------|-------|--------|
| `reference_validator.py` | +30 | Data Integrity Gate |
| `industry_logic/__init__.py` | +374 | Structural check + archetype + dimensional |
| `config/companies.yaml` | +36 | Hybrid archetype for JPM/BAC/C |
| `config/golden_set/banking_bgs20.yaml` | +200 | New ground truth schema |

### Key Method Added (Causing Regression)

```python
def _is_concept_nested_in_stb(self, xbrl, concept: str) -> bool:
    """
    Dual-Check Strategy: Determine if a concept is nested inside ShortTermBorrowings.

    Check Order:
    1. Calculation Linkbase - definitive parent/child
    2. Presentation Linkbase - visual indentation
    3. Default: Assume SIBLING (Do Not Subtract)  ← THIS IS THE ISSUE
    """
```

---

## Conclusion

The implementation of Directive #2 (Structural Linkbase Check) replaced the working magnitude heuristic with a linkbase-based approach that defaults to "sibling" when relationships aren't explicitly found. This caused WFC and USB regressions because their XBRL filings don't have the expected linkbase structure.

**Recommended immediate action:** Add magnitude heuristic as fallback (Option A) to restore pass rates while investigating the linkbase structure.
