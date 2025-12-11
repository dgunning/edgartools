# Phase 2: Company Reports Migration Plan

**Date**: 2025-11-25
**Status**: In Progress
**Related**: docs/OLD_PARSER_AUDIT.md

---

## Overview

Migrate `CompanyReport` base class and all form classes from `ChunkedDocument` (old parser) to `Document` (new parser).

---

## Current API Contract

### CompanyReport Base Class (`edgar/company_reports/_base.py`)

```python
@cached_property
def chunked_document(self):
    return ChunkedDocument(self._filing.html())

@property
def doc(self):
    return self.chunked_document

@property
def items(self) -> List[str]:
    return self.chunked_document.list_items()

def __getitem__(self, item_or_part: str):
    item_text = self.chunked_document[item_or_part]
    return item_text  # Returns str (HTML text)
```

### Old Parser API (`ChunkedDocument`)

- `__init__(html, chunk_fn, prefix_src)` - Initialize with HTML
- `list_items()` - Returns `List[str]` of item names
- `__getitem__(item_or_part)` - Returns `str` (HTML text) or `None`
- Supports both integer index and string item names

### New Parser API (`Document`)

- `HTMLParser().parse(html)` - Returns `Document` object
- `document.sections` - Returns `Sections` dict-like object
- `sections.keys()` - Returns item names
- `sections[key]` - Returns `Section` object (not text!)
- `section.text()` - Extract text from section

---

## Migration Strategy

### Approach: Hybrid with Deprecation

1. **Add new `document` property** - Primary API going forward
2. **Keep `chunked_document` for backwards compat** - Add deprecation warning
3. **Update `items` property** - Use new parser internally
4. **Update `__getitem__`** - Use new parser, return text for compatibility

### Key Differences to Handle

| Old Parser | New Parser | Migration Action |
|------------|------------|------------------|
| `ChunkedDocument(html)` | `HTMLParser().parse(html)` | Create parser instance |
| `list_items()` | `list(sections.keys())` | Convert sections to list |
| `[item]` returns `str` | `[item]` returns `Section` | Call `.text()` on section |
| No part support in 10-Q | Part-aware sections | Use `sections.get_item(item, part)` |

---

## Implementation Plan

### Step 1: Update CompanyReport Base Class

**File**: `edgar/company_reports/_base.py`

```python
from functools import cached_property
from typing import List
import warnings

from edgar.documents import HTMLParser, Document
from edgar.files.htmltools import ChunkedDocument  # Keep for backwards compat
from edgar.financials import Financials
from edgar.richtools import repr_rich

class CompanyReport:

    def __init__(self, filing):
        self._filing = filing
        self._parser = None  # Lazy init

    # NEW: Primary API - new parser
    @cached_property
    def document(self) -> Document:
        """Get the filing document using new parser (primary API)."""
        if self._parser is None:
            from edgar.documents.config import ParserConfig
            # Create parser with form type for better section detection
            config = ParserConfig(form=self._filing.form)
            self._parser = HTMLParser(config)
        return self._parser.parse(self._filing.html())

    # BACKWARDS COMPAT: Keep old API but deprecate
    @cached_property
    def chunked_document(self):
        """
        Get chunked document using old parser.

        .. deprecated:: 5.0
            Use :attr:`document` instead. This will be removed in v6.0.
        """
        warnings.warn(
            "chunked_document is deprecated and will be removed in v6.0. "
            "Use document property instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return ChunkedDocument(self._filing.html())

    @property
    def doc(self):
        """Get the filing document (returns new Document object)."""
        return self.document

    @property
    def items(self) -> List[str]:
        """Get list of items/sections in the filing."""
        return list(self.document.sections.keys())

    def __getitem__(self, item_or_part: str):
        """
        Get item or part text from the filing.

        Args:
            item_or_part: Item identifier (e.g., "Item 1", "1", "Part I")

        Returns:
            str: Item text or None if not found

        Examples:
            >>> report["Item 1"]
            >>> report["1A"]
            >>> report["Part I"]  # For 10-Q
        """
        # Try to get section using new parser
        section = self.document.sections.get(item_or_part)
        if section:
            return section.text()

        # Try flexible item lookup (handles "Item 1", "1", etc.)
        section = self.document.sections.get_item(item_or_part)
        if section:
            return section.text()

        return None
```

**Changes Summary:**
- ✅ New `document` property (primary API)
- ✅ `chunked_document` kept but deprecated
- ✅ `doc` returns new `Document` object
- ✅ `items` uses `document.sections.keys()`
- ✅ `__getitem__` uses `document.sections[].text()`

### Step 2: Verify Form Classes

All form classes inherit from `CompanyReport`, so they automatically get the new API:

- ✅ `TenK` - No changes needed (inherits from `CompanyReport`)
- ✅ `TenQ` - No changes needed (inherits from `CompanyReport`)
- ✅ `EightK` - May have custom parsing - needs review
- ✅ `SixK` - May have custom parsing - needs review
- ✅ `TwentyF` - No changes needed (inherits from `CompanyReport`)
- ⏳ `PressRelease` - Uses `HtmlDocument` directly - needs review

### Step 3: Update Form-Specific Logic

#### EightK/SixK Custom Parsing

**File**: `edgar/company_reports/current_report.py`

Currently uses:
- `ChunkedDocument` via base class
- `chunks2df`, `adjust_for_empty_items`, `detect_decimal_items` from `htmltools`

**Action**: Review and migrate custom parsing logic if needed.

---

## Testing Strategy

### Unit Tests to Update

1. **Base Class Tests** (`tests/test_company_reports.py`)
   - Test new `document` property
   - Test `items` property returns correct list
   - Test `__getitem__` returns text
   - Test backwards compat with `chunked_document` (with warning)

2. **Form-Specific Tests**
   - `test_tenk_item_and_parts` - Item extraction
   - `test_eightK.py` - 8-K specific parsing
   - Regression tests for issues #447, #454, #311, #462

### Integration Tests

1. **Item Extraction Accuracy**
   - Compare old vs new parser results
   - Ensure no regressions in item detection

2. **Part-Aware Sections (10-Q)**
   - Test Part I vs Part II item extraction
   - Test `get_item(item, part)` functionality

3. **Performance**
   - Compare parsing speed old vs new
   - Check memory usage

---

## Backwards Compatibility

### Breaking Changes

**None** - This migration maintains full backwards compatibility:

- ✅ `report["Item 1"]` still works
- ✅ `report.items` still returns list
- ✅ `report.doc` still works (returns new Document instead)
- ✅ `report.chunked_document` still works (with deprecation warning)

### Deprecation Timeline

1. **v5.0** - Add deprecation warning for `chunked_document`
2. **v5.x** - Migration period (6+ months)
3. **v6.0** - Remove `chunked_document` and old parser

---

## Risks and Mitigations

### Risk 1: Different Text Output

**Risk**: New parser may extract text differently than old parser.

**Mitigation**:
- Run side-by-side comparison tests
- Check regression tests pass
- Allow for minor whitespace differences

### Risk 2: Section Detection Differences

**Risk**: New parser may detect different sections or miss some.

**Mitigation**:
- Hybrid section detector uses multiple strategies (TOC, heading, pattern)
- Confidence scores help identify low-confidence detections
- Fallback to pattern-based for edge cases

### Risk 3: Performance Regression

**Risk**: New parser may be slower than old parser.

**Mitigation**:
- New parser has performance optimizations (caching, streaming)
- Benchmark tests to verify
- ParserConfig.for_performance() option available

---

## Success Criteria

- ✅ All tests pass with new parser
- ✅ No regressions in item extraction accuracy
- ✅ Performance equal or better than old parser
- ✅ Backwards compatibility maintained
- ✅ Deprecation warnings work correctly
- ✅ Documentation updated

---

## Implementation Checklist

### Phase 2.1: Base Class Migration

- [ ] Update `CompanyReport._base.py`
- [ ] Add deprecation warning for `chunked_document`
- [ ] Update docstrings
- [ ] Run unit tests
- [ ] Fix any failures

### Phase 2.2: Form Class Review

- [ ] Review `TenK` - verify inheritance works
- [ ] Review `TenQ` - verify inheritance works
- [ ] Review `EightK/SixK` - migrate custom parsing
- [ ] Review `TwentyF` - verify inheritance works
- [ ] Review `PressRelease` - migrate HtmlDocument usage

### Phase 2.3: Testing

- [ ] Run all company report tests
- [ ] Run regression tests (#447, #454, #311, #462, #107, #251, #365)
- [ ] Compare old vs new parser output
- [ ] Performance benchmarks

### Phase 2.4: Documentation

- [ ] Update API documentation
- [ ] Add migration guide for users
- [ ] Update examples
- [ ] Update CHANGELOG

---

## Next Steps

1. ✅ Create migration plan (this document)
2. ⏳ Implement `CompanyReport._base.py` changes
3. ⏳ Run tests and fix issues
4. ⏳ Review form-specific classes
5. ⏳ Update documentation
6. ⏳ Create PR

---

**Migration Plan Created**: 2025-11-25
**Target Completion**: TBD
**Related Tasks**: edgartools-8fk (Phase 2 migration)
