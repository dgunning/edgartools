# Old Parser Audit Report
**Task**: edgartools-8fk
**Date**: 2025-11-25
**Purpose**: Document all usages of legacy `edgar.files.html` parser for migration planning

---

## Executive Summary

The legacy parser (`edgar/files/html.py` and `edgar/files/htmltools.py`) is deeply embedded in the codebase with **critical dependencies** in core functionality:

- **5 company report classes** depend on `ChunkedDocument` via base class
- **17 source files** import from old parser modules
- **19 test files** depend on old parser classes
- **Core filing API** (`Filing.document()`) uses old parser

**Migration Complexity**: HIGH - Base class dependency affects all company reports

---

## 1. Core Module Dependencies

### 1.1 edgar.files.html (Document class)

**Purpose**: Main HTML document parsing and node tree structure

**Direct Imports** (13 files):
```
edgar/__init__.py:29                          # Public API export
edgar/_filings.py:53                          # Filing.document() method
edgar/xbrl/rendering.py:18                    # XBRL table rendering
edgar/files/tables.py:5                       # Table extraction (BaseNode)
edgar/sgml/table_to_dataframe.py:13          # SGML table conversion (Document, TableNode)
edgar/sgml/filing_summary.py:17              # Filing summary parsing
edgar/files/markdown.py:4                     # Markdown conversion (BaseNode, Document)
edgar/files/docs/filing_document.py:14       # Documentation example
edgar/company_reports/current_report.py:16   # 8-K/6-K reports
```

**Key Classes Used**:
- `Document` - Main document class with node tree
- `BaseNode` - Base class for document nodes
- `TableNode` - Table representation
- `HeadingNode` - Heading elements

### 1.2 edgar.files.htmltools (ChunkedDocument class)

**Purpose**: Section-based document parsing for SEC filings (Items, Parts)

**Direct Imports** (6 files):
```
edgar/company_reports/_base.py:9              # CompanyReport base class ⚠️ CRITICAL
edgar/company_reports/ten_k.py:13            # 10-K reports
edgar/company_reports/ten_q.py:15            # 10-Q reports
edgar/company_reports/current_report.py:17   # 8-K/6-K reports
edgar/files/html_documents_id_parser.py:14   # ID-based parsing
edgar/_filings.py:55                          # html_sections utility
```

**Key Classes/Functions Used**:
- `ChunkedDocument` - Section-based extraction (Items/Parts)
- `chunks2df` - Convert chunks to DataFrame
- `adjust_for_empty_items` - Handle empty item sections
- `detect_decimal_items` - Detect decimal item numbering (8-K)
- `html_sections` - Extract sections from HTML

---

## 2. Company Report Classes (CRITICAL DEPENDENCY)

### 2.1 Base Class Dependency

**File**: `edgar/company_reports/_base.py`

The `CompanyReport` base class uses `ChunkedDocument`:

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
    return item_text
```

**Impact**: ALL company report classes inherit this dependency.

### 2.2 Form-Specific Parsers Using Old Parser

| Form Class | File | Old Parser Usage | Migration Status |
|------------|------|------------------|------------------|
| `TenK` | `company_reports/ten_k.py` | Inherits from `CompanyReport` | ❌ Not migrated |
| `TenQ` | `company_reports/ten_q.py` | Inherits from `CompanyReport` | ❌ Not migrated |
| `EightK` | `company_reports/current_report.py` | Inherits from `CompanyReport` + custom parsing | ❌ Not migrated |
| `SixK` | `company_reports/current_report.py` | Inherits from `CompanyReport` + custom parsing | ❌ Not migrated |
| `TwentyF` | `company_reports/twenty_f.py` | Inherits from `CompanyReport` | ❌ Not migrated |
| `PressRelease` | `company_reports/press_release.py` | Uses `HtmlDocument` directly | ❌ Not migrated |

**Total**: 6 form classes

### 2.3 Additional Parser Dependencies

**current_report.py** (8-K/6-K) has BOTH parsers:
- `ChunkedDocument` (via base class)
- New `HTMLParser` (already imported but not fully used)
- Custom functions: `chunks2df`, `adjust_for_empty_items`, `detect_decimal_items`

This file is **partially migrated** - it imports the new parser but still uses the old one.

---

## 3. Filing API Integration

### 3.1 Core Filing Class

**File**: `edgar/_filings.py`

```python
from edgar.files.html import Document
from edgar.files.htmltools import html_sections

class Filing:
    def document(self) -> Document:
        """Get the filing document"""
        return Document.from_html(self.html())

    def sections(self):
        """Get sections using html_sections()"""
        return html_sections(self.html())
```

**Impact**: The public `Filing.document()` API returns old `Document` class.

---

## 4. Supporting Functionality

### 4.1 XBRL Rendering

**File**: `edgar/xbrl/rendering.py`

Uses old `Document` class for table rendering in XBRL statements.

### 4.2 SGML Processing

**Files**:
- `edgar/sgml/table_to_dataframe.py` - Uses `Document`, `TableNode`
- `edgar/sgml/filing_summary.py` - Uses `Document`

### 4.3 Markdown Conversion

**File**: `edgar/files/markdown.py`

Uses `BaseNode`, `Document` for converting to markdown.

### 4.4 Table Extraction

**File**: `edgar/files/tables.py`

Uses `BaseNode` for table extraction logic.

### 4.5 Utility Parsers

**File**: `edgar/files/html_documents_id_parser.py`

Uses `ChunkedDocument` for ID-based section extraction.

---

## 5. Test Files Using Old Parser

**Total**: 19 test files

### 5.1 Core Tests
```
tests/test_html.py                           # Document class tests
tests/test_htmltools.py                      # ChunkedDocument tests
tests/test_documents.py                      # General document tests
```

### 5.2 Company Report Tests
```
tests/test_company_reports.py                # All company report forms
tests/test_eightK.py                         # 8-K specific tests
```

### 5.3 Feature Tests
```
tests/test_html_parser_integration.py        # Parser integration
tests/test_table_extraction.py               # Table extraction
tests/test_html_tables.py                    # HTML table parsing
tests/test_tables.py                         # Table utilities
tests/test_markdown_page_breaks.py           # Markdown conversion
tests/test_page_breaks.py                    # Page break handling
tests/test_attachments.py                    # Filing attachments
tests/test_filing_html.py                    # Filing HTML methods
tests/test_table_financial_headers_detection.py  # Financial table headers
```

### 5.4 Issue Reproduction Tests
```
tests/issues/regression/test_issue_454_get_item_with_part.py
tests/issues/reproductions/filing-parsing/issue_447_item_part_conflict_reproduction.py
tests/issues/reproductions/filing-parsing/issue_365_split_heading_reproduction.py
tests/issues/reproductions/filing-parsing/issue_107_henryschein_extraction_reproduction.py
```

### 5.5 Performance Tests
```
tests/perf/perf_get_html_text.py             # Performance benchmarks
```

---

## 6. Documentation Files (Reference Only)

These are docs/examples, not production code:
```
edgar/files/docs/document_review.md
edgar/files/docs/filing_document.py
edgar/files/docs/chunked_document_extraction.md
edgar/documents/implementation-plan.md
edgar/documents/parsing-analysis.md
edgar/documents/migration_example.py
```

---

## 7. Migration Helper Code

**File**: `edgar/documents/migration.py`

Contains migration helpers and examples (not production code):
- Example old parser imports (lines 178, 181, 246, 113)
- Migration documentation
- Code transformation examples

---

## 8. Migration Complexity Analysis

### 8.1 Critical Path

1. **CompanyReport Base Class** (`_base.py`)
   - Must be migrated first
   - Affects ALL company report forms
   - Provides `chunked_document`, `doc`, `items`, `__getitem__`

2. **Individual Form Classes**
   - TenK - Inherits from CompanyReport
   - TenQ - Inherits from CompanyReport
   - EightK/SixK - Inherits + custom parsing
   - TwentyF - Inherits from CompanyReport
   - PressRelease - Uses HtmlDocument

3. **Filing Class** (`_filings.py`)
   - `document()` method
   - `sections()` method

### 8.2 Dependency Order

**Must migrate in this order**:

1. ✅ Create new parser equivalent functionality (DONE - `edgar.documents` exists)
2. ⏳ Migrate `CompanyReport` base class to use new parser
3. ⏳ Migrate individual form classes (TenK, TenQ, etc.)
4. ⏳ Update `Filing.document()` to return new Document type
5. ⏳ Update supporting utilities (XBRL, SGML, markdown, tables)
6. ⏳ Update all test files
7. ⏳ Deprecate old parser with warnings
8. ⏳ Remove old parser (major version bump)

### 8.3 Breaking Change Impact

**Public API Changes**:
- `Filing.document()` return type changes
- `CompanyReport.doc` return type changes
- `CompanyReport.__getitem__()` behavior changes
- Item/section extraction API changes

**Mitigation**: Need compatibility layer or major version bump.

---

## 9. Known Issues Related to Old Parser

From edgartools-3b1 investigation:

**Fixed in Legacy Parser** (need new parser verification):
- #447 - PART I/II item conflicts
- #454 - `get_item_with_part` case sensitivity
- #311 - Legal Proceedings extraction
- #462 - 8-K item parsing
- #248 - Table truncation

**Unfixed** (will be resolved by migration):
- #107 - TenK extraction failures (ChunkedDocument bug)
- #251 - Citigroup 10-K returns None
- #365 - Split heading bug in `styles.py`

---

## 10. Recommended Migration Strategy

### Phase 1: Base Infrastructure (CURRENT)
- ✅ New parser exists (`edgar.documents`)
- ✅ Migration helpers exist
- ⏳ Feature parity verification

### Phase 2: Company Reports Migration
1. Create new base class or update `CompanyReport._base.py`
2. Migrate TenQ first (already has new parser import in `current_report.py`)
3. Migrate TenK (edgartools-cv8)
4. Migrate EightK/SixK
5. Migrate TwentyF
6. Migrate PressRelease

### Phase 3: Core API Migration
1. Update `Filing.document()` with compatibility layer
2. Update supporting utilities
3. Add deprecation warnings

### Phase 4: Test Migration
1. Update all test files
2. Add new parser tests
3. Keep regression tests

### Phase 5: Deprecation
1. Major version bump (v5.0?)
2. Remove old parser
3. Update documentation

---

## 11. Summary Statistics

| Category | Count | Status |
|----------|-------|--------|
| Source files importing old parser | 17 | ❌ Need migration |
| Company report forms affected | 6 | ❌ Need migration |
| Test files using old parser | 19 | ❌ Need update |
| GitHub issues blocked by migration | 3 | ⏳ Will be fixed |
| GitHub issues fixed in old parser | 5 | ⏳ Need verification |

**Estimated Effort**:
- Base class migration: 8-12 hours
- Form class migrations: 6-8 hours each × 6 = 36-48 hours
- Supporting utilities: 8-12 hours
- Test updates: 16-24 hours
- **Total**: ~70-100 hours

**Risk Level**: HIGH - Core functionality, public API changes

---

## 12. Next Steps

1. ✅ Complete this audit (DONE)
2. ⏳ Verify new parser feature parity
3. ⏳ Create detailed migration plan for CompanyReport base class
4. ⏳ Implement base class migration with compatibility layer
5. ⏳ Migrate forms one-by-one (TenQ → TenK → EightK → TwentyF → PressRelease)
6. ⏳ Update tests incrementally
7. ⏳ Add deprecation warnings
8. ⏳ Plan v5.0 release with old parser removal

**Blocking Issues**:
- edgartools-cv8: Migrate TenK to new HTMLParser
- edgartools-3dp: Migrate all old parser usages (this task)
- edgartools-xso: Retire ChunkedDocument epic

---

**Report Generated**: 2025-11-25
**Next Review**: After TenK migration (edgartools-cv8)
