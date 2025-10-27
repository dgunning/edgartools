# XBRL Class Documentation

## Overview

The `XBRL` class is the primary interface for working with XBRL (eXtensible Business Reporting Language) financial data from SEC filings. It provides structured access to financial statements, facts, and related data extracted from filings like 10-K, 10-Q, and 8-K reports.

XBRL documents contain:
- **Financial statements** (Income Statement, Balance Sheet, Cash Flow, etc.)
- **Facts** - Individual data points with values, periods, and dimensions
- **Contexts** - Time periods and dimensional information
- **Presentation** - How facts are organized into statements

## Getting XBRL Data

### From a Filing

```python
# Get XBRL from any filing with financial data
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()
```

### Quick Check

```python
# Print XBRL to see what's available
print(xbrl)
# Shows: company info, available statements, periods, and usage examples
```

## Accessing Financial Statements

### Core Statement Methods

The XBRL class provides convenient methods for accessing standard financial statements:

```python
# Access core financial statements
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()
cashflow = xbrl.statements.cash_flow_statement()
equity = xbrl.statements.statement_of_equity()
comprehensive = xbrl.statements.comprehensive_income()
```

### Access by Name

You can access any statement by its exact name as it appears in the filing:

```python
# List all available statements
print(xbrl.statements)

# Access specific statement by name
cover_page = xbrl.statements['CoverPage']
disclosure = xbrl.statements['CONDENSED CONSOLIDATED BALANCE SHEETS Unaudited']
```

### Access by Index

Statements can also be accessed by their index position:

```python
# Get statement by index (0-based)
first_statement = xbrl.statements[0]
sixth_statement = xbrl.statements[6]
```

## Working with Periods

### Current Period Only

To work with just the most recent period's data:

```python
# Get current period XBRL view
current = xbrl.current_period

# Access statements for current period
current_income = current.income_statement()
current_balance = current.balance_sheet()
```

### Multi-Period Statements

By default, statements include multiple periods for comparison:

```python
# Get income statement with comparative periods
income = xbrl.statements.income_statement()
# Typically includes current year/quarter and prior periods

# Convert to DataFrame to see all periods
df = income.to_dataframe()
print(df.columns)  # Shows all available periods
```

### Available Periods

```python
# See what periods are available
for period in xbrl.reporting_periods:
    print(f"Period: {period['label']}, Key: {period['key']}")
```

## Querying Facts

The `.facts` property provides a powerful query interface for finding specific data points:

### Basic Fact Queries

```python
# Get all revenue facts
revenue_facts = xbrl.facts.query().by_concept('Revenue').to_dataframe()

# Get net income facts
net_income = xbrl.facts.query().by_concept('NetIncome').to_dataframe()

# Search by label instead of concept name
revenue = xbrl.facts.query().by_label('Revenue').to_dataframe()
```

### Filter by Period

```python
# Get facts for a specific period
period_key = "duration_2024-01-01_2024-12-31"
facts_2024 = xbrl.facts.query().by_period_key(period_key).to_dataframe()

# Filter by fiscal year
facts_fy2024 = xbrl.facts.query().by_fiscal_year(2024).to_dataframe()

# Filter by fiscal period
q1_facts = xbrl.facts.query().by_fiscal_period("Q1").to_dataframe()
```

### Filter by Statement Type

```python
# Get all income statement facts
income_facts = xbrl.facts.query().by_statement_type("IncomeStatement").to_dataframe()

# Get all balance sheet facts
balance_facts = xbrl.facts.query().by_statement_type("BalanceSheet").to_dataframe()
```

### Chaining Filters

```python
# Combine multiple filters
revenue_2024 = (xbrl.facts.query()
    .by_concept('Revenue')
    .by_fiscal_year(2024)
    .by_period_type('duration')
    .to_dataframe())
```

### Pattern Matching

```python
# Find all concepts matching a pattern (case-insensitive)
asset_facts = xbrl.facts.query().by_concept('Asset', exact=False).to_dataframe()

# Search labels with pattern
liability_facts = xbrl.facts.query().by_label('liabilities', exact=False).to_dataframe()
```

## Converting to DataFrames

### Statement to DataFrame

```python
# Convert any statement to pandas DataFrame
income = xbrl.statements.income_statement()
df = income.to_dataframe()

# DataFrame has:
# - One row per line item
# - One column per period
# - Index is the concept/label
```

### Facts to DataFrame

```python
# Query returns DataFrame directly
df = xbrl.facts.query().by_concept('Revenue').to_dataframe()

# DataFrame columns:
# - concept: XBRL concept name
# - label: Human-readable label
# - value: Fact value
# - period: Period identifier
# - start: Period start date (for duration)
# - end: Period end date
# - unit: Unit of measure (e.g., USD)
# - dimensions: Dimensional breakdowns (if any)
```

## Advanced Patterns

### Finding Specific Disclosures

```python
# Get statements organized by category
categories = xbrl.statements.get_statements_by_category()

# View all disclosures
disclosures = categories['disclosure']
for disc in disclosures:
    print(f"{disc['index']}: {disc['title']}")

# View all notes
notes = categories['note']
for note in notes:
    print(f"{note['index']}: {note['title']}")

# Get core financial statements
core_statements = categories['statement']

# Or list all statements to find specific ones
all_statements = xbrl.get_all_statements()
for stmt in all_statements:
    print(f"{stmt['type']}: {stmt['title']}")

# Access by exact name or index
risk_factors = xbrl.statements['RiskFactorsDisclosure']
# Or by index from the category list
first_disclosure = xbrl.statements[disclosures[0]['index']]
```

### Cross-Period Analysis

```python
# Get multi-period income statement
income = xbrl.statements.income_statement()
df = income.to_dataframe()

# Calculate year-over-year growth
if len(df.columns) >= 2:
    current = df.iloc[:, 0]
    prior = df.iloc[:, 1]
    growth = ((current - prior) / prior * 100).round(2)
    print(f"Revenue growth: {growth.loc['Revenue']}%")
```

### Working with Dimensions

```python
# Query facts with specific dimensional breakdowns
segment_revenue = (xbrl.facts.query()
    .by_concept('Revenue')
    .by_dimension('Segment', 'ProductSegment')
    .to_dataframe())

# Group by dimensions
segment_totals = segment_revenue.groupby('dimensions')['value'].sum()
```

### Custom Fact Filtering

```python
# Use custom filter function
large_amounts = xbrl.facts.query().by_value(lambda v: abs(v) > 1000000).to_dataframe()

# Custom filter with lambda
recent_facts = xbrl.facts.query().by_custom(
    lambda fact: fact['end'] >= '2024-01-01'
).to_dataframe()
```

## Common Workflows

### Extract Revenue from Income Statement

```python
# Method 1: Via statement
income = xbrl.statements.income_statement()
df = income.to_dataframe()
revenue = df.loc['Revenue']

# Method 2: Via facts query
revenue_facts = xbrl.facts.query().by_concept('Revenues').to_dataframe()
latest_revenue = revenue_facts.iloc[0]['value']
```

### Compare Current vs Prior Year

```python
# Get current period data
current = xbrl.current_period
current_income = current.income_statement()
current_df = current_income.to_dataframe()

# Get full multi-period data
full_income = xbrl.statements.income_statement()
full_df = full_income.to_dataframe()

# Compare
if len(full_df.columns) >= 2:
    comparison = pd.DataFrame({
        'Current': full_df.iloc[:, 0],
        'Prior': full_df.iloc[:, 1],
        'Change': full_df.iloc[:, 0] - full_df.iloc[:, 1]
    })
    print(comparison)
```

### Extract Specific Disclosure Data

```python
# Find debt-related disclosures
all_statements = xbrl.get_all_statements()
debt_statements = [s for s in all_statements if 'debt' in s['title'].lower()]

# Access first debt disclosure
if debt_statements:
    debt_disclosure = xbrl.statements[debt_statements[0]['type']]
    debt_df = debt_disclosure.to_dataframe()
```

### Export All Core Statements

```python
# Export all core financial statements to CSV
statements_to_export = {
    'income_statement': xbrl.statements.income_statement(),
    'balance_sheet': xbrl.statements.balance_sheet(),
    'cash_flow': xbrl.statements.cash_flow_statement(),
}

for name, stmt in statements_to_export.items():
    if stmt:
        df = stmt.to_dataframe()
        df.to_csv(f"{name}.csv")
```

### Build Custom Financial Summary

```python
# Extract key metrics from multiple statements
metrics = {}

# Revenue and profit from income statement
income = xbrl.statements.income_statement()
income_df = income.to_dataframe()
metrics['Revenue'] = income_df.loc['Revenue', income_df.columns[0]]
metrics['Net Income'] = income_df.loc['Net Income', income_df.columns[0]]

# Assets from balance sheet
balance = xbrl.statements.balance_sheet()
balance_df = balance.to_dataframe()
metrics['Total Assets'] = balance_df.loc['Assets', balance_df.columns[0]]

# Cash flow from operations
cashflow = xbrl.statements.cash_flow_statement()
cashflow_df = cashflow.to_dataframe()
metrics['Operating Cash Flow'] = cashflow_df.loc['Operating Activities', cashflow_df.columns[0]]

# Create summary DataFrame
summary = pd.DataFrame([metrics])
print(summary)
```

## Entity Information

### Access Filing Metadata

```python
# Get entity and filing information
entity_info = xbrl.entity_info

print(f"Company: {entity_info.get('entity_name')}")
print(f"Ticker: {entity_info.get('trading_symbol')}")
print(f"CIK: {entity_info.get('entity_identifier')}")
print(f"Form: {entity_info.get('document_type')}")
print(f"Fiscal Year: {entity_info.get('document_fiscal_year_focus')}")
print(f"Fiscal Period: {entity_info.get('document_fiscal_period_focus')}")
```

## Error Handling

### Missing Statements

```python
from edgar.xbrl.xbrl import StatementNotFound

try:
    equity = xbrl.statements.statement_of_equity()
except StatementNotFound:
    print("Statement of equity not available in this filing")
    equity = None
```

### Empty Query Results

```python
# Query returns empty DataFrame if no matches
results = xbrl.facts.query().by_concept('NonexistentConcept').to_dataframe()

if results.empty:
    print("No facts found matching query")
```

### Handling Multiple Formats

```python
# Some companies use different concept names
revenue_concepts = ['Revenue', 'Revenues', 'SalesRevenue', 'RevenueFromContractWithCustomer']

for concept in revenue_concepts:
    revenue = xbrl.facts.query().by_concept(concept).to_dataframe()
    if not revenue.empty:
        print(f"Found revenue under concept: {concept}")
        break
```

## Performance Considerations

### Caching

```python
# Facts are cached after first access
facts = xbrl.facts  # First call - loads data
facts2 = xbrl.facts  # Subsequent calls use cache
```

### Limiting Results

```python
# Use limit() to reduce memory usage for large result sets
sample_facts = xbrl.facts.query().limit(100).to_dataframe()
```

### Efficient Filtering

```python
# Apply specific filters early in the query chain
# Good: specific filters first
revenue = (xbrl.facts.query()
    .by_statement_type("IncomeStatement")  # Narrow down first
    .by_concept("Revenue")  # Then more specific
    .to_dataframe())

# Less efficient: broad query then filter
all_facts = xbrl.facts.query().to_dataframe()
revenue = all_facts[all_facts['concept'] == 'Revenue']
```

## Data Structure Reference

### Key Properties

| Property | Type | Description |
|----------|------|-------------|
| `statements` | Statements | Access to financial statements |
| `facts` | FactsView | Query interface for facts |
| `entity_info` | dict | Company and filing metadata |
| `reporting_periods` | list | Available time periods |
| `contexts` | dict | XBRL contexts (periods + dimensions) |
| `units` | dict | Units of measure |
| `current_period` | CurrentPeriodView | Current period only |

### Fact DataFrame Columns

When you convert facts to a DataFrame using `.to_dataframe()`, you get:

- `concept`: XBRL element name (e.g., 'Revenues', 'Assets')
- `label`: Human-readable label
- `value`: Fact value (numeric or text)
- `period`: Period identifier
- `start`: Period start date (for duration periods)
- `end`: Period end date
- `unit`: Unit of measure (e.g., 'USD', 'shares')
- `dimensions`: Dictionary of dimensional breakdowns
- `decimals`: Precision indicator

## Integration with Other Classes

### With Filing

```python
# XBRL comes from filing
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Access back to filing if needed
# (Store reference if you need it)
```

### With Company

```python
# Get multiple filings and compare XBRL data
filings = company.get_filings(form="10-Q", count=4)

revenue_trend = []
for filing in filings:
    xbrl = filing.xbrl()
    revenue = xbrl.facts.query().by_concept('Revenue').to_dataframe()
    if not revenue.empty:
        revenue_trend.append({
            'filing_date': filing.filing_date,
            'revenue': revenue.iloc[0]['value']
        })

trend_df = pd.DataFrame(revenue_trend)
```

## Best Practices

1. **Check statement availability** before accessing:
   ```python
   print(xbrl)  # See what's available
   ```

2. **Use query chaining** for complex filters:
   ```python
   results = (xbrl.facts.query()
       .by_statement_type("IncomeStatement")
       .by_fiscal_year(2024)
       .by_period_type("duration")
       .to_dataframe())
   ```

3. **Handle missing data gracefully**:
   ```python
   try:
       stmt = xbrl.statements.equity_statement()
   except StatementNotFound:
       stmt = None
   ```

4. **Convert to DataFrame for analysis**:
   ```python
   df = statement.to_dataframe()  # Easier to work with
   ```

5. **Use current_period for latest data**:
   ```python
   current = xbrl.current_period
   latest_income = current.income_statement()
   ```

## Troubleshooting

### "Statement not found"

**Cause**: Statement doesn't exist in this filing or uses non-standard name

**Solution**:
```python
# List all available statements
print(xbrl.statements)

# Or check available types
all_statements = xbrl.get_all_statements()
statement_types = [s['type'] for s in all_statements]
```

### "No facts found"

**Cause**: Concept name doesn't match or no data for period

**Solution**:
```python
# Try pattern matching
results = xbrl.facts.query().by_concept('Revenue', exact=False).to_dataframe()

# Or search by label
results = xbrl.facts.query().by_label('revenue').to_dataframe()
```

### "Empty DataFrame"

**Cause**: Period filter too restrictive or no data available

**Solution**:
```python
# Check available periods
print(xbrl.reporting_periods)

# Query without period filter
all_revenue = xbrl.facts.query().by_concept('Revenue').to_dataframe()
```

This comprehensive guide covers the essential patterns for working with XBRL data in edgartools. For more examples, see the Filing and Statement documentation.
