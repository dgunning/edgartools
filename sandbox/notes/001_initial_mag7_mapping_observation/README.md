# Initial MAG7 Data Mapping & Coverage Observations

**Date:** 2026-01-03
**Author:** Antigravity (Assistant)
**Related Task:** Explore MAG7 Data Coverage
**Tags:** #mag7 #mapping #coverage #data-quality

## Context
We executed a data exploration script (`explore_mag7.py`) to fetch financial metrics for the MAG7 companies from 2009 to 2026.

## Key Findings

### MAG7 Filing Counts
| Ticker | 10-K/10-Q Filings | Notes |
|--------|-------------------|-------|
| MSFT | 134 | Most filings (IPO 1986) |
| AAPL | 129 | Long EDGAR history |
| AMZN | 113 | IPO 1997 |
| NVDA | 109 | IPO 1999 |
| TSLA | 67 | IPO 2010 |
| META | 56 | IPO 2012 |
| GOOG | 43 | Post-2015 restructuring |

### How to Get "Real" Available Periods
Query filings directly, independent of concept mapping:
```python
company = Company('GOOG')
filings = company.get_filings(form=['10-K', '10-Q'])
print(f'Total filings: {len(filings)}')  # Returns 43 for GOOG
```
Compare this to extracted period count to detect mapping gaps.

### Corporate Restructuring Issue - RESOLVED
**GOOG has TWO separate CIKs:**
| CIK | Entity | Period | 10-K/10-Q |
|-----|--------|--------|-----------|
| 1652044 | Alphabet Inc. | 2015-present | 43 |
| 1288776 | GOOGLE INC. | 2004-2016 | 51 |

**Solution:** The script now fetches from both CIKs using the `LEGACY_CIKS` mapping:
```python
LEGACY_CIKS = {
    'GOOG': [
        (1652044, 'Alphabet Inc. (2015-present)'),
        (1288776, 'GOOGLE INC. (2004-2016)')
    ]
}
```
**Result:** GOOG now shows 94 filings and 66 extracted periods (2009-2025).

### Coverage Gap Detection
The script includes automatic detection of potential legacy CIK issues:
```python
def detect_coverage_gap(ticker, filings, extracted_periods):
    if extracted_periods < 60 and filings >= 50:
        return f"⚠️ COVERAGE GAP: {ticker} may have legacy CIKs!"
```
When a gap is detected, check SEC for related entities and add to `LEGACY_CIKS`.


## Bulk Data Support

### Download & Setup
```python
from edgar import download_edgar_data, use_local_storage

download_edgar_data(facts=True, submissions=True, reference=True)
use_local_storage(True)
# Now all API calls read from local files
```

### Test Run (2026-01-04)
We created `explore_mag7_bulk.py` to test bulk data extraction. Results:

**Download Location:** `~/.edgar/`
| Folder | Size |
|--------|------|
| `submissions/` | 7.1 GB |
| `companyfacts/` | ~4 GB |
| **Total** | ~11 GB |

**Download Time:** ~15 minutes (910s)

**Extraction Results (from LOCAL bulk data):**
| Ticker | Facts Found | Periods Extracted |
|--------|-------------|-------------------|
| GOOG | 29,283 (combined) | 66 |
| AMZN | 28,172 | 66 |
| AAPL | 23,807 | 66 |
| MSFT | 29,910 | 65 |
| NVDA | 26,034 | 62 |
| TSLA | 22,842 | 58 |
| META | 16,895 | 54 |

**Output:** 437 records saved to `sandbox/data/mag7_financials_bulk.parquet`

### Key Observations
-   GOOG dual-CIK handling worked correctly (19,170 + 10,113 facts merged)
-   Local storage mode eliminates network latency for repeated queries
-   Script: `explore_mag7_bulk.py` is reusable for future bulk analysis

## Open Questions
-   Why does `former_names` not show the 2015 restructuring?
-   Should we track CIK changes manually for major companies?
