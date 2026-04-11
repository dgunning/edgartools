# KO (Coca-Cola) OperatingIncome Gap Analysis

## Summary

**XBRL Value**: $9.99B (GAAP OperatingIncomeLoss)  
**yfinance GAAP Value**: $9.99B (`Total Operating Income As Reported`)  
**yfinance Calculated Value**: $14.02B (`Operating Income` - Yahoo-normalized)  
**Gap**: 0.0% ✓ RESOLVED

**Resolution Status**: RESOLVED - Was comparing to wrong yfinance field

---

## Root Cause (2026-01-20 Investigation)

### The Issue Was NOT Non-GAAP vs GAAP

yfinance provides **two** OperatingIncome fields:

| Field | Value | Source |
|-------|-------|--------|
| `Total Operating Income As Reported` | $9.99B | GAAP from 10-K |
| `Operating Income` | $14.02B | Yahoo-calculated/normalized |

We were comparing XBRL to `Operating Income` (the Yahoo-calculated field).
When we switch to `Total Operating Income As Reported`, the variance is **0.0%**.

### Why Yahoo's Calculated Value Differs

Yahoo normalizes by adding back one-time charges:
- Special Income Charges: -$2.30B
- Impairment Of Capital Assets: $0.89B  
- Restructuring And Merger Acquisition: $2.25B

---

## Fix Applied

**File**: `reference_validator.py`

```python
# Changed OperatingIncome mapping to use GAAP field
'OperatingIncome': ('financials', 'Total Operating Income As Reported'),

# Added fallback for companies without GAAP field (NKE, LLY)
YFINANCE_GAAP_FALLBACKS = {
    'OperatingIncome': ('financials', 'Operating Income'),
}
```

---

## Previous Analysis (Incorrect Conclusion)

~~The original analysis concluded that yfinance uses "Comparable Currency Neutral~~
~~Operating Income" from 8-K earnings releases, requiring a RAG system to extract.~~

**Corrected**: yfinance's `Operating Income` is Yahoo's own normalization, NOT KO's
"Comparable" metric. The GAAP value is available in a different field.

---

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
