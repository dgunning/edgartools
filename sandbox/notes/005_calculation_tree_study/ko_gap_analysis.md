# KO (Coca-Cola) OperatingIncome Gap Analysis

## Summary

**XBRL Value**: $9.99B (GAAP OperatingIncomeLoss)  
**yfinance Value**: $14.02B (Non-GAAP "Comparable Operating Income")  
**Gap**: $4.03B (28.7%)

**Resolution Status**: DATA_SOURCE_MISMATCH - Requires RAG system for 8-K earnings release parsing

---

## Investigation Findings

### 1. The "Golden Source" Tag Does Not Exist in XBRL

Searched KO's 10-K for custom tags:
- Found 76 `ko:` namespace concepts
- **None** contain "Comparable", "Adjusted", or "CurrencyNeutral" operating income
- The ~$14B "Street" number exists only in 8-K Earnings Release (Exhibit 99.1)

### 2. yfinance Uses Non-GAAP Metric

yfinance's "Operating Income" for KO is NOT the GAAP `OperatingIncomeLoss` tag. It sources the "Comparable Currency Neutral Operating Income" figure from earnings releases.

### 3. Add-Back Components Found (But Incomplete)

| XBRL Tag | Value |
|----------|-------|
| `AssetImpairmentCharges` | $0.05B |
| `ImpairmentOfIntangibleAssetsExcludingGoodwill` | $0.89B (BODYARMOR) |
| `BusinessCombinationContingentConsideration` | $6.13B (Fairlife - balance sheet) |

Total add-backs found: $7.06B (exceeds gap - selective application unclear)

### 4. Currency Neutral Adjustment Not Available

KO reports "Comparable Currency Neutral" metrics that adjust for FX headwinds. This is a derived figure in MD&A narrative, not a discrete XBRL concept.

---

## Why XBRL Cannot Solve This

1. **Non-GAAP metrics are not required** to be XBRL-tagged
2. **Earnings releases (8-K Exhibit 99.1)** contain these figures as unstructured text
3. **"Items Impacting Comparability"** are company-defined adjustments with no standard taxonomy

---

## Recommendation: RAG System for Earnings Releases

To resolve KO-type gaps, the system needs:

1. **8-K Earnings Release Parser**
   - Extract Exhibit 99.1 from 8-K filings
   - Parse "Comparable Operating Income" from tables/text

2. **Non-GAAP Metric Registry**
   - Map company-specific non-GAAP concepts to standard metrics
   - Example: `ko:ComparableOperatingIncome` → `OperatingIncome`

3. **RAG-based Extraction**
   - Use LLM to extract non-GAAP figures from unstructured earnings releases
   - Validate against yfinance reference values

---

## Files Modified in OperatingIncome Sprint

| File | Change |
|------|--------|
| `reference_validator.py` | Smart Retry logic |
| `industry_logic/__init__.py` | Dimension filtering, R&D variants, EnergyExtractor |
| `industry_mappings.json` | Added SIC 2900-2999 to energy |

## Final Results

| Company | Variance | Status |
|---------|----------|--------|
| NKE | 0.0% | ✓ PASS |
| LLY | 2.6% | ✓ PASS |
| MRK | 0.0% | ✓ PASS |
| CVX | 4.2% | ✓ PASS |
| **KO** | 28.7% | DATA_SOURCE_MISMATCH |
