# Invalid Return Type Errors - Analysis & Fixing Strategy

**Issue**: edgartools-v7iz
**Total Errors**: 79 invalid-return-type errors across 32 files
**Generated**: 2025-12-16

## Error Categories

### Category 1: MISSING OPTIONAL (28 errors, ~35%)
**Pattern**: Functions that can return `None` but return type doesn't include `Optional`

**Example**:
```python
# Current (WRONG)
def end_date(self) -> str:
    return str(self.date_range[1]) if self.date_range[1] else self.date_range[1]
    # Can return datetime (when falsy) - not str!

# Fix Option A: Add Optional
def end_date(self) -> Optional[str]:
    return str(self.date_range[1]) if self.date_range[1] else None

# Fix Option B: Ensure always returns str
def end_date(self) -> str:
    return str(self.date_range[1]) if self.date_range[1] else ""
```

**Top Affected Files**:
- edgar/_filings.py (3 errors) - lines 194, 634, 1663
- edgar/funds/reports.py (4 errors) - lines 585, 601, 605
- edgar/entity/entity_facts.py (3 errors) - lines 1298, 1617, 1638
- edgar/xmltools.py (2 errors) - lines 30, 40
- edgar/files/html_documents.py (2 errors) - lines 238, 497

**Fix Strategy**: Add `Optional[]` to return type or ensure non-None return

---

### Category 2: TYPE MISMATCH (23 errors, ~29%)
**Pattern**: Return type annotation doesn't match what function actually returns

**Example**:
```python
# Current (WRONG)
def parse_company_facts(company_facts_json) -> CompanyFacts:
    # But company_facts_json can be None
    return EntityFactsParser.parse_company_facts(company_facts_json)
    # parse_company_facts expects dict[str, Any], gets dict[str, Any] | None

# Fix: Handle None case or change signature
def parse_company_facts(company_facts_json) -> CompanyFacts:
    if company_facts_json is None:
        raise ValueError("No company facts data")
    return EntityFactsParser.parse_company_facts(company_facts_json)
```

**Top Affected Files**:
- edgar/files/html.py (6 errors) - lines 126, 206, 293, etc.
- edgar/entity/entity_facts.py (3 errors) - lines 95, 1184, 1240
- edgar/entity/data.py (2 errors) - lines 435, 653

**Common Subcategories**:
- **None in union**: Function receives `Type | None` but passes to function expecting `Type`
- **Wrong type**: Returns `DataFrame` but annotation says `dict`
- **Union refinement**: Returns specific type from union but annotation too broad

**Fix Strategy**:
1. Add None-checks before calling functions
2. Update return type to match actual returns
3. Add type narrowing/guards

---

### Category 3: IMPLICIT NONE RETURNS (3 errors, ~4%)
**Pattern**: Functions with code paths that don't return anything (implicit `None`)

**Example**:
```python
# Current (WRONG)
def get_statement(statement_type: str) -> Statement:
    statement = self[statement_type]
    return statement.render().to_dataframe()
    # If statement is None or doesn't have render(), implicit None return

# Fix: Add Optional or ensure return
def get_statement(statement_type: str) -> Optional[Statement]:
    statement = self[statement_type]
    if statement is None:
        return None
    return statement.render().to_dataframe()
```

**Affected Files**:
- edgar/xbrl/statements.py (1 error) - line 1238
- edgar/offerings/formc.py (1 error) - line 943
- edgar/npx/parsing.py (1 error) - line 6

**Fix Strategy**: Add `Optional` to return type or add explicit return

---

## Files by Error Count

| Count | File |
|-------|------|
| 10 | edgar/entity/entity_facts.py |
| 10 | edgar/files/html.py |
| 8 | edgar/funds/reports.py |
| 5 | edgar/_filings.py |
| 5 | edgar/files/html_documents.py |
| 4 | edgar/xmltools.py |
| 3 | edgar/documents/document.py |
| 3 | edgar/financials.py |
| 3 | edgar/ownership/ownershipforms.py |
| 2 | edgar/company_reports/press_release.py |
| 2 | edgar/entity/data.py |
| 2 | edgar/files/styles.py |
| 2 | edgar/funds/core.py |
| 2 | edgar/ownership/core.py |
| 1 | 18 other files |

**Total**: 79 errors across 32 files

---

## Recommended Fixing Order

### Phase 1: Simple Fixes (MISSING OPTIONAL - ~28 errors)
Start with these as they're straightforward: add `Optional[]` to return types
- edgar/xmltools.py (2 errors) - utility functions
- edgar/_filings.py (3 errors) - property methods
- edgar/funds/reports.py (4 errors) - data methods
- Other files with 1-2 MISSING OPTIONAL errors

**Estimated effort**: 1-2 hours, low risk

### Phase 2: Medium Complexity (TYPE MISMATCH - ~23 errors)
Requires understanding function logic and adding None-checks or type guards
- edgar/files/html.py (6 errors) - HTML rendering
- edgar/entity/entity_facts.py (partial - 3 errors)
- edgar/entity/data.py (2 errors)

**Estimated effort**: 2-3 hours, medium risk

### Phase 3: Complex Fixes (IMPLICIT NONE + remaining - ~28 errors)
May require refactoring or careful logic changes
- edgar/entity/entity_facts.py (remaining 7 errors) - core financial logic
- edgar/xbrl/statements.py (1 error) - statement rendering
- Other complex type mismatches

**Estimated effort**: 2-4 hours, higher risk (affects core functionality)

---

## Testing Strategy

After each phase:
1. Run `uvx ty check edgar | grep invalid-return-type` to verify count decrease
2. Run relevant test suite: `hatch run test-fast -k <module>`
3. Manual smoke test affected functionality

**Critical areas to test**:
- Company facts retrieval (`test_entity_facts.py`)
- Filing queries (`test_filings.py`)
- XBRL parsing (`test_xbrl.py`)
- HTML rendering (`test_html.py`)

---

## Risk Assessment

**Low Risk** (Can fix immediately):
- Adding Optional to return types where None is already handled
- Properties that clearly can return None

**Medium Risk** (Need careful testing):
- Functions that pass values to other functions
- HTML/XBRL rendering logic
- Data transformation functions

**High Risk** (Requires thorough review):
- Core entity facts logic
- Statement building
- Any function in hot paths (filing retrieval, company lookup)

---

## Success Criteria

1. ✅ `uvx ty check edgar | grep invalid-return-type` returns 0 errors
2. ✅ All existing tests pass
3. ✅ No behavioral changes to public API
4. ✅ Type hints accurately reflect function behavior

---

## Notes

- Most errors are in recently added or refactored code
- Many are in property methods and data transformation functions
- Some indicate potential bugs (functions that might unexpectedly return None)
- Consider this an opportunity to improve error handling
