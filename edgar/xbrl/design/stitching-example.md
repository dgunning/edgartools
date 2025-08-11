# XBRL Statement Stitching Examples

This document demonstrates how to use the statement stitching functionality to combine financial statements across multiple XBRL filings for the same company. This allows you to analyze trends over time and compare multiple periods in a single view.

## Basic Usage

The most common use case is to stitch together statements from multiple quarterly or annual filings:

```python
from edgar import Company, XBRL

# Get a list of filings for a company
company = Company.find("AAPL")  # Apple Inc.
filings = company.get_filings(form="10-Q", count=4)  # Get the last 4 quarterly filings

# Parse XBRL from each filing
xbrl_list = [XBRL.from_filing(filing) for filing in filings]

# Stitch income statements from the last 3 quarters
stitched_income = XBRL.stitch_statements(
    xbrl_list,
    statement_type="IncomeStatement",
    period_type="THREE_QUARTERS",
    max_periods=3,
    standard=True  # Use standardized concepts for consistent labels
)

# Render the stitched statement as a rich table
income_table = xbrl_list[0].render_stitched_statement(
    stitched_income,
    "Apple Inc. Consolidated Statements of Operations",
    "IncomeStatement"
)

# Display the table
display(income_table)

# Convert to pandas DataFrame for analysis
import pandas as pd
from edgar.xbrl.stitching import to_pandas

income_df = to_pandas(stitched_income)
display(income_df)
```

## Period Selection Options

The statement stitcher supports different period selection strategies to customize your multi-period view:

```python
from edgar.xbrl.stitching import StatementStitcher

# Available period types:
# 1. For income statements and cash flow statements (duration periods)
stitched_income_quarterly = XBRL.stitch_statements(
    xbrl_list,
    statement_type="IncomeStatement",
    period_type=StatementStitcher.PeriodType.THREE_QUARTERS,  # Most recent 3 quarters
    standard=True
)

stitched_income_annual = XBRL.stitch_statements(
    xbrl_list,
    statement_type="IncomeStatement",
    period_type=StatementStitcher.PeriodType.ANNUAL_COMPARISON,  # Annual periods only
    standard=True
)

# 2. For balance sheets (instant periods)
stitched_balance_sheet = XBRL.stitch_statements(
    xbrl_list,
    statement_type="BalanceSheet",
    period_type=StatementStitcher.PeriodType.THREE_YEAR_COMPARISON,  # Last 3 year-ends
    standard=True
)

# 3. For any statement type
stitched_recent = XBRL.stitch_statements(
    xbrl_list,
    statement_type="IncomeStatement",
    period_type=StatementStitcher.PeriodType.RECENT_PERIODS,  # Most recent periods (default)
    max_periods=3,
    standard=True
)

stitched_all = XBRL.stitch_statements(
    xbrl_list,
    statement_type="IncomeStatement",
    period_type=StatementStitcher.PeriodType.ALL_PERIODS,  # All available periods
    max_periods=10,  # Limit to 10 periods maximum
    standard=True
)
```

## Combining Annual and Quarterly Data

You can stitch together a mix of annual and quarterly filings to see both long-term and short-term trends:

```python
# Get both annual and quarterly filings
annual_filings = company.get_filings(form="10-K", count=3)  # Last 3 annual filings
quarterly_filings = company.get_filings(form="10-Q", count=4)  # Last 4 quarterly filings

# Combine and sort by filing date (newest first)
all_filings = annual_filings + quarterly_filings
all_filings.sort(key=lambda f: f.filing_date, reverse=True)

# Parse XBRL from all filings
xbrl_list = [XBRL.from_filing(filing) for filing in all_filings]

# Stitch income statements with mixed periods
stitched_mixed = XBRL.stitch_statements(
    xbrl_list,
    statement_type="IncomeStatement",
    period_type=StatementStitcher.PeriodType.RECENT_PERIODS,
    max_periods=5,  # Show up to 5 periods
    standard=True
)
```

## Standardization

Statement stitching works best with standardization enabled (`standard=True`), which normalizes concepts across different filings and companies:

```python
# Without standardization - company-specific labels are preserved
stitched_raw = XBRL.stitch_statements(
    xbrl_list,
    statement_type="IncomeStatement",
    period_type="THREE_QUARTERS",
    standard=False  # Use original, non-standardized labels
)

# With standardization - consistent labels across filings
stitched_standardized = XBRL.stitch_statements(
    xbrl_list,
    statement_type="IncomeStatement",
    period_type="THREE_QUARTERS",
    standard=True  # Use standardized concept labels (recommended)
)
```

## Advanced Usage: Custom Period Selection

For more control over period selection, you can use the `StatementStitcher` class directly:

```python
from edgar.xbrl.stitching import StatementStitcher

# Extract statements from XBRL objects
statements = []
for xbrl in xbrl_list:
    statement = xbrl.find_statement("IncomeStatement")
    if statement:
        statements.append(statement)

# Create a stitcher and customize the period selection
stitcher = StatementStitcher()
stitched_data = stitcher.stitch_statements(
    statements,
    period_type=StatementStitcher.PeriodType.RECENT_PERIODS,
    max_periods=3,
    standard=True
)

# Render the stitched statement
from edgar.xbrl.stitching import render_stitched_statement

table = render_stitched_statement(
    stitched_data,
    "Custom Period Selection",
    "IncomeStatement",
    entity_info=xbrl_list[0].entity_info
)
display(table)
```

## Notes and Best Practices

1. **Ordering**: Provide XBRL objects in chronological order (newest first) for best results.

2. **Statement Types**: Make sure to use consistent statement types:
   - "IncomeStatement" - For income statements
   - "BalanceSheet" - For balance sheets
   - "CashFlowStatement" - For cash flow statements
   - "StatementOfEquity" - For statements of equity

3. **Period Types**: Choose the appropriate period type based on the statement type:
   - Use `THREE_QUARTERS` or `ANNUAL_COMPARISON` for income statements and cash flows
   - Use `THREE_YEAR_COMPARISON` for balance sheets
   - Use `RECENT_PERIODS` as a general-purpose option for any statement type

4. **Standardization**: Always use `standard=True` when comparing across multiple filings or multiple companies, as it ensures consistent concept mapping.

5. **Performance**: The stitcher is optimized to handle a large number of statements efficiently, but performance may degrade with very large datasets (20+ statements). In such cases, consider filtering to a smaller set of periods.