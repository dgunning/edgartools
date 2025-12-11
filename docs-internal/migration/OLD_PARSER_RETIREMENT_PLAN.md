# Old HTML Parser Retirement Plan

## Executive Summary

**Goal**: Retire the legacy HTML parser (`edgar.files.html*`) and reduce testing load while maintaining stability and backward compatibility.

**Current State** (v5.0):
- ✅ All major forms migrated (8-K, 10-K, 10-Q, 20-F) to new parser
- 📦 Old parser still in codebase (~4,200 lines)
- 🧪 ~24 test files still using old parser
- 🔄 Fallback mechanisms still active in production code

**Timeline**: 3-phase approach over 2 releases (v5.0 → v5.1 → v6.0)

---

## Current Old Parser Footprint

### Code Size
```
edgar/files/html.py                 1,759 lines (65KB)
edgar/files/html_documents.py       1,156 lines (43KB)
edgar/files/html_documents_id_parser.py  687 lines (27KB)
edgar/files/htmltools.py              584 lines (21KB)
edgar/files/styles.py                 645 lines (25KB)
edgar/files/tables.py                 625 lines (25KB)
-------------------------------------------
TOTAL:                              ~5,456 lines (~206KB)
```

### Production Usage
- **35 references** to ChunkedDocument/HtmlDocument in edgar/ codebase
- **Fallback mechanisms** in TenK, TenQ, EightK
- **Legacy APIs** exported from `edgar/__init__.py`
- **Supporting utilities** (markdown, attachments, etc.)

### Test Usage
- **24 test files** directly testing old parser
- **~13 HTML-related test modules**
- Mix of unit tests, integration tests, and reproduction tests

---

## Three-Phase Retirement Plan

### **Phase 1: Deprecation Warnings** (v5.0 - Now)

**Goal**: Notify users that old parser is deprecated, encourage migration

**Status**: ✅ Ready to implement

#### Actions

1. **Add Deprecation Warnings**
   ```python
   # edgar/files/html.py
   import warnings

   warnings.warn(
       "edgar.files.html module is deprecated and will be removed in v6.0. "
       "Use edgar.documents.HTMLParser instead. "
       "See migration guide: https://edgartools.readthedocs.io/migration/",
       DeprecationWarning,
       stacklevel=2
   )
   ```

2. **Update Documentation**
   - Add migration guide to docs
   - Mark old parser classes as deprecated in API docs
   - Update examples to use new parser

3. **Keep Fallback Mechanisms**
   - TenK/TenQ/EightK still fall back to old parser if new parser fails
   - No breaking changes for users
   - Log warnings when fallback is used

4. **Test Strategy**
   - Keep all old parser tests (mark with `@pytest.mark.legacy_parser`)
   - Add migration tests showing old → new equivalence
   - Monitor fallback usage in production

**Testing Load**: No reduction yet (need both parsers working)

**User Impact**: Minimal - just warnings in logs

---

### **Phase 2: Remove Fallbacks & Hard Deprecation** (v5.1 - Q1 2026)

**Goal**: Remove fallback mechanisms, hard-deprecate old parser

**Prerequisites**:
- ✅ v5.0 released and stable
- ✅ User feedback collected (are fallbacks being used?)
- ✅ Migration guide published and tested

#### Actions

1. **Remove Fallback Logic**
   ```python
   # edgar/company_reports/ten_k.py - BEFORE
   def __getitem__(self, item):
       # Try new parser first
       if self.sections and item in self.sections:
           return self.sections[item].text()

       # Fallback to old parser
       return self.chunked_document[item]  # REMOVE THIS

   # edgar/company_reports/ten_k.py - AFTER
   def __getitem__(self, item):
       # Only use new parser
       if self.sections and item in self.sections:
           return self.sections[item].text()

       # No fallback - raise helpful error
       raise KeyError(
           f"Item '{item}' not found. Available items: {list(self.sections.keys())}"
       )
   ```

2. **Remove Old Parser Imports from Production Code**
   - TenK, TenQ, EightK: Remove `ChunkedDocument` imports
   - edgar/__init__.py: Stop exporting old `Document` class
   - _filings.py, _markdown.py: Migrate to new parser APIs

3. **Consolidate Tests**
   - Delete duplicate tests (old parser tests with new parser equivalents)
   - Keep ~5 regression tests for old parser edge cases
   - Move old parser tests to `tests/legacy/` directory

4. **Update Package Metadata**
   ```python
   # edgar/files/html.py
   raise DeprecationWarning(
       "edgar.files.html module has been removed as of v5.1. "
       "Use edgar.documents.HTMLParser instead."
   )
   ```

**Testing Load**: 📉 **Reduce by ~50%** - Remove ~12 old parser test files

**User Impact**: 🔴 **Breaking** for anyone still using old parser directly

**Migration Path**:
- Users get clear error messages
- Migration guide shows exact replacements
- New parser handles all use cases from old parser

---

### **Phase 3: Complete Removal** (v6.0 - Q2 2026)

**Goal**: Delete all old parser code from codebase

**Prerequisites**:
- ✅ v5.1 released and stable (3+ months)
- ✅ No major issues reported with new parser
- ✅ Fallback usage metrics show <1% of requests

#### Actions

1. **Delete Old Parser Files**
   ```bash
   rm edgar/files/html.py                    # 1,759 lines
   rm edgar/files/html_documents.py          # 1,156 lines
   rm edgar/files/html_documents_id_parser.py #  687 lines
   rm edgar/files/htmltools.py               #  584 lines
   rm edgar/files/styles.py                  #  645 lines
   # Keep tables.py - still used by new parser
   ```

2. **Delete Old Parser Tests**
   ```bash
   rm -rf tests/legacy/  # All old parser tests
   rm tests/test_htmltools.py
   rm tests/test_html.py
   rm tests/test_html_parser_integration.py
   # Keep reproduction tests as documentation
   ```

3. **Clean Up Dependencies**
   - Remove any old-parser-specific dependencies
   - Update package imports

4. **Update edgar/__init__.py**
   ```python
   # REMOVE
   from edgar.files.html import Document  # OLD

   # KEEP
   from edgar.documents import Document  # NEW (if we want to export)
   ```

**Code Reduction**: 📉 **~5,500 lines** (~200KB)

**Testing Load**: 📉 **~70% reduction** in HTML parsing tests

**User Impact**: None (already deprecated in v5.1)

---

## Test Reduction Strategy

### Current Test Breakdown

```
Old Parser Tests (to remove):
├── tests/test_htmltools.py           ❌ Delete in Phase 2
├── tests/test_html.py                ❌ Delete in Phase 2
├── tests/test_html_parser_integration.py  ❌ Delete in Phase 2
├── tests/test_html_tables.py         ❌ Delete in Phase 2
├── tests/test_table_extraction.py    ❌ Delete in Phase 2
├── tests/test_markdown_page_breaks.py  ❌ Delete in Phase 2
├── tests/test_page_breaks.py         ❌ Delete in Phase 2
├── tests/test_filing_html.py         ❌ Delete in Phase 2
├── tests/test_textsearch.py          ❌ Delete in Phase 2 (if old parser specific)
└── tests/manual/compare_parsers.py   ❌ Delete in Phase 2

New Parser Tests (keep & enhance):
├── tests/test_documents/              ✅ Keep
├── tests/test_company_reports.py      ✅ Keep (new parser tests)
├── tests/issues/regression/           ✅ Keep (validates bug fixes)
└── tests/test_attachments.py          ✅ Keep (migrate to new parser)

Reproduction Tests (archive):
└── tests/issues/reproductions/        📦 Archive (move to docs)
```

### Test Migration Matrix

| Test File | Action | Reason |
|-----------|--------|--------|
| test_htmltools.py | Delete Phase 2 | Old parser internals |
| test_html.py | Delete Phase 2 | Old parser API |
| test_html_parser_integration.py | Delete Phase 2 | Integration tests for old parser |
| test_html_tables.py | Migrate Phase 1 | Table extraction still needed |
| test_company_reports.py | Keep | Already using new parser |
| test_attachments.py | Migrate Phase 1 | Update to use new parser |
| test_eightK.py | Keep | Already migrated |
| Reproduction tests | Archive Phase 3 | Move to docs as examples |

### Testing Load Metrics

| Phase | Test Files | Lines of Test Code | Test Execution Time |
|-------|-----------|-------------------|---------------------|
| **Current** (v4.35) | ~24 old parser tests | ~3,000 lines | ~45s |
| **Phase 1** (v5.0) | ~24 old parser tests | ~3,000 lines | ~45s |
| **Phase 2** (v5.1) | ~12 tests | ~1,500 lines | ~20s |
| **Phase 3** (v6.0) | ~5 regression tests | ~500 lines | ~5s |

**Total Reduction**: 📉 **~90% fewer old parser tests**

---

## Fallback Strategy (Phase 1 & 2)

### Current Fallback Mechanisms

#### TenK Fallback (edgar/company_reports/ten_k.py)
```python
@property
def items(self):
    # Try new parser first
    if self.sections:
        return [section_to_item[name] for name in self.sections.keys()]

    # Fallback to old parser
    return self.chunked_document.get_items()

def __getitem__(self, item):
    # Try new parser
    if self.sections and item in friendly_name_map:
        section = self.sections.get(friendly_name_map[item])
        if section:
            return section.text()

    # Fallback to old ChunkedDocument
    return self.chunked_document[item]
```

#### TenQ Fallback (edgar/company_reports/ten_q.py)
Similar pattern - try new parser, fallback to ChunkedDocument

### Logging Fallback Usage (v5.0)

Add telemetry to understand fallback frequency:

```python
import logging
logger = logging.getLogger(__name__)

def __getitem__(self, item):
    # Try new parser
    if self.sections:
        try:
            return self.sections[item].text()
        except KeyError:
            pass

    # Fallback with logging
    logger.warning(
        f"Falling back to old parser for {self._filing.accession_number}, item '{item}'. "
        f"New parser sections: {list(self.sections.keys())}"
    )
    return self.chunked_document[item]
```

### Metrics to Track

1. **Fallback Rate**: % of requests using fallback
2. **Filing Types**: Which filings trigger fallbacks
3. **Missing Items**: What items are new parser missing
4. **Error Patterns**: Common failure modes

**Target for Phase 2**: <1% fallback usage

---

## Migration Guide for Users

### For Users of Public APIs

#### Before (Old Parser)
```python
from edgar import Company
from edgar.files.html import Document  # OLD

company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

# Old way
doc = Document.parse(filing.html())
sections = doc.sections
```

#### After (New Parser)
```python
from edgar import Company
from edgar.documents import HTMLParser, ParserConfig  # NEW

company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

# New way - or just use filing.obj()
tenk = filing.obj()  # Uses new parser automatically
sections = tenk.sections
```

### For Users of Low-Level APIs

#### Old API → New API Mapping

| Old (edgar.files.html) | New (edgar.documents) |
|------------------------|----------------------|
| `Document.parse(html)` | `HTMLParser(config).parse(html)` |
| `doc.sections` | `document.sections` |
| `ChunkedDocument` | `Document` |
| `HtmlDocument` | `Document` |
| `doc.get_items()` | `document.sections.keys()` |

### No Action Required (Using High-Level APIs)

If you're using:
- `company.latest_tenk`
- `filing.obj()`
- `tenk['Item 1']`

**You're already using the new parser!** No migration needed.

---

## Risk Assessment

### Low Risk ✅

- **Phase 1**: Adding deprecation warnings
  - No breaking changes
  - Users notified in advance
  - Fallbacks still work

### Medium Risk ⚠️

- **Phase 2**: Removing fallbacks
  - Breaking for <1% of edge cases
  - Clear migration path
  - Good error messages

### High Risk 🔴

- **Phase 3**: Complete removal
  - Breaking for anyone on old APIs
  - Mitigated by 6+ months notice
  - Clear semver (v6.0 = major)

---

## Success Criteria

### Phase 1 (v5.0)
- ✅ Deprecation warnings added
- ✅ Migration guide published
- ✅ All major forms use new parser
- ✅ Fallback usage logged and tracked
- ✅ No regressions in functionality

### Phase 2 (v5.1)
- ✅ <1% fallback usage
- ✅ Fallbacks removed from production code
- ✅ ~50% reduction in test files
- ✅ All old parser imports removed from edgar/
- ✅ Clear error messages for missing items

### Phase 3 (v6.0)
- ✅ Old parser code completely removed
- ✅ ~70% reduction in HTML parsing tests
- ✅ ~5,500 fewer lines of code
- ✅ Cleaner codebase for AI/human maintainability
- ✅ No old parser imports anywhere

---

## Rollout Timeline

```
v5.0 (Dec 2025)
│
├── Phase 1: Deprecation Warnings
│   ├── Add warnings to old parser
│   ├── Publish migration guide
│   ├── Log fallback usage
│   └── Monitor for 3 months
│
v5.1 (Mar 2026)
│
├── Phase 2: Remove Fallbacks
│   ├── Remove fallback logic
│   ├── Delete ~12 test files
│   ├── Remove old parser imports from production
│   └── Monitor for 3 months
│
v6.0 (Jun 2026)
│
└── Phase 3: Complete Removal
    ├── Delete old parser files (~5,500 lines)
    ├── Delete remaining old parser tests
    └── Clean, modern codebase
```

---

## Action Items

### For v5.0 Release (Now)

- [ ] Add deprecation warnings to edgar/files/html*.py
- [ ] Create migration guide in docs/
- [ ] Add fallback logging to TenK/TenQ
- [ ] Mark old parser tests with `@pytest.mark.legacy_parser`
- [ ] Update CHANGELOG with deprecation notice
- [ ] Create dashboard to track fallback metrics

### For v5.1 Release (Q1 2026)

- [ ] Review fallback metrics from v5.0
- [ ] Remove fallback logic from company reports
- [ ] Delete redundant old parser tests
- [ ] Move remaining old parser tests to tests/legacy/
- [ ] Update package to raise errors on old parser imports
- [ ] Announce v6.0 removal in release notes

### For v6.0 Release (Q2 2026)

- [ ] Delete edgar/files/html*.py files
- [ ] Delete tests/legacy/ directory
- [ ] Update edgar/__init__.py exports
- [ ] Update documentation to remove all old parser references
- [ ] Celebrate cleaner codebase! 🎉

---

## Questions & Answers

### Q: What if the new parser fails for some filing?

**A**: In v5.0 and v5.1, fallback mechanisms will catch these cases. By v6.0, we'll have identified and fixed all edge cases.

### Q: Can users still use the old parser if they want?

**A**:
- v5.0: Yes, but with deprecation warnings
- v5.1: Yes, but imports will raise errors
- v6.0: No, code completely removed

### Q: What about backward compatibility?

**A**: High-level APIs (filing.obj(), tenk['Item 1']) remain unchanged. Only low-level parser APIs are affected.

### Q: How do we handle edge cases the new parser doesn't support?

**A**: Fallback usage logging in v5.0 will identify these. We fix them before removing fallbacks in v5.1.

---

## Related Issues

- edgartools-xso: Epic: Retire ChunkedDocument (CLOSED)
- edgartools-436: Epic: Cutover from edgar.files.html to edgar.documents parser
- edgartools-3dp: Task: Migrate all old parser usages to edgar.documents
- edgartools-f76: Task: Review and close old parser issues after v5.0 cutover

---

**Document Status**: Draft
**Last Updated**: 2025-12-06
**Next Review**: After v5.0 release (check fallback metrics)
