# 8-K Item Structure Research Summary

**Date:** 2025-11-07
**Status:** Initial Research Complete
**Related Issue:** Beads #tm2

## Research Completed

### Primary Document: [8k-item-structure-evolution.md](./8k-item-structure-evolution.md)

Comprehensive 25KB+ documentation covering:
1. **Three Filing Eras Identified:**
   - Legacy SGML (1995-2004): Integer items
   - Mid-Period XML (2005-2012): Decimal transition
   - Modern XML (2013-present): Standardized decimals

2. **Code Analysis:**
   - Current detection: `decimal_item_pattern` in `htmltools.py`
   - EightK class implementation in `company_reports.py`
   - Test coverage gaps identified

3. **Sample Filings:**
   - 15+ test cases across all eras
   - Real accession numbers for validation
   - Expected vs. actual item lists

4. **Recommendations:**
   - Legacy SGML support implementation
   - Item format normalization
   - Enhanced test coverage

## Key Discoveries

### Detection Issues

**Current Code:**
```python
decimal_item_pattern = r"^(Item\s{1,3}[0-9]{1,2}\.[0-9]{2})\.?"
```

**Problems:**
1. ❌ Returns "Item 2.02" but tests expect "2.02"
2. ❌ No support for integer items (legacy filings)
3. ❌ Requires HTML (fails on SGML filings)
4. ⚠️ Inconsistent with mid-period HTML structure

### Era-Specific Patterns

**Legacy SGML (1995-2004):**
- Format: Plain text, "ITEM 5", "ITEM 7"
- Detection: Regex on raw text
- Common items: 1, 4, 5, 6, 7, 8, 9

**Mid-Period XML (2005-2012):**
- Format: HTML with `<FONT>` tags, `&nbsp;` entities
- Detection: HTML parsing with flexible patterns
- Common items: 2.02, 5.02, 8.01, 9.01

**Modern XML (2013-present):**
- Format: Semantic HTML with `-sec-extract:summary`
- Detection: Current code works well
- Common items: 2.02, 5.02, 7.01, 8.01, 9.01

## Files Created

### Research Documents
- ✅ `8k-item-structure-evolution.md` (25KB comprehensive guide)
- ✅ `README.md` (Quick reference and index)
- ✅ `RESEARCH_SUMMARY.md` (This file)

### Test Sample Collections
15 filings identified across eras:
- 3 Legacy SGML (1999)
- 6 Mid-Period XML (2008, 2011)
- 6 Modern XML (2015, 2020, 2024)

## Implementation Roadmap

### Phase 1: Core Fixes (High Priority)
1. **Normalization**: Strip "Item " prefix for consistency
2. **Legacy Support**: Add integer item detection for SGML
3. **Fallback Logic**: Handle filings without HTML

### Phase 2: Enhanced Detection (Medium Priority)
4. **Mid-Period Support**: Flexible patterns for transitional HTML
5. **Pattern Optimization**: Handle `&nbsp;` and table layouts
6. **Error Handling**: Graceful degradation for malformed HTML

### Phase 3: Testing & Validation (Ongoing)
7. **Test Coverage**: Add era-specific tests
8. **Batch Validation**: Test 1000+ filings per era
9. **Regression Tests**: Ensure modern filings still work

## Code Locations

**Detection Logic:**
- `/edgar/files/htmltools.py` (Lines 101, 141-142)
- `/edgar/company_reports.py` (Lines 621-847)

**Tests:**
- `/tests/test_eightK.py` (Existing modern era tests)
- *Need to add*: Legacy and mid-period tests

**Related:**
- `/scripts/batch/batch_eightk.py` (Batch testing infrastructure)

## Next Actions

1. ✅ **Research Complete** - Comprehensive documentation created
2. ⏭️ **Code Changes** - Implement recommendations from research
3. ⏭️ **Test Addition** - Add era-specific test coverage
4. ⏭️ **Validation** - Batch test across all eras

## Research Artifacts

**Scripts Created (Now Deleted):**
- `research_8k_eras.py` - Initial era analysis
- `examine_8k_html_structure.py` - HTML structure examination
- `debug_2011_filing.py` - Mid-period debugging
- `find_real_8k_samples.py` - Sample collection

**Findings Preserved In:**
- Main research document (8k-item-structure-evolution.md)
- Sample filing list with accession numbers
- Detection pattern analysis
- HTML structure examples

## Cross-References

**Related Research:**
- `8k-financial-exhibit-patterns.md` - Exhibit analysis
- `docs-internal/issues/reproductions/` - Issue reproductions

**Related Issues:**
- Beads #tm2 - Root cause investigation

**Related Tests:**
- `tests/issues/regression/test_issue_477_item_rule_tags.py` - SGML parser fixes

---

**Research Status:** ✅ Complete
**Documentation Quality:** Comprehensive
**Implementation Status:** Pending
**Test Coverage:** Identified, not yet added

**Maintained By:** SEC Filing Research Agent
