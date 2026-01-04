# EdgarTools 5.8.0 Release Notes

Release Date: 2026-01-04

## Overview

EdgarTools 5.8.0 is a feature release that introduces major improvements to XBRL statement handling, dimension filtering, and Statement of Equity rendering. This release replaces confusing boolean parameters with semantic enums, fixes critical balance sheet and equity statement bugs, and adds opt-in matrix rendering for equity statements.

## What's New

### StatementView Enum for Semantic Dimension Filtering

Replace the confusing `include_dimensions` boolean with a clear, semantic `StatementView` enum that offers three distinct presentation modes:

```python
from edgar import Filing
from edgar.xbrl import StatementView

filing = Filing(company='Apple Inc', cik='320193', form='10-K',
                filing_date='2024-09-28', accession_no='0000320193-24-000123')
financials = filing.xbrl()

# STANDARD view: Face presentation matching SEC Viewer (default for rendering)
income = financials.income_statement(view=StatementView.STANDARD)
print(income)  # Clean, dimensional breakouts hidden

# DETAILED view: All dimensional data included (default for to_dataframe)
income_df = income.to_dataframe(view=StatementView.DETAILED)
# Returns DataFrame with dimension columns for analysis

# SUMMARY view: Non-dimensional totals only
income_summary = financials.income_statement(view=StatementView.SUMMARY)
# Returns only top-level aggregates without segment breakouts
```

**Key Benefits:**
- Clear semantic meaning: STANDARD, DETAILED, SUMMARY instead of True/False
- Different defaults per use case: STANDARD for display, DETAILED for analysis
- Filters structural XBRL elements (ProductMember, ServiceMember) that appeared as empty rows
- Backward compatible: `include_dimensions` still works with deprecation warning (removed in v6.0)

**Related Issue:** edgartools-dvel (GH-574)

### Enhanced Dimension Labels

Structured dimension fields now available in both statement DataFrames and XBRL facts queries:

```python
# Statement DataFrames now include:
# - dimension: Axis name (e.g., 'srt:ProductOrServiceAxis')
# - member: Member value (e.g., 'us-gaap:ProductMember')
# - dimension_label: Full format (e.g., 'Product and Service: Products')
# - dimension_member_label: Just the member (e.g., 'Products')

# XBRL facts queries have matching columns
facts = financials.query("RevenueFromContractWithCustomerExcludingAssessedTax")
# Filter by specific dimensions
product_revenue = facts[facts['dimension_member_label'] == 'Products']
```

For multi-dimensional items, `dimension_member_label` uses the LAST (most specific) dimension's member label, fixing ambiguities like "Operating segments" vs "Americas".

**Related Issue:** GH-574

### Matrix Rendering for Statement of Equity (Opt-in)

New opt-in matrix format for companies with simple equity structures:

```python
equity = financials.statement_of_equity()

# Standard list format (default - most reliable)
print(equity)  # Hierarchical presentation

# Opt-in matrix format for cleaner visualization
equity_df = equity.to_dataframe(matrix=True)
# Components as columns: Common Stock, APIC, Retained Earnings, AOCI, etc.
# Activities as rows: Net Income, Dividends, Stock-based comp, etc.
```

**Why opt-in?** SEC equity statement formats vary significantly by company. Matrix format works well for companies with simple structures (AAPL, GOOGL, MSFT) but not for complex ones (JPM with many AOCI sub-components). Making it opt-in ensures predictable, reliable output by default.

**Related Issue:** edgartools-uqg7 (GH-574)

## Bug Fixes

### Statement of Equity Period Matching

Fixed critical bug where beginning balance values were incorrectly matched to ending balance rows in Statement of Equity DataFrames.

**The Problem:**
```python
# Before: Beginning balance showed ending values!
equity_df = equity.to_dataframe()
# "Balance at 2023-01-01" row incorrectly showed 2023-12-31 values
```

**The Fix:**
- Track concept occurrences to distinguish first vs. later appearances
- First occurrence (beginning balance): uses instant_{start_date - 1 day}
- Later occurrences (ending balance): uses instant_{end_date}
- Now consistent with render() behavior (Issue #450)

**Related Issue:** edgartools-096c (GH-572)

### Balance Sheet Concept Names

Fixed bug where balance sheet items with certain concept patterns weren't properly recognized or rendered.

**Related Issue:** edgartools-17ow (GH-570)

### ORCL Statement Resolver

Fixed statement resolver to prefer main equity statements over parentheticals for Oracle and similar companies.

**The Problem:** Some companies (ORCL) have both main and parenthetical equity statements. The resolver was sometimes selecting the wrong one.

**The Fix:**
- Added roll-forward concept pattern matching (us-gaap_IncreaseDecreaseInStockholdersEquityRollForward)
- Added -80 score penalty for parenthetical statements
- Ensures main statement is always selected when both are available

**Related Issue:** edgartools-8ad8

## Breaking Changes

None. This release maintains full backward compatibility with v5.7.x.

## Deprecations

- `include_dimensions` parameter in statement methods is deprecated
- Use `view=StatementView.DETAILED` instead of `include_dimensions=True`
- Use `view=StatementView.STANDARD` instead of `include_dimensions=False`
- Deprecated parameter will be removed in v6.0.0
- Deprecation warning raised when used

## Installation

```bash
pip install --upgrade edgartools
```

## Verification

After installing, verify your version:

```python
import edgar
print(edgar.__version__)  # Should print 5.8.0
```

## Contributors

Thank you to all contributors who helped with this release!

Special thanks for issue reports and feedback on:
- Dimension filtering and presentation (GH-574)
- Statement of Equity rendering (GH-572)
- Balance sheet concept handling (GH-570)

## What's Next

Version 5.9.0 will focus on:
- Additional XBRL statement improvements
- Performance optimizations for large datasets
- Enhanced documentation and examples

Version 6.0.0 (future major release) will include:
- Removal of deprecated `include_dimensions` parameter
- Potential breaking changes to dimension column naming
- Other accumulated deprecations

## Full Commit History

```
5b82f208 refactor: Make matrix rendering opt-in for equity statements (GH-574)
7c2fffe1 feat: Add matrix rendering for Statement of Equity (GH-574)
264b8982 fix: Prefer main equity statement over parenthetical in resolver
dde205c6 feat: Add StatementView enum for semantic dimension filtering (GH-574)
06f04456 Filter the new dimension columns from xbrl facts when include_dimension=False
5e544da8 test: Add dimension_member_label to METADATA_COLUMNS in regression tests
6ba736f5 feat: Add structured dimension fields to XBRL facts query results (GH-574)
0037d66c fix: Preserve dimension_label and add dimension_member_label (GH-574)
b6f73b3a fix: Correct Statement of Equity roll-forward instant period matching (GH-572)
```
