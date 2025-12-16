# EdgarTools Type Quality Check Report

**Generated:** 2025-12-15
**Tool:** uvx ty check edgar
**Total Diagnostics:** 1,346 (down from 1,360 after suppressing PyArrow false positives)

## Configuration Added

Added `[tool.ty]` section to `pyproject.toml`:
- Suppressed `unresolved-attribute` errors in `edgar/_filings.py` (PyArrow C extension false positives)
- Reduced diagnostics from 1,360 to 1,346 (14 PyArrow errors suppressed)

## Issue Categories (Ranked by Frequency)

### 1. invalid-argument-type (549 issues - 40.8%)
**Description:** Function arguments don't match expected types
**Common Patterns:**
- Union types with refinement types (`~AlwaysFalsy`, `~AlwaysTruthy`)
- Exchange enum vs string mismatches
- Range types passed where list[int] expected
- Type narrowing issues after conditional checks

**Example:**
```python
# edgar/_filings.py:733
filing_index = filter_by_exchange(filing_index, exchange)
# Expected: str | list[str]
# Found: (str & ~AlwaysFalsy) | (list[str] & ~AlwaysFalsy) | Exchange | (list[Exchange] & ~AlwaysFalsy)
```

**Top Affected Files:**
- edgar/funds/reports.py (90 issues)
- edgar/ownership/ownershipforms.py (45 issues)
- edgar/files/html.py (34 issues)

### 2. possibly-missing-attribute (216 warnings - 16.1%)
**Description:** Accessing attributes on objects that could be None
**Common Patterns:**
- BeautifulSoup elements: `el.find()` returns `PageElement | None`
- DateTime objects that could be None
- Attachment objects that could be None
- Conditional attribute access without None checks

**Example:**
```python
# edgar/_filings.py:194
if not is_range and start_date.date() == today:
# start_date could be None
```

**Top Affected Files:**
- edgar/xmltools.py (20 issues)
- edgar/funds/reports.py (19 issues)
- edgar/files/html.py (15 issues)

### 3. unresolved-attribute (201 errors - 14.9%)
**Description:** Attributes don't exist on the object type
**Common Patterns:**
- BeautifulSoup `PageElement` vs `Tag` confusion
- `PageElement.find_all()` not recognized (should be `Tag`)
- Custom object attributes not recognized
- XML parsing element type issues

**Example:**
```python
# edgar/_party.py:141
for el in edgar_previous_names_el.find_all("value")
# PageElement & ~AlwaysFalsy has no attribute find_all
```

**Top Affected Files:**
- edgar/xmltools.py (55 issues)
- edgar/ownership/ownershipforms.py (22 issues)
- edgar/files/docs/filing_document.py (16 issues)

### 4. invalid-parameter-default (119 errors - 8.8%)
**Description:** Default parameter values don't match type annotations
**Common Patterns:**
- `param: str = None` (should be `Optional[str] = None`)
- `param: bool = None` (should be `Optional[bool] = None`)
- Missing Optional wrapper in type hints

**Example:**
```python
# edgar/_filings.py:661
def filter(self, *, amendments: bool = None, ...)
# Should be: amendments: Optional[bool] = None
```

**Top Affected Files:**
- edgar/files/html.py (10 issues)
- edgar/_filings.py (8 issues)
- edgar/xmltools.py (7 issues)

### 5. invalid-return-type (78 errors - 5.8%)
**Description:** Function return values don't match declared return types
**Common Patterns:**
- Functions can return None but type doesn't include Optional
- Return union types with refinement (`str | datetime`)
- Missing None in return type annotation

**Example:**
```python
# edgar/_filings.py:629
def start_date(self) -> Optional[str]:
    return str(self.date_range[0]) if self.date_range[0] else self.date_range[0]
# Returns: str | None but also datetime possible
```

**Top Affected Files:**
- edgar/xmltools.py (8 issues)
- edgar/ownership/ownershipforms.py (7 issues)
- edgar/funds/reports.py (6 issues)

### 6. invalid-assignment (54 errors - 4.0%)
**Description:** Assigning incompatible types to variables

### 7. unresolved-import (24 errors - 1.8%)
**Description:** Import statements that can't be resolved

### 8. not-iterable (22 errors - 1.6%)
**Description:** Attempting to iterate over non-iterable objects

### 9. unsupported-operator (20 errors - 1.5%)
**Description:** Using operators on incompatible types

### 10. non-subscriptable (15 errors - 1.1%)
**Description:** Using [] on non-subscriptable types

### Other Categories (44 issues - 3.3%)
- no-matching-overload (12)
- unknown-argument (10)
- invalid-method-override (8)
- invalid-type-form (7)
- call-non-callable (7)
- unresolved-reference (1)
- too-many-positional-arguments (1)
- invalid-context-manager (1)
- deprecated (1)

## Top 20 Files by Issue Count

| File | Issues | Primary Issue Types |
|------|--------|-------------------|
| edgar/funds/reports.py | 172 | invalid-argument-type (90), possibly-missing-attribute (19) |
| edgar/ownership/ownershipforms.py | 113 | invalid-argument-type (45), unresolved-attribute (22) |
| edgar/xmltools.py | 96 | unresolved-attribute (55), possibly-missing-attribute (20) |
| edgar/files/html.py | 85 | invalid-argument-type (34), possibly-missing-attribute (15) |
| edgar/form144.py | 79 | invalid-argument-type (30), invalid-parameter-default (6) |
| edgar/offerings/formd.py | 67 | invalid-argument-type (25), unresolved-attribute (14) |
| edgar/sgml/filing_summary.py | 45 | invalid-argument-type (15), unresolved-attribute (10) |
| edgar/files/docs/filing_document.py | 45 | unresolved-attribute (16), invalid-argument-type (12) |
| edgar/xbrl/analysis/ratios.py | 40 | invalid-argument-type (20), possibly-missing-attribute (8) |
| edgar/sgml/sgml_header.py | 39 | invalid-argument-type (18), unresolved-attribute (8) |
| edgar/files/html_documents.py | 39 | invalid-argument-type (15), possibly-missing-attribute (10) |
| edgar/muniadvisors.py | 37 | invalid-argument-type (20), unresolved-attribute (8) |
| edgar/xbrl/examples.py | 36 | invalid-argument-type (18), possibly-missing-attribute (6) |
| edgar/_party.py | 36 | unresolved-attribute (15), possibly-missing-attribute (10) |
| edgar/files/styles.py | 28 | invalid-argument-type (12), unresolved-attribute (8) |
| edgar/core.py | 28 | invalid-argument-type (15), possibly-missing-attribute (5) |
| edgar/thirteenf/parsers/primary_xml.py | 25 | invalid-argument-type (10), unresolved-attribute (8) |
| edgar/entity/entity_facts.py | 23 | invalid-argument-type (12), possibly-missing-attribute (6) |
| edgar/entity/data.py | 22 | invalid-argument-type (10), possibly-missing-attribute (5) |
| edgar/funds/data.py | 21 | invalid-argument-type (8), unresolved-attribute (6) |

## Recommended Prioritization

### High Priority (Should Fix)
1. **invalid-parameter-default (119)** - Easy to fix, improves API clarity
   - Add `Optional[]` wrapper to parameters with `= None`
   - Low risk, high value changes

2. **BeautifulSoup Type Issues (~150)** - Core XML/HTML parsing reliability
   - Cast `PageElement` to `Tag` after None checks
   - Add proper None guards before accessing attributes
   - Affects: xmltools.py, _party.py, ownership, funds

3. **invalid-return-type (78)** - API contract violations
   - Add missing `Optional[]` to return types
   - Fix return statements that can return None

### Medium Priority (Consider Fixing)
4. **possibly-missing-attribute (216)** - Potential runtime errors
   - Add None checks before attribute access
   - Many are warnings, not errors
   - Focus on high-impact files first

5. **invalid-argument-type for simple cases** - Subset of 549
   - Fix obvious type mismatches (str vs Exchange)
   - Leave complex union types for later

### Low Priority (Review Later)
6. **Complex invalid-argument-type issues** - Type system limitations
   - Many involve refinement types (`~AlwaysFalsy`)
   - Some may require `# type: ignore` comments
   - May be false positives from flow typing

7. **Other categories** - Various edge cases
   - Review on case-by-case basis
   - Some may require larger refactoring

## Next Steps

1. **Fix invalid-parameter-default** - Quick wins (~2 hours)
2. **Fix BeautifulSoup issues in xmltools.py** - Core infrastructure (~3 hours)
3. **Fix invalid-return-type** - API improvements (~2 hours)
4. **Incrementally address possibly-missing-attribute** - File by file
5. **Evaluate remaining invalid-argument-type** - Case by case

## Notes

- Total reduction from 1,360 to 1,346 after PyArrow suppressions
- Configuration in place to handle C extension false positives
- Many issues are in specialized modules (funds, ownership, offerings)
- Core modules (_filings.py, entity, xbrl) are relatively clean
