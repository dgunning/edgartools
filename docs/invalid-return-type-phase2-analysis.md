# Phase 2: TYPE MISMATCH Errors - Analysis

**Generated**: 2025-12-16
**Previous Progress**: Phase 1 fixed 17 MISSING OPTIONAL errors (8 in this session)
**Remaining**: ~130 invalid-return-type errors (mostly TYPE MISMATCH)

## Safe Fixes (Low Risk)

### 1. edgar/ownership/ownershipforms.py

#### Line 327: transaction_footnote_id - Wrong tuple type
**Current**:
```python
def transaction_footnote_id(tag: Tag) -> Tuple[str, str]:
    return 'footnote', tag.attrs.get("id") if tag else None
```

**Issue**: Can return `('footnote', None)` but expects `Tuple[str, str]`

**Fix**:
```python
def transaction_footnote_id(tag: Tag) -> Tuple[str, Optional[str]]:
    return 'footnote', tag.attrs.get("id") if tag else None
```

**Risk**: LOW - Just updating type annotation to match reality

---

#### Line 333: get_footnotes - None in list comprehension
**Current**:
```python
def get_footnotes(tag: Tag) -> str:
    return '\n'.join([
        el.attrs.get('id') for el in tag.find_all("footnoteId")
    ])
```

**Issue**: `el.attrs.get('id')` can return None, but join expects strings. Also, `find_all` returns `PageElement` which might not have `attrs`.

**Fix**:
```python
def get_footnotes(tag: Tag) -> str:
    return '\n'.join([
        el.attrs.get('id', '') for el in tag.find_all("footnoteId")
        if isinstance(el, Tag) and el.attrs.get('id')
    ])
```

**Risk**: LOW - Filtering out None values, same behavior but type-safe

---

#### Line 1068: shares_numeric - float vs int mismatch
**Current**:
```python
@property
def shares_numeric(self) -> Optional[int]:
    """Get shares as a numeric value, handling footnotes"""
    return safe_numeric(self.shares)
```

**Issue**: `safe_numeric()` returns `int | float | None` but annotation says `int | None`

**Fix Option A** (Change return type):
```python
@property
def shares_numeric(self) -> Optional[Union[int, float]]:
    """Get shares as a numeric value, handling footnotes"""
    return safe_numeric(self.shares)
```

**Fix Option B** (Cast to int):
```python
@property
def shares_numeric(self) -> Optional[int]:
    """Get shares as a numeric value, handling footnotes"""
    result = safe_numeric(self.shares)
    return int(result) if result is not None else None
```

**Risk**: MEDIUM - Option A is safer (preserves precision), Option B might lose precision

---

#### Line 1186: total_shares - sum can return float
**Current**:
```python
@property
def total_shares(self) -> int:
    """Get total non-derivative shares owned"""
    return sum(safe_numeric(h.shares) or 0 for h in self.holdings if not h.is_derivative)
```

**Issue**: `sum()` can return float if any value is float, but expects int

**Fix Option A** (Cast to int):
```python
@property
def total_shares(self) -> int:
    """Get total non-derivative shares owned"""
    return int(sum(safe_numeric(h.shares) or 0 for h in self.holdings if not h.is_derivative))
```

**Fix Option B** (Change type):
```python
@property
def total_shares(self) -> Union[int, float]:
    """Get total non-derivative shares owned"""
    return sum(safe_numeric(h.shares) or 0 for h in self.holdings if not h.is_derivative)
```

**Risk**: MEDIUM - Option A is reasonable (share counts should be ints), but might hide float inputs

---

## Medium Risk Fixes

### 2. edgar/financials.py - Statement type mismatch

**Lines 390, 393, 396**:
```python
def balance_sheet(self) -> Optional[Statement]:
    return self.xbs.statements.balance_sheet()  # Returns Unknown | StitchedStatement | None

def income_statement(self) -> Optional[Statement]:
    return self.xbs.statements.income_statement()  # Returns Unknown | StitchedStatement | None

def cashflow_statement(self) -> Optional[Statement]:
    return self.xbs.statements.cashflow_statement()  # Returns Unknown | StitchedStatement | None
```

**Issue**: Returns `StitchedStatement` but annotation says `Statement`

**Fix**: Need to understand inheritance - is `StitchedStatement` a subclass of `Statement`? If yes, change return type. If no, need type guard.

**Investigation needed**:
- Check `StitchedStatement` class definition
- Verify if it's compatible with `Statement`
- May need `Union[Statement, StitchedStatement]` or cast

**Risk**: MEDIUM-HIGH - Affects API consumers

---

## High Risk / Complex Fixes

### 3. edgar/files/html.py - RenderResult mismatches

**Multiple lines (124, 147, 211, 293, etc.)**:
```python
def render(self, console_width: int) -> RenderResult:
    return Text(...)  # Returns Text, expects Iterable[ConsoleRenderable | ...]
```

**Issue**: `RenderResult` is for generators that yield renderables, but methods return single renderables

**Fix**: Change return type from `RenderResult` to appropriate type:
```python
def render(self, console_width: int) -> Text:
    return Text(...)
```

**Note**: This file is DEPRECATED (will be removed in v6.0), so fixes may not be worth the effort

**Risk**: LOW impact (deprecated code) but HIGH volume (many occurrences)

---

### 4. edgar/entity/entity_facts.py - Complex union and protocol types

**Multiple lines with complex type mismatches**:
- Line 95, 1121, 1184, 1221, 1240, 1284, 1298, etc.

**Issues**:
- DataFrame protocol vs concrete DataFrame
- MultiPeriodStatement vs FinancialStatement
- UnitResult vs float return types
- Dictionary with mixed value types

**Analysis needed**: Requires careful review of each case

**Risk**: HIGH - Core financial data functionality

---

## Recommended Phase 2 Approach

### Step 1: Safe Fixes (Start here)
1. Fix `edgar/ownership/ownershipforms.py` lines 327, 333 (tuple and list fixes)
2. Commit and test

### Step 2: Medium Risk (After testing)
1. Fix `edgar/ownership/ownershipforms.py` lines 1068, 1186 (numeric type fixes)
2. Investigate `edgar/financials.py` StitchedStatement issue
3. Commit and test

### Step 3: Defer to Phase 3
1. `edgar/files/html.py` - deprecated code, low priority
2. `edgar/entity/entity_facts.py` - complex, needs thorough analysis

---

## Testing Strategy

After each fix:
```bash
# Run type check
uvx ty check edgar/ownership/ownershipforms.py

# Run relevant tests
hatch run test-fast -k ownership

# Check for regressions
hatch run test-fast
```

---

## Success Metrics

- [ ] Fix 4 safe errors in ownershipforms.py
- [ ] Investigate and document financials.py issue
- [ ] All tests pass
- [ ] No new type errors introduced
