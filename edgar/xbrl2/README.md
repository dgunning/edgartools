# XBRL2 Module - Enhanced XBRL Processing for EdgarTools

## Overview

The XBRL2 module provides a powerful yet user-friendly API for processing XBRL (eXtensible Business Reporting Language) financial data from SEC filings. It simplifies the complex task of parsing, analyzing, and displaying financial statements with an intuitive interface designed for both casual users and financial analysts.

## Key Features

- **Intuitive API**: Access financial statements with simple, readable method calls
- **Multi-period Analysis**: Compare financial data across quarters and years with statement stitching
- **Standardized Concepts**: View company-specific terms or standardized labels for cross-company comparison
- **Rich Rendering**: Display beautifully formatted financial statements in console or notebooks
- **Smart Period Selection**: Automatically identify and select relevant periods for meaningful comparisons
- **DataFrame Export**: Convert any statement to pandas DataFrames for further analysis

## Getting Started

### From a Single Filing

```python
from edgar import Company
from edgar.xbrl2.xbrl import XBRL

# Get a company's latest 10-K filing
company = Company('AAPL')
filing = company.latest("10-K")

# Parse XBRL data
xbrl = XBRL.from_filing(filing)

# Access statements through the user-friendly API
statements = xbrl.statements

# Display financial statements
balance_sheet = statements.balance_sheet()
income_statement = statements.income_statement()
cash_flow = statements.cash_flow_statement()
```

### Multi-Period Analysis with XBRLS

```python
from edgar import Company
from edgar.xbrl2.xbrl import XBRLS

# Get multiple filings for trend analysis
company = Company('AAPL')
filings = company.get("10-K", 3)  # Get the last 3 annual reports

# Create a stitched view across multiple filings
xbrls = XBRLS.from_filings(filings)

# Access stitched statements
stitched_statements = xbrls.statements

# Display multi-period statements
income_trend = stitched_statements.income_statement()
balance_sheet_trend = stitched_statements.balance_sheet()
```

## User-Friendly Features

### Simple Statement Access

Access common financial statements with intuitive methods:

```python
# Get basic statements
balance_sheet = statements.balance_sheet()
income_statement = statements.income_statement()
cash_flow = statements.cash_flow_statement()
statement_of_equity = statements.statement_of_equity()

# Access any statement by type
comprehensive_income = statements["ComprehensiveIncome"]
```

### Smart Period Views

Choose from intelligent period selection views:

```python
# See available period views
period_views = statements.get_period_views("IncomeStatement")
for view in period_views:
    print(f"- {view['name']}: {view['description']}")

# Render with specific view
annual_comparison = statements.income_statement(period_view="Annual Comparison")
quarter_comparison = statements.income_statement(period_view="Quarterly Comparison")
```

### Standardized Concepts

Switch between company-specific and standardized terminology:

```python
# Company-specific labels (as reported)
original_income = statements.income_statement(standard=False)

# Standardized labels (for cross-company comparison)
standardized_income = statements.income_statement(standard=True)
```

### Easy Conversion to DataFrames

Transform any statement into a pandas DataFrame for further analysis:

```python
# Get DataFrame of income statement
df = statements.to_dataframe("IncomeStatement")

# Filter for revenues
revenue_df = df[df['concept'].str.contains('Revenue')]

# Plot trends
import matplotlib.pyplot as plt
plt.figure(figsize=(10, 6))
for column in df.columns:
    if column not in ['concept', 'label', 'level', 'is_abstract']:
        plt.plot(column, df.loc[df['label'] == 'Revenue', column], label=column)
plt.legend()
plt.title('Revenue Trend')
plt.show()
```

## Statement Stitching for Trend Analysis

The XBRLS class combines data from multiple periods with intelligent handling of concept changes:

```python
# Create stitched statements across multiple filings
xbrls = XBRLS.from_filings(filings)
stitched = xbrls.statements

# Get a three-year comparison of income statements
income_trend = stitched.income_statement(max_periods=3)

# Convert to DataFrame for time series analysis
trend_df = income_trend.to_dataframe()
```

## Rendering Options

Statements are rendered as rich tables with proper formatting:

```python
# Display with default styling
print(statements.balance_sheet())

# Convert to pandas for custom visualization
df = statements.to_dataframe("BalanceSheet")
```

## Advanced Features

### Custom Period Selection

```python
# Get specific periods from available options
available_periods = xbrl.reporting_periods
latest_period = available_periods[0]

# Render with specific period
if latest_period['type'] == 'instant':
    period_filter = f"instant_{latest_period['date']}"
    latest_balance_sheet = statements.balance_sheet().render(period_filter=period_filter)
```

### Statement Data Exploration

```python
# Get raw statement data for custom processing
raw_data = statements.balance_sheet().get_raw_data()

# Extract specific information
assets = [item for item in raw_data if 'assets' in item['label'].lower()]
```

## Design Philosophy

The XBRL2 module is designed with these principles:

1. **User-First API**: Simple methods that match how financial analysts think about statements
2. **Intelligent Defaults**: Smart period selection and formatting that "just works" out of the box
3. **Flexible Output Options**: Rich tables for display, DataFrames for analysis, and raw data for custom processing
4. **Consistency Across Companies**: Standardized concepts that enable cross-company comparison

## Enhanced Facts API

The XBRL2 module includes a powerful facts query interface for direct access to individual XBRL facts:

```python
from edgar import Company
from edgar.xbrl2 import XBRL

# Parse XBRL data
company = Company('AAPL')
filing = company.latest_10k()
xbrl = XBRL.from_filing(filing)

# Access the facts view
facts = xbrl.facts_view

# Query facts by various attributes
revenue = facts.query().by_concept('Revenue').to_dataframe()
balance_sheet_facts = facts.query().by_statement_type('BalanceSheet').to_dataframe()

# Use predefined period views - returns important metadata including available periods
income_views = facts.get_available_period_views('IncomeStatement')
for view in income_views:
    print(f"- {view['name']}: {view['description']} ({view['facts_count']} facts)")
    
# Get facts filtered by period view
annual_comparison = facts.get_facts_by_period_view('IncomeStatement', 'Annual Comparison')

# Flexible text search across all text fields (concept, label, element name)
earnings_facts = facts.search_facts("Earnings Per Share")

# Filter by period keys - useful for custom period selection
facts.query().by_period_keys(['duration_2023-01-01_2023-12-31', 
                             'duration_2022-01-01_2022-12-31']).to_dataframe()

# Query dimensional data
facts_by_segment = facts.query().by_dimension('Segment').to_dataframe()

# Safe numeric value filtering with proper None handling
large_income_items = facts.query() \
    .by_statement_type('IncomeStatement') \
    .by_value(lambda v: v > 1_000_000_000) \
    .sort_by('numeric_value', ascending=False) \
    .to_dataframe()
    
# Time series analysis
revenue_over_time = facts.time_series('Revenue')
```

## Future Enhancements

- Enhanced support for non-standard financial statements
- Interactive visualization options
- Expanded dimensional analysis capabilities
- Automatic footnote association
- Financial ratio calculations