# Implementation Plan: StatementView API

**Date Created**: 2026-01-03
**Status**: Planning
**Related Issues**: Follows from dimension handling epic (edgartools-445y)

## Overview

Replace the confusing `include_dimensions` boolean with a semantic `StatementView` enum that clearly communicates user intent and aligns with our North Star goals.

## Goals

1. **Clarity**: API clearly expresses what the user wants to see
2. **Consistency**: Same parameter works in render path and to_dataframe
3. **Extensibility**: Enum allows future view modes without API changes
4. **Backward Compatibility**: Existing code continues to work with deprecation warning

## North Star Alignment

| North Star Goal | StatementView Mode |
|-----------------|-------------------|
| Default matches SEC Viewer | `STANDARD` (default) |
| Full data for custom processing | `DETAILED` |
| New: Summary totals only | `SUMMARY` |

## API Design

### Enum Definition

```python
from enum import Enum

class StatementView(str, Enum):
    """Controls dimensional data display in financial statements.

    STANDARD: Face presentation matching SEC Viewer (default)
              Shows face-level dimensions, hides breakdowns

    DETAILED: All dimensional data included
              For custom analysis and data processing

    SUMMARY:  Non-dimensional totals only
              Hides all dimensional rows
    """

    STANDARD = "standard"
    DETAILED = "detailed"
    SUMMARY = "summary"

    def __str__(self):
        return self.value
```

Using `str, Enum` enables both enum and string usage:
```python
stmt.to_dataframe(view=StatementView.STANDARD)  # enum
stmt.to_dataframe(view="standard")               # string
```

### Behavior Matrix

| View | Face Dimensions | Breakdowns | Non-dimensional |
|------|----------------|------------|-----------------|
| `STANDARD` | ✅ Show | ❌ Hide | ✅ Show |
| `DETAILED` | ✅ Show | ✅ Show | ✅ Show |
| `SUMMARY` | ❌ Hide | ❌ Hide | ✅ Show |

### Usage Examples

```python
from edgar import Company
from edgar.xbrl import StatementView

company = Company("BA")
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Default: Standard view (SEC Viewer style)
income = xbrl.statements.income_statement()
print(income)  # Renders with STANDARD view

# Explicit view modes
income_detailed = xbrl.statements.income_statement(view=StatementView.DETAILED)
income_summary = xbrl.statements.income_statement(view=StatementView.SUMMARY)

# DataFrame export respects view
df_standard = income.to_dataframe()  # Uses statement's view
df_detailed = income.to_dataframe(view=StatementView.DETAILED)  # Override

# String shorthand works too
df = income.to_dataframe(view="detailed")
```

## Implementation Phases

### Phase 1: Core Enum and Statement Class ⬜

**Goal**: Add StatementView enum and update Statement.to_dataframe()

**Files**:

1. `edgar/xbrl/presentation.py` (new file):
   ```python
   from enum import Enum
   from typing import Union

   class StatementView(str, Enum):
       """Controls dimensional data display in financial statements."""

       STANDARD = "standard"
       DETAILED = "detailed"
       SUMMARY = "summary"

       def __str__(self):
           return self.value

   # Type alias for parameter hints
   ViewType = Union[StatementView, str]

   def normalize_view(view: ViewType) -> StatementView:
       """Convert string or enum to StatementView."""
       if isinstance(view, StatementView):
           return view
       try:
           return StatementView(view.lower())
       except ValueError:
           raise ValueError(
               f"Invalid view '{view}'. Must be one of: "
               f"{', '.join(v.value for v in StatementView)}"
           )
   ```

2. `edgar/xbrl/statements.py`:
   - Import `StatementView`, `ViewType`, `normalize_view`
   - Add `view` parameter to `Statement.__init__()` to store default view
   - Update `Statement.to_dataframe()`:
     ```python
     def to_dataframe(
         self,
         view: ViewType = None,  # None = use statement's default
         include_dimensions: bool = None,  # deprecated
         include_concept: bool = True,
         include_format: bool = False,
     ) -> pd.DataFrame:
         # Handle deprecation
         if include_dimensions is not None:
             import warnings
             warnings.warn(
                 "include_dimensions is deprecated. Use view='standard'|'detailed'|'summary'",
                 DeprecationWarning,
                 stacklevel=2
             )
             view = StatementView.DETAILED if include_dimensions else StatementView.STANDARD

         # Use statement's default if not specified
         if view is None:
             view = self._view
         else:
             view = normalize_view(view)

         # Apply view-based filtering
         if view == StatementView.STANDARD:
             # Current behavior: filter breakdowns, keep face dimensions
             ...
         elif view == StatementView.DETAILED:
             # Show all dimensions
             ...
         elif view == StatementView.SUMMARY:
             # Hide all dimensional rows
             ...
     ```

3. `edgar/xbrl/__init__.py`:
   - Export `StatementView`

**Verification**:
- [ ] `StatementView.STANDARD` works
- [ ] `"standard"` string works
- [ ] Invalid values raise clear error
- [ ] `include_dimensions=True` triggers deprecation warning
- [ ] `include_dimensions=False` triggers deprecation warning
- [ ] Behavior matches matrix for all three views

### Phase 2: Rendering Path ⬜

**Goal**: Update render path to use StatementView

**Files**:

1. `edgar/xbrl/rendering.py`:
   - Update `render_statement()` signature:
     ```python
     def render_statement(
         xbrl: 'XBRL',
         statement_name: str,
         view: ViewType = StatementView.STANDARD,
         ...
     ) -> RenderedStatement:
     ```
   - Pass view through to statement filtering logic
   - Update `_filter_items_for_display()` or equivalent to respect view

2. `edgar/xbrl/statements.py`:
   - Update `Statement.__rich__()` to use stored view:
     ```python
     def __rich__(self):
         # Render using self._view
         ...
     ```

**Verification**:
- [ ] `print(income_statement)` uses STANDARD view by default
- [ ] Statement created with DETAILED view renders with all dimensions
- [ ] Rich output matches view setting

### Phase 3: Statement Accessor Methods ⬜

**Goal**: Allow view to be specified when getting statements

**Files**:

1. `edgar/xbrl/xbrl.py`:
   - Update `StatementAccessor` methods:
     ```python
     class StatementAccessor:
         def income_statement(
             self,
             view: ViewType = StatementView.STANDARD
         ) -> Statement:
             stmt = self._get_statement("IncomeStatement")
             stmt._view = normalize_view(view)
             return stmt

         def balance_sheet(
             self,
             view: ViewType = StatementView.STANDARD
         ) -> Statement:
             ...

         # Same for cash_flow_statement, etc.
     ```

**Verification**:
- [ ] `xbrl.statements.income_statement(view="detailed")` works
- [ ] Default view is STANDARD
- [ ] Statement carries view through to render and to_dataframe

### Phase 4: SUMMARY View Implementation ⬜

**Goal**: Implement the new SUMMARY view (non-dimensional only)

**Files**:

1. `edgar/xbrl/dimensions.py`:
   - Add helper function:
     ```python
     def is_dimensional_item(item: Dict[str, Any]) -> bool:
         """Check if item has any dimensional data."""
         return bool(item.get('dimension_metadata'))
     ```

2. `edgar/xbrl/statements.py`:
   - In filtering logic:
     ```python
     if view == StatementView.SUMMARY:
         # Filter out ALL dimensional items
         items = [item for item in items if not is_dimensional_item(item)]
     ```

**Verification**:
- [ ] SUMMARY view shows only non-dimensional rows
- [ ] Boeing income statement with SUMMARY shows NaN for COGS (expected)
- [ ] Companies with non-dimensional data show correct values

### Phase 5: Documentation and Tests ⬜

**Goal**: Update documentation and add comprehensive tests

**Files**:

1. `docs/xbrl/dimension-handling.md`:
   - Update usage examples to use StatementView
   - Add section on view modes

2. `tests/xbrl/test_statement_view.py` (new):
   ```python
   class TestStatementView:
       def test_enum_values(self):
           assert StatementView.STANDARD.value == "standard"
           assert StatementView.DETAILED.value == "detailed"
           assert StatementView.SUMMARY.value == "summary"

       def test_string_conversion(self):
           assert normalize_view("standard") == StatementView.STANDARD
           assert normalize_view("DETAILED") == StatementView.STANDARD

       def test_invalid_view_raises(self):
           with pytest.raises(ValueError):
               normalize_view("invalid")

       def test_deprecation_warning(self):
           with pytest.warns(DeprecationWarning):
               stmt.to_dataframe(include_dimensions=True)

   @pytest.mark.network
   class TestStatementViewBehavior:
       def test_standard_view_filters_breakdowns(self):
           ...

       def test_detailed_view_shows_all(self):
           ...

       def test_summary_view_hides_dimensional(self):
           ...
   ```

3. Update existing tests:
   - Replace `include_dimensions=False` with `view=StatementView.STANDARD`
   - Replace `include_dimensions=True` with `view=StatementView.DETAILED`

**Verification**:
- [ ] All new tests pass
- [ ] Existing tests pass (backward compatibility)
- [ ] Documentation builds correctly

## Deprecation Timeline

| Version | Status |
|---------|--------|
| v5.8.0 | Introduce `StatementView`, `include_dimensions` emits `DeprecationWarning` |
| v5.9.0 | `include_dimensions` emits `FutureWarning` |
| v6.0.0 | Remove `include_dimensions` parameter |

## Files Summary

| File | Action |
|------|--------|
| `edgar/xbrl/presentation.py` | **New** - StatementView enum |
| `edgar/xbrl/statements.py` | Update - to_dataframe(), __rich__() |
| `edgar/xbrl/rendering.py` | Update - render_statement() |
| `edgar/xbrl/xbrl.py` | Update - StatementAccessor methods |
| `edgar/xbrl/dimensions.py` | Update - add is_dimensional_item() |
| `edgar/xbrl/__init__.py` | Update - export StatementView |
| `docs/xbrl/dimension-handling.md` | Update - new examples |
| `tests/xbrl/test_statement_view.py` | **New** - view tests |

## Success Criteria

- [ ] `StatementView` enum exported from `edgar.xbrl`
- [ ] All three views work in both render and to_dataframe paths
- [ ] String values work as convenience alternative to enum
- [ ] `include_dimensions` continues to work with deprecation warning
- [ ] Default behavior unchanged (STANDARD = previous include_dimensions=False)
- [ ] Documentation updated with new API
- [ ] Comprehensive test coverage

## Open Questions

1. **Presentation file location**: New `presentation.py` or add to existing `statements.py`?
2. **Default view storage**: Store on Statement instance or pass through each call?
3. **Render method signature**: Should `__rich__()` accept view parameter or always use stored view?

## Estimated Effort

- Phase 1 (Core): 2-3 hours
- Phase 2 (Rendering): 1-2 hours
- Phase 3 (Accessor): 1 hour
- Phase 4 (SUMMARY): 1 hour
- Phase 5 (Docs/Tests): 2-3 hours
- **Total**: 7-10 hours
