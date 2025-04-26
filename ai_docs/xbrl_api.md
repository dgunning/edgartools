# XBRL API

## Overview
The XBRL API extracts structured financial data from SEC filings, providing access to financial statements, metrics, and facts.

## Key Classes
- `XBRLData` - Container for XBRL financial data with presentation linkages
- `XBRLInstance` - Basic XBRL instance data without presentation linkages
- `Financials` - High-level interface for financial statements

## Core Functionality
- Extract financial statements from filings
- Access individual financial facts and metrics
- Work with standardized financial data
- Track financial metrics over time

## Common Patterns

### Accessing XBRL from Filings
```python
# Get XBRL from a filing
filing = company.get_filings(form="10-K").latest()
xbrl_data = filing.xbrl()

# Or directly from company financials
financials = company.financials
```

### Working with Financial Statements
```python
# Access common financial statements
income_statement = financials.income_statement
balance_sheet = financials.balance_sheet
cashflow = financials.cashflow_statement

# Get as DataFrame
income_df = income_statement.get_dataframe()
```

### Extracting Specific Metrics
```python
# Get a specific financial fact
revenue = financials.get_fact_for_metric("RevenueFromContractWithCustomerExcludingAssessedTax")
net_income = financials.get_fact_for_metric("NetIncomeLoss")

# Calculate financial ratios
profit_margin = financials.get_profit_margin()
pe_ratio = financials.get_pe_ratio()
```

### Working with Financial Time Series
```python
# Get quarterly data
quarterly_revenue = financials.get_quarterly_values("RevenueFromContractWithCustomerExcludingAssessedTax")

# Get annual data
annual_revenue = financials.get_annual_values("RevenueFromContractWithCustomerExcludingAssessedTax")
```

## Common Financial Metrics
- Revenue: "RevenueFromContractWithCustomerExcludingAssessedTax"
- Net Income: "NetIncomeLoss"
- Total Assets: "Assets"
- Total Liabilities: "Liabilities"
- EPS: "EarningsPerShareBasic", "EarningsPerShareDiluted"

## Relevant User Journeys
- Financial Data Extraction Journey
- Company Financial Analysis Journey