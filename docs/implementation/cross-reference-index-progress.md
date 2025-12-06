# Cross Reference Index Implementation Progress

## Status: Phases 1, 2 & 4 Complete ✓

Implementation of Cross Reference Index format support for 10-K filings (edgartools-zwd).

**GitHub #215 SOLVED ✓**

## What Was Accomplished

### 1. Research & Analysis ✓
- Analyzed GE 10-K filing (CIK 40545, filed 2025-02-03) to understand Cross Reference Index format
- Documented table structure and HTML patterns
- Identified technical challenges (page-based navigation)
- Created comprehensive research document: `docs/research/cross-reference-index-format.md`

### 2. Core Implementation ✓
Created `edgar/documents/cross_reference_index.py` with:

**Classes:**
- `PageRange`: Parses and represents page numbers/ranges
  - Handles single pages: `"25"`
  - Handles ranges: `"26-33"`
  - Handles multiple ranges: `"4-7, 9-11, 74-75"`
  - Handles special cases: `"Not applicable"`, `"77-78, (a)"`

- `IndexEntry`: Represents a single Cross Reference Index entry
  - Item number (e.g., "1A")
  - Item title (e.g., "Risk Factors")
  - Page ranges where content is located
  - Part designation (e.g., "Part I", "Part II")

- `CrossReferenceIndex`: Main parser class
  - `has_index()`: Detects Cross Reference Index format
  - `parse()`: Parses the index table
  - `get_item(item_id)`: Gets entry for specific item
  - `get_page_ranges(item_id)`: Gets page ranges for item
  - `find_page_breaks()`: Locates page breaks in HTML
  - `extract_content_by_page_range()`: Extracts content from page range
  - `extract_item_content()`: Extracts content for specific item

### 3. Test Suite ✓
Created `tests/test_cross_reference_index.py` with:
- Unit tests for PageRange parsing (5 tests)
- Unit tests for IndexEntry (2 tests)
- Integration tests with GE 10-K filing (8 tests)
- Saved sample data: `tests/data/cross_reference_index/ge_10k_cross_reference_sample.html`

**Test Results:**
```
8 passed (non-network tests)
All network tests passing with GE 10-K
```

### 4. Validation ✓
Successfully extracted from GE 10-K:
- 23 Cross Reference Index entries
- All Part I, Part II, and Part III items
- Correct page ranges for each item

Example entries:
```
Item 1:   Business                → Pages: 4-7, 9-11, 74-75
Item 1A:  Risk Factors             → Pages: 26-33
Item 1C:  Cybersecurity            → Pages: 25
Item 7:   MD&A                     → Pages: 8-24
Item 8:   Financial Statements     → Pages: 34-72
```

### 5. Multi-Company Validation (Phase 2) ✓

**Format Prevalence Study:**
Tested 31 major companies across multiple sectors:
- **Only 1 company (3.2%)** uses Cross Reference Index format: **GE**
- **30 companies (96.8%)** use standard Item heading format
- Cross Reference Index format is **extremely rare**

**Companies Tested:**
- Industrials: GE ✓, Boeing, Honeywell, 3M, Caterpillar, Deere, Lockheed, Raytheon, Union Pacific
- Banks: Citigroup, Bank of America, JPMorgan, Wells Fargo, Morgan Stanley, Goldman Sachs
- Tech: Apple, Microsoft, Google, Meta, Amazon
- Retail: Walmart, Home Depot, Target, Costco
- Healthcare: J&J, Pfizer, UnitedHealth, CVS
- Energy: Exxon, Chevron, ConocoPhillips

**Historical Validation (GE):**
Tested GE's 5 most recent 10-K filings (2021-2025):
- ✓ 2025-02-03: 23 entries, 75,491 chars extracted for Item 1A
- ✓ 2024-02-02: 23 entries, 95,280 chars extracted for Item 1A
- ✓ 2023-02-10: 22 entries, 104,340 chars extracted for Item 1A
- ✓ 2022-02-11: 22 entries, 84,699 chars extracted for Item 1A
- ✓ 2021-02-12: 21 entries, 70,007 chars extracted for Item 1A

**Key Finding:** GE has used Cross Reference Index format **consistently for 5+ years**. Parser works reliably across all historical filings.

**GitHub #251 Investigation:**
- Citigroup does NOT use Cross Reference Index format
- Uses standard Item headings
- Issue #251 is a **different problem**, not related to Cross Reference Index

### 6. TenK Integration (Phase 4 - Minimal) ✓

Integrated CrossReferenceIndex parser with `TenK` class for automatic, transparent usage.

**Implementation Location:** `edgar/company_reports/ten_k.py`

**Changes:**
1. Added `_cross_reference_index` cached property - lazy-loads parser when needed
2. Modified `__getitem__` method to fall back to Cross Reference Index when standard extraction fails
3. Item mapping dictionary for "Item 1A" → "1A" conversion
4. Backward compatible - standard format companies unaffected

**User Experience:**
```python
# Before (manual usage required):
from edgar.documents import CrossReferenceIndex
index = CrossReferenceIndex(filing.html())
content = index.extract_item_content('1A')

# After (automatic - GitHub #215 SOLVED):
tenk = filing.obj()
content = tenk.risk_factors  # ✓ Works for GE!
```

**Testing:**
- 6 new TenK integration tests added to regression suite
- Total: 16 regression tests, all passing
- Validated with GE (Cross Reference Index) and Apple (standard format)
- Backward compatibility confirmed

**Results:**
| API | GE (Cross Ref) | Apple (Standard) |
|-----|----------------|------------------|
| `tenk.risk_factors` | 75,491 chars ✓ | 68,069 chars ✓ |
| `tenk.business` | 6,094 chars ✓ | Works ✓ |
| `tenk.management_discussion` | 423,356 chars ✓ | Works ✓ |
| `tenk.directors_officers_and_governance` | 106,966 chars ✓ | Works ✓ |
| `tenk['Item 1A']` | 75,491 chars ✓ | Works ✓ |

**GitHub #215 Status:** ✓ **SOLVED** - Users can now use standard `TenK` API with GE filings

## Technical Details

### Table Structure Discovered
```html
<table>
  <tr>
    <td colspan="3"><span>Item 1A.</span></td>
    <td colspan="3"></td>  <!-- Empty spacer -->
    <td colspan="3"><span>Risk Factors</span></td>
    <td colspan="3"></td>  <!-- Empty spacer -->
    <td colspan="3"><span>26-33</span></td>
  </tr>
</table>
```

### Detection Strategy
1. Look for "Form 10-K Cross Reference Index" header
2. Verify presence of Item/page mapping pattern (e.g., Item 1A → page numbers)
3. Use regex to match table row structure

### Parsing Strategy
1. Search in last 1MB of HTML (index table is near end of document)
2. Use regex to extract Item number, title, and page numbers
3. Parse page ranges with robust handling of edge cases
4. Build dictionary mapping item IDs to IndexEntry objects

### Page Number Edge Cases Handled
- Single pages: `"4"`, `"25"`
- Page ranges: `"26-33"`, `"73-74"`
- Multiple ranges: `"4-7, 9-11, 74-75"`
- Not applicable: `"Not applicable"`
- Footnotes: `"77-78, (a)"` → Extracts `77-78`, ignores `(a)`
- HTML entities: `"&#8217;"` → Preserved in title

## Remaining Work

### Phase 2: Multi-Company Validation ✓ COMPLETE
- [x] Research page break patterns across multiple filings
- [x] Test with Citigroup 10-K (GitHub #251) - Not using Cross Reference Index format
- [x] Test with other companies using this format - Only GE found in 31-company sample
- [x] Validate page break detection accuracy - Consistent across 5 years of GE filings
- [x] Test historical filings - Validated GE 2021-2025

### Phase 3: Content Extraction ⏭ SKIPPED
- Phase 3 was skipped - current content extraction works for GE
- No additional robustness needed given format rarity (3.2% - only GE)
- Can revisit if more companies adopt format

### Phase 4: Integration with TenK ✓ COMPLETE (Minimal)
- [x] Integrate with existing 10-K item extraction in `edgar/company_reports.py`
- [x] Update `TenK` class to detect and use Cross Reference Index
- [x] Add graceful fallback when page extraction fails
- [x] Maintain backward compatibility with standard format
- [x] Add comprehensive regression tests

### Phase 5: Testing & Validation ✓ COMPLETE
- [x] Add regression tests for GitHub #215 (GE) - 16 tests all passing
- [x] Test with multiple filing years - Validated GE 2021-2025
- [x] Document known limitations
- N/A: GitHub #251 (Citigroup) - uses standard format, unrelated issue

## Files Created/Modified

1. **Implementation:**
   - `edgar/documents/cross_reference_index.py` (367 lines) - NEW
   - `edgar/documents/__init__.py` - MODIFIED (added exports)
   - `edgar/company_reports/ten_k.py` - MODIFIED (Phase 4 integration)

2. **Documentation:**
   - `docs/research/cross-reference-index-format.md` - NEW
   - `docs/implementation/cross-reference-index-progress.md` (this file) - NEW
   - `docs/implementation/cross-reference-index-recommendations.md` - NEW
   - `docs/implementation/cross-reference-index-summary.md` - NEW

3. **Tests:**
   - `tests/test_cross_reference_index.py` (217 lines) - NEW
   - `tests/issues/regression/test_issue_215_ge_cross_reference_index.py` (245 lines) - NEW
   - `tests/data/cross_reference_index/ge_10k_cross_reference_sample.html` - NEW

4. **Validation Scripts (Phase 2):**
   - `scripts/validate_cross_reference_index.py` - NEW
   - `scripts/find_cross_reference_index_companies.py` - NEW
   - `scripts/test_ge_historical_filings.py` - NEW
   - `scripts/test_tenk_cross_reference_integration.py` (Phase 4) - NEW

## Usage Examples

### Standard User API (Automatic - Recommended)

```python
from edgar import Company

# Get GE 10-K - works automatically for Cross Reference Index format
company = Company('GE')
filing = company.get_filings(form='10-K').latest()
tenk = filing.obj()

# Standard API just works - no special handling needed!
risk_factors = tenk.risk_factors
business = tenk.business
mda = tenk.management_discussion
directors = tenk.directors_officers_and_governance

print(f"Risk Factors: {len(risk_factors):,} characters")
```

### Advanced API (Manual - For Special Cases)

```python
from edgar import Company
from edgar.documents import CrossReferenceIndex

# Get a 10-K filing
company = Company('GE')
filing = company.get_filings(form='10-K').latest()
html = filing.html()

# Detect and parse Cross Reference Index manually
index = CrossReferenceIndex(html)

if index.has_index():
    entries = index.parse()

    # Get Risk Factors entry
    risk_factors = index.get_item('1A')
    print(f"{risk_factors.full_item_name}")
    print(f"Pages: {', '.join(str(p) for p in risk_factors.pages)}")

    # Get page ranges
    pages = index.get_page_ranges('1A')  # [PageRange(26, 33)]

    # Extract content
    content = index.extract_item_content('1A')
```

## Next Steps

**Status:** Feature complete for current needs ✓

**Completed:**
- ✓ Phase 1: Detection and parsing
- ✓ Phase 2: Multi-company validation
- ⏭ Phase 3: Skipped (not needed - works for GE)
- ✓ Phase 4: TenK integration (minimal)
- ✓ Phase 5: Testing and validation

**Possible Future Enhancements:**
1. **Monitor format adoption** - Check quarterly if more companies adopt Cross Reference Index format
2. **If ≥5 companies use format:** Consider Phase 3 (robust content extraction improvements)
3. **GitHub #251 (Citigroup):** Investigate separately - uses standard format, different issue
4. **User documentation:** Add examples to main docs showing Cross Reference Index support

## Related Issues

- **edgartools-zwd** (P3): Support Cross Reference Index format in 10-K filings
- **GitHub #215**: GE 10-K extraction returns None for all items
- **GitHub #251**: Citigroup 10-K extraction returns None for all items

## Conclusion

**Implementation Complete ✓ - GitHub #215 SOLVED**

**Phase 1 (Detection and Parsing)** - Complete:
- Detects Cross Reference Index format ✓
- Parses the index table ✓
- Extracts Item-to-page mappings ✓
- Handles edge cases robustly ✓

**Phase 2 (Multi-Company Validation)** - Complete with key findings:
- **Format is extremely rare:** Only 1/31 companies (3.2%) use this format
- **Only GE identified** in comprehensive sample across multiple sectors
- **GE is consistent:** Used format for 5+ years (2021-2025)
- **Content extraction works:** Successfully extracts 70-105K chars for Risk Factors across all years
- **GitHub #251 (Citigroup) unrelated:** Uses standard format, different extraction issue

**Phase 3 (Content Extraction Enhancement)** - Skipped:
- Current implementation works for GE
- No additional robustness needed given format rarity
- Can revisit if more companies adopt format

**Phase 4 (TenK Integration)** - Complete (Minimal):
- ✓ Auto-detection in `TenK` class
- ✓ Transparent fallback to Cross Reference Index parser
- ✓ Backward compatible with standard format
- ✓ **GitHub #215 SOLVED** - Standard API now works for GE

**Phase 5 (Testing & Validation)** - Complete:
- ✓ 16 comprehensive regression tests
- ✓ Validated across 5 years of GE filings
- ✓ Backward compatibility confirmed with Apple
- ✓ Documentation complete

**Final Status:**
- **Production-ready** for GE (the only known user)
- **GitHub #215 closed** - Users can use standard `tenk.risk_factors` API
- **Transparent to users** - No special code required for Cross Reference Index format
- **Backward compatible** - Standard format companies unaffected
- **Well-tested** - 16 regression tests ensure it stays working
- **Future-proof** - Solid foundation if more companies adopt format
