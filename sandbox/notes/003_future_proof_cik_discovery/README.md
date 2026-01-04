# Future-Proof CIK Discovery for Corporate Restructurings

**Date:** 2026-01-03
**Author:** Antigravity (Assistant)
**Related Task:** Future-Proof CIK Discovery
**Tags:** #cik #restructuring #discovery #data-completeness

## Problem Statement
When a company undergoes corporate restructuring (e.g., GOOG creating Alphabet Inc. as parent), historical data may exist under a **different CIK**. The current solution requires manual `LEGACY_CIKS` mapping.

**How was the GOOG issue discovered?**
-   Manual investigation: I searched SEC for "Google Inc" and found CIK 1288776
-   This is NOT automated - it required prior knowledge of the restructuring

## Limitations of Current Approach

| Data Source | Active Companies | Inactive/Historical |
|-------------|------------------|---------------------|
| `get_company_tickers()` | ✅ 10,196 companies | ❌ Not included |
| `Company(CIK)` direct access | ✅ Works | ✅ Works (if you know CIK) |
| `former_names` API | ✅ Tracks renames | ❌ Doesn't track restructurings |

## Proposed Future-Proof Solutions

### Option 1: Maintain LEGACY_CIKS Registry (Current)
```python
LEGACY_CIKS = {
    'GOOG': [(1652044, 'Alphabet Inc.'), (1288776, 'GOOGLE INC.')],
    # Add more as discovered...
}
```
**Pros**: Simple, explicit  
**Cons**: Requires manual maintenance

### Option 2: SEC's Full EDGAR Company Search
The SEC provides a full company search at `https://www.sec.gov/cgi-bin/browse-edgar` that includes inactive entities.
**Pros**: Comprehensive  
**Cons**: Requires web scraping or API integration

### Option 3: Coverage Gap Detection ✅ IMPLEMENTED
Automatically detect when extracted periods << expected:
```python
def detect_coverage_gap(ticker, filings, extracted_periods):
    if extracted_periods < 60 and filings >= 50:
        return f"⚠️ COVERAGE GAP: {ticker} may have legacy CIKs!"
```
**Pros**: Proactive detection  
**Cons**: Doesn't tell you WHICH legacy CIK (requires manual SEC search)

### Option 4: SEC Relationship Data (Ideal but Not Available)
Ideally, SEC would provide parent/subsidiary/predecessor relationship data.
**Status**: Not currently available in EDGAR API

## Recommended Approach
1.  **Short-term**: Maintain `LEGACY_CIKS` for known restructurings (MAG7, S&P 500)
2.  **Medium-term**: Implement coverage gap detection to flag potential issues
3.  **Long-term**: Build web scraper for SEC full company search

## Known Restructurings to Track
| Current | CIKs | Notes |
|---------|------|-------|
| GOOG/GOOGL | 1652044, 1288776 | 2015 Alphabet creation |
| META | 1326801 | Facebook → Meta (same CIK, rename only) |
