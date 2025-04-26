# Financial Statements API

## Overview

The Financial Statements API provides a powerful and user-friendly interface for accessing and analyzing company financial statements extracted from SEC XBRL filings. Statements are accessed via the XBRL and XBRLS classes, enabling both single-period and multi-period (trend) analysis.

## Key Classes
- `XBRL` — Main interface for a single filing's financial statements
- `XBRLS` — Interface for stitched, multi-period financial statements
- `Statements` — Accessor for all statement types (balance sheet, income, cash flow, equity, etc.)

## Core Functionality
- Access and display standardized financial statements
- Multi-period (trend) analysis across filings
- Convert statements to pandas DataFrames for analysis
- Smart period selection and comparison views
- Rich rendering for console and notebooks

## Common Patterns

### Accessing Financial Statements from a Filing
```python
from edgar import Company
from edgar.xbrl.xbrl import XBRL

company = Company('AAPL')
filing = company.latest("10-K")

# Parse XBRL data
xbrl = XBRL.from_filing(filing)

# Access statements through the user-friendly API
statements = xbrl.statements

# Display financial statements
balance_sheet = statements.balance_sheet()
income_statement = statements.income_statement()
cash_flow = statements.cashflow_statement()
```

### Multi-Period Analysis with XBRLS
```python
from edgar.xbrl import XBRLS

# Get multiple filings for trend analysis
filings = company.get_filings(form="10-K").head(3)  # Last 3 annual reports
xbrls = XBRLS.from_filings(filings)
stitched_statements = xbrls.statements

# Multi-period statements
income_trend = stitched_statements.income_statement()
balance_sheet_trend = stitched_statements.balance_sheet()
cashflow_trend = stitched_statements.cashflow_statement()
```

### Statement Access and DataFrame Conversion
```python
# Access basic statements
balance_sheet = statements.balance_sheet()
income_statement = statements.income_statement()
cash_flow = statements.cashflow_statement()

# Convert to pandas DataFrame
income_df = income_statement.to_dataframe()
```

### Smart Period Views
```python
# See available period views
period_views = statements.get_period_views("IncomeStatement")
for view in period_views:
    print(f"- {view['name']}: {view['description']}")

# Render with a specific period view
annual_comparison = statements.income_statement(period_view="Annual Comparison")
```

### Rendering and Display Options
```python
# Display with default styling
print(statements.balance_sheet())

# Customize period view
print(statements.income_statement(period_view="Quarterly Comparison"))
```

## User-Friendly Features
- Intuitive method-based access to all major statements
- Multi-period stitching and comparison
- DataFrame export for analysis
- Smart period selection and rich rendering

## Note
Statements should be accessed via the XBRL or XBRLS classes, not directly from Company or TenK objects. This ensures standardized, robust, and future-proof financial data access.
net_income = financials.net_income
total_assets = financials.total_assets
total_liabilities = financials.total_liabilities

# Get custom metrics
custom_metric = financials.get_fact_for_metric("ResearchAndDevelopmentExpense")
```

### Calculating Financial Ratios
```python
# Common financial ratios
profit_margin = financials.get_profit_margin()
current_ratio = financials.get_current_ratio()
debt_to_equity = financials.get_debt_to_equity()
return_on_equity = financials.get_return_on_equity()
```

### Time Series Analysis
```python
# Get quarterly data
quarterly_revenue = financials.get_quarterly_values("RevenueFromContractWithCustomerExcludingAssessedTax")

# Calculate year-over-year growth
def calculate_yoy_growth(series):
    return series.pct_change(4)  # 4 quarters for annual comparison

revenue_growth = calculate_yoy_growth(quarterly_revenue)
```

## Common Financial Metrics
- Revenue: "RevenueFromContractWithCustomerExcludingAssessedTax"
- Gross Profit: "GrossProfit"
- Operating Income: "OperatingIncomeLoss"
- Net Income: "NetIncomeLoss"
- EPS: "EarningsPerShareBasic"
- Total Assets: "Assets"
- Total Liabilities: "Liabilities"
- Total Equity: "StockholdersEquity"
- Operating Cash Flow: "NetCashProvidedByUsedInOperatingActivities"

## Relevant User Journeys
- Company Financial Analysis Journey
- Financial Data Extraction Journey