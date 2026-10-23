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

# DataFrame columns include:
# - concept: XBRL concept name (e.g., 'us-gaap:Assets')
# - label: Human-readable label
# - value: Fact value as text
# - numeric_value: Fact value as a number (NaN for text facts)
# - period_start, period_end: Dates of a duration fact
# - period_instant: Date of an instant fact (duration facts leave it empty)
# - unit_ref, currency: Unit of measure (e.g., 'usd', 'USD')
# - is_dimensioned: True for facts that carry a dimensional breakdown
```

## Advanced Patterns

### Finding Specific Disclosures

```python
# Get statements organized by category
categories = xbrl.statements.get_statements_by_category()

# View all disclosures
disclosures = categories['disclosure']
for disc in disclosures:
    print(f"{disc['index']}: {disc['definition']}")

# View all notes
notes = categories['note']
for note in notes:
    print(f"{note['index']}: {note['definition']}")

# Get core financial statements
core_statements = categories['statement']

# Or list all statements to find specific ones
all_statements = xbrl.get_all_statements()
for stmt in all_statements:
    print(f"{stmt['type']}: {stmt['definition']}")

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

# The period columns are the dated ones, newest first
periods = [c for c in df.columns if c[:4].isdigit()]

# Calculate year-over-year growth
if len(periods) >= 2:
    sales = df[df['label'] == 'Net sales']
    growth = ((sales[periods[0]] - sales[periods[1]]) / sales[periods[1]] * 100).round(2)
    print(f"Revenue growth: {growth.iloc[0]}%")
```

### Working with Dimensions

```python
# Query facts with specific dimensional breakdowns
# by_dimension takes the axis; filter on its member with a second argument
segment_revenue = (xbrl.facts.query()
    .by_concept('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax')
    .by_dimension('srt:ProductOrServiceAxis')
    .to_dataframe())

# The frame gains dimension, member and dim_<axis> columns.
# Sum the latest fiscal year by member; numeric_value holds numbers, value holds text.
latest = segment_revenue[segment_revenue['period_end'] == segment_revenue['period_end'].max()]
segment_totals = latest.groupby('member')['numeric_value'].sum()
```

### Custom Fact Filtering

```python
# Use custom filter function
large_amounts = xbrl.facts.query().by_value(lambda v: abs(v) > 1000000).to_dataframe()

# Custom filter with lambda: duration facts carry period_end, instant facts period_instant
recent_facts = xbrl.facts.query().by_custom(
    lambda fact: (fact.get('period_end') or fact.get('period_instant') or '') >= '2022-01-01'
).to_dataframe()
```

## Common Workflows

### Extract Revenue from Income Statement

```python
# Method 1: Via statement
income = xbrl.statements.income_statement()
df = income.to_dataframe()
revenue = df[df['label'] == 'Net sales']   # one row; the period columns hold the amounts

# Method 2: Via facts query (use the concept the filer tagged, with its prefix)
revenue_facts = (xbrl.facts.query()
    .by_concept('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax', exact=True)
    .to_dataframe())
totals = revenue_facts[~revenue_facts['is_dimensioned']].sort_values('period_end', ascending=False)
latest_revenue = totals.iloc[0]['numeric_value']
```

### Compare Current vs Prior Year

```python
# Get current period data
current = xbrl.current_period
current_df = current.income_statement(as_statement=False)

# Get full multi-period data
full_income = xbrl.statements.income_statement()
full_df = full_income.to_dataframe()

# Compare the dated period columns, newest first
periods = [c for c in full_df.columns if c[:4].isdigit()]
if len(periods) >= 2:
    amounts = full_df.set_index('label')[periods[:2]]
    comparison = pd.DataFrame({
        'Current': amounts.iloc[:, 0],
        'Prior': amounts.iloc[:, 1],
        'Change': amounts.iloc[:, 0] - amounts.iloc[:, 1]
    })
    print(comparison)
```

### Extract Specific Disclosure Data

```python
# Find debt-related disclosures
all_statements = xbrl.get_all_statements()
debt_statements = [s for s in all_statements if 'debt' in s['definition'].lower()]

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
def latest(statement, label):
    """Most recent value of the line item with this label (the company's own label)."""
    df = statement.to_dataframe()
    period = next(c for c in df.columns if c[:4].isdigit())
    return df.loc[df['label'] == label, period].iloc[0]

metrics = {}

# Revenue and profit from income statement
income = xbrl.statements.income_statement()
metrics['Revenue'] = latest(income, 'Net sales')
metrics['Net Income'] = latest(income, 'Net income')

# Assets from balance sheet
balance = xbrl.statements.balance_sheet()
metrics['Total Assets'] = latest(balance, 'Total assets')

# Cash flow from operations
cashflow = xbrl.statements.cash_flow_statement()
metrics['Operating Cash Flow'] = latest(cashflow, 'Cash generated by operating activities')

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
print(f"Ticker: {entity_info.get('ticker')}")
print(f"CIK: {entity_info.get('identifier')}")
print(f"Form: {entity_info.get('document_type')}")
print(f"Fiscal Year: {entity_info.get('fiscal_year')}")
print(f"Fiscal Period: {entity_info.get('fiscal_period')}")
```

## Error Handling

### Missing Statements

```python
from edgar.exceptions import StatementNotFoundError

try:
    equity = xbrl.statements.statement_of_equity()
except StatementNotFoundError:
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
revenue = all_facts[all_facts['concept'].str.contains('Revenue')]
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

- `concept`: XBRL element name with its prefix (e.g., 'us-gaap:Assets')
- `label`: Human-readable label
- `value`: Fact value as text
- `numeric_value`: Fact value as a number (NaN for text facts)
- `period_key`: Period identifier (e.g., 'duration_2022-09-25_2023-09-30')
- `period_start`, `period_end`: Dates of a duration fact
- `period_instant`: Date of an instant fact
- `unit_ref`: The filing's unit id (e.g., 'usd', 'shares'); `currency` holds 'USD' when it is a currency
- `is_dimensioned`: True when the fact has a dimensional breakdown
- `decimals`: Precision indicator

Queries filtered with `by_dimension()` add `dimension`, `member` and one `dim_<axis>` column per axis.

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
filings = company.get_filings(form="10-Q").head(4)

revenue_trend = []
for filing in filings:
    xbrl = filing.xbrl()
    revenue = (xbrl.facts.query()
        .by_concept('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax', exact=True)
        .to_dataframe())
    revenue = revenue[~revenue['is_dimensioned']]
    if not revenue.empty:
        revenue_trend.append({
            'filing_date': filing.filing_date,
            'revenue': revenue.iloc[0]['numeric_value']
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
       stmt = xbrl.statements.statement_of_equity()
   except StatementNotFoundError:
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
