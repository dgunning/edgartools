# XBRL2 Module - Enhanced XBRL Processing for EdgarTools

## Overview

The XBRL2 module provides an enhanced, integrated parser for XBRL (eXtensible Business Reporting Language) data. It is designed to process the full collection of XBRL files that make up a complete SEC filing, including:

- Instance documents (containing the actual facts/values)
- Schema files (describing the elements)
- Presentation linkbases (defining statement structure)
- Calculation linkbases (defining mathematical relationships)
- Definition linkbases (defining dimensional relationships)
- Label linkbases (providing human-readable labels)

The module provides a single, unified interface to work with XBRL data, offering improvements over the original XBRL parser:

- Comprehensive processing of all XBRL file types
- Clean data model based on Pydantic models
- Support for dimensional data
- Calculation validation
- Easy pandas DataFrame conversion
- Rich console display

## Usage Examples

### Parsing a Directory of XBRL Files

```python
from edgar.xbrl2.xbrl import XBRL

# Parse all XBRL files in a directory
xbrl = XBRL.parse_directory('/path/to/xbrl/files')

# Print information about the XBRL document
print(xbrl)

# Get all available statements
statements = xbrl.get_all_statements()
for stmt in statements:
    print(f"- {stmt['definition']} ({stmt['element_count']} elements)")
```

### Working with Financial Statements

```python
# Get a specific statement by role
balance_sheet_role = next(stmt['role'] for stmt in statements if stmt['type'] == 'BalanceSheet')
statement_data = xbrl.get_statement(balance_sheet_role)

# Print the statement structure
for item in statement_data:
    indent = '  ' * item['level']
    print(f"{indent}{item['label']}")
    
    # Print values if available
    if item['values'] and not item['is_abstract']:
        for period, value in item['values'].items():
            print(f"{indent}  {period}: {value}")
```

### Rendering Financial Statements

```python
from rich.console import Console
console = Console()

# Render a balance sheet (automatically selects the right role)
balance_sheet = xbrl.render_statement("BalanceSheet")
console.print(balance_sheet)

# Render an income statement
income_statement = xbrl.render_statement("IncomeStatement")
console.print(income_statement)

# Render a cash flow statement
cash_flow_statement = xbrl.render_statement("CashFlowStatement")
console.print(cash_flow_statement)
```

### Using Period Views for Comparative Analysis

```python
# Get available period views for a statement type
balance_sheet_views = xbrl.get_period_views("BalanceSheet")
for view in balance_sheet_views:
    print(f"- {view['name']}: {view['description']}")

# Render balance sheet with a specific period view
bs_current_vs_previous = xbrl.render_statement("BalanceSheet", period_view="Current vs Previous")
console.print(bs_current_vs_previous)

# Get available period views for income statement
income_statement_views = xbrl.get_period_views("IncomeStatement")
for view in income_statement_views:
    print(f"- {view['name']}: {view['description']}")

# Render income statement with quarterly data
quarterly_view = next((v['name'] for v in income_statement_views if 'Quarterly' in v['name']), None)
if quarterly_view:
    is_quarterly = xbrl.render_statement("IncomeStatement", period_view=quarterly_view)
    console.print(is_quarterly)

# Render statement with a specific period filter (for custom analyses)
instant_periods = [p for p in xbrl.reporting_periods if p['type'] == 'instant']
if instant_periods:
    latest_period = f"instant_{instant_periods[0]['date']}"
    balance_sheet_current = xbrl.render_statement("BalanceSheet", period_filter=latest_period)
    console.print(balance_sheet_current)
```

### Converting to Pandas DataFrame

```python
# Convert to pandas DataFrame
dataframes = xbrl.to_pandas(balance_sheet_role)

# All facts
facts_df = dataframes['facts']
print(facts_df.head())

# Specific statement
statement_df = dataframes['statement']
print(statement_df.head())
```

### Creating from a Filing Object

```python
from edgar import Filing
from edgar.xbrl2.xbrl import XBRL

# Get a filing from EdgarTools
filing = Filing.get('0000320193-23-000077')  # Apple 10-K

# Parse XBRL data from the filing
xbrl = XBRL.from_filing(filing)
```

## Key Classes

- `XBRL`: Main class that integrates all XBRL components
- `ElementCatalog`: Represents an XBRL element with its properties
- `Context`: Represents an XBRL context (entity, period, dimensions)
- `Fact`: Represents an XBRL fact with value and references
- `PresentationNode`/`PresentationTree`: Represents presentation hierarchy
- `CalculationNode`/`CalculationTree`: Represents calculation relationships
- `Table`/`Axis`/`Domain`: Represents dimensional structures

## Design Principles

This module follows these design principles:

1. **Integration**: Unifies all XBRL components under a single interface
2. **Parsing Order**: Follows logical dependencies when parsing (schema → labels → presentation → etc.)
3. **Clean Data Model**: Uses Pydantic models for type safety and validation
4. **Compatibility**: Maintains backward compatibility with existing EdgarTools functionality

## Recent Enhancements

Recent enhancements include:

- Statement detection using standard taxonomy concepts (us-gaap_StatementOfFinancialPositionAbstract, etc.)
- Financial statement rendering in tabular format similar to actual filings
- Statement selection by standard type name (BalanceSheet, IncomeStatement, etc.)
- Intelligent period selection with comparative period matching for statement rendering
- Support for different period views (quarterly, annual, current only, etc.)
- Better period selection for Income/Cash Flow statements
- Professional formatting with headers noting the scale (e.g., "In millions, except per share data")
- Automatic detection of document scale (thousands, millions, billions)
- No more individual value suffixes (the "M", "K", "B" suffixes are removed in favor of a header)
- Filtering out dimensional items ([Axis], [Member], etc.) for cleaner statement displays
- Improved rendering options with standardized formats for headers, subtotals, etc.
- A simple Statements class with user-friendly API for accessing financial statements

## Future Enhancements

Planned future enhancements include:

- Complete dimensional analysis support
- Enhanced calculation validation
- Time series analysis of fact values
- Automatic footnote association
- Statement comparison across periods
- Enhanced support for customized taxonomies
- Performance optimizations for large XBRL documents
- Export to Excel or CSV formats
- Interactive visualization options

## New Features Available

### User-friendly Statements API

```python
from edgar import Filing
from edgar.xbrl2.xbrl import XBRL
from edgar.xbrl2.statements import Statements

# Parse XBRL from a filing
filing = Filing.get('0000320193-23-000077')  # Apple 10-K
xbrl = XBRL.from_filing(filing)

# Create Statements object for easy access
statements = Statements(xbrl)

# Display available statements
print(statements)

# Easy access to common statements
balance_sheet = statements.balance_sheet()
income_statement = statements.income_statement()
cash_flow = statements.cash_flow_statement()

# Convert to DataFrame
income_statement_df = statements.to_dataframe("IncomeStatement")
```