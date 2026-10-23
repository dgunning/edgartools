# Statement Class Documentation

## Overview

The `Statement` class represents a single financial statement extracted from XBRL data. It provides methods for viewing, manipulating, and analyzing financial statement data including income statements, balance sheets, cash flow statements, and disclosure notes.

A Statement object contains:
- **Line items** with values across multiple periods
- **Hierarchy** showing the structure and relationships
- **Metadata** including concept names and labels
- **Period information** for time-series analysis

## Getting a Statement

### From XBRL

```python
# Get XBRL data first
xbrl = filing.xbrl()

# Access specific statements
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()
cashflow = xbrl.statements.cash_flow_statement()
equity = xbrl.statements.statement_of_equity()

# By name
cover_page = xbrl.statements['CoverPage']

# By index
first_statement = xbrl.statements[0]
```

## Viewing Statements

### Rich Display

```python
# Print statement to see formatted table
print(income)

# Shows:
# - Statement title
# - Line items with hierarchical structure
# - Values for multiple periods
# - Proper number formatting
```

### Text Representation

```python
# Get plain text version
text = str(income)

# Or explicitly
text_output = income.text()
```

## Converting to DataFrame

### Basic Conversion

```python
# Convert statement to pandas DataFrame
df = income.to_dataframe()

# DataFrame structure:
# - Index: a plain RangeIndex (0, 1, 2, ...), one row per line item
# - Columns: concept, label, standard_concept, then one column per period
#   (such as '2023-09-30 (FY)'), then display metadata (level, abstract,
#   dimension, balance, ...)
# - Values: financial amounts in the period columns, text in the others
```

The period columns are the ones that start with a year. Most examples below work on `amounts()`, a label-indexed frame of just the periods, newest first:

```python
def amounts(statement, **kwargs):
    """Label-indexed frame holding only the period columns of a statement."""
    df = statement.to_dataframe(**kwargs)
    periods = [c for c in df.columns if c[:4].isdigit()]
    table = df.set_index("label")[periods]
    # A label can repeat (Apple lists "Marketable securities" under current and
    # non-current assets); keep the first row, which is the one listed first.
    return table[~table.index.duplicated(keep="first")]

df = amounts(income)
df.loc["Net sales"]    # that line item across periods (labels are the company's own)
df.columns.tolist()    # ['2023-09-30 (FY)', '2022-09-24 (FY)', '2021-09-25 (FY)']
```

### With Period Filter

`period_filter` takes a period key, not a year: `duration_START_END` for flow statements and `instant_DATE` for balance sheets. The keys are listed in `xbrl.reporting_periods`.

```python
# Keep one fiscal year of the income statement
df = income.to_dataframe(period_filter='duration_2022-09-25_2023-09-30')
# Only the '2023-09-30 (FY)' period column remains

# Keep one balance sheet date
df = balance.to_dataframe(period_filter='instant_2023-09-30')
```

A key that matches nothing, such as `'2023'`, returns an empty frame.

### Accessing Specific Data

```python
# Label-indexed frame of the period columns (see amounts() above)
df = amounts(income)

# Access specific line items
revenue = df.loc['Net sales']
net_income = df.loc['Net income']

# Access specific periods
current_period = df.iloc[:, 0]  # First period column (most recent)
prior_period = df.iloc[:, 1]    # Second period column
current_period = df['2023-09-30 (FY)']  # Or by its header

# Specific cell
current_revenue = df.loc['Net sales', df.columns[0]]
```

To find a line item whatever the company calls it, use `standard_concept` on the full frame:

```python
full = income.to_dataframe()
periods = [c for c in full.columns if c[:4].isdigit()]
revenue = full.loc[full['standard_concept'] == 'Revenue', periods[0]].iloc[0]
```

## Statement Properties

### Available Periods

```python
# The periods are the dated columns of the DataFrame
df = statement.to_dataframe()
periods = [c for c in df.columns if c[:4].isdigit()]

# Each period column is headed by its end date, e.g. '2023-09-30 (FY)'
for period in periods:
    print(f"Data available for: {period}")
```

### Statement Name and Type

```python
# Get statement information
concept = statement.primary_concept   # XBRL concept identifier, e.g. 'us-gaap_IncomeStatementAbstract'
role = statement.role_or_type         # Role URI, e.g. 'http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFOPERATIONS'
```

### Raw Data Access

```python
# Get underlying statement data structure
raw_data = statement.get_raw_data()

# Returns list of dictionaries with:
# - concept: XBRL concept name
# - label: Display label
# - values: Dict of period -> value
# - level: Hierarchy depth
# - all_names: All concept variations
```

## Rendering and Display

### Custom Rendering

```python
# Render with specific options
rendered = statement.render()

# Rendered statement has rich formatting
print(rendered)
```

### Text Export

```python
# Get markdown-formatted text
markdown_text = statement.text()

# Suitable for:
# - AI/LLM consumption
# - Documentation
# - Text-based analysis
```

## Working with Statement Data

### Calculate Growth Rates

```python
# Label-indexed frame of the period columns
df = amounts(income)

# Calculate period-over-period growth
if len(df.columns) >= 2:
    current = df.iloc[:, 0]
    prior = df.iloc[:, 1]

    # Growth rate
    growth = ((current - prior) / prior * 100).round(2)

    # Create comparison DataFrame
    comparison = pd.DataFrame({
        'Current': current,
        'Prior': prior,
        'Growth %': growth
    })

    print(comparison)
```

### Extract Specific Metrics

```python
# Get income statement metrics
df = amounts(income)

# Extract key metrics from most recent period
current = df.iloc[:, 0]

metrics = {
    'Revenue': current.get('Net sales', 0),
    'Operating Income': current.get('Operating income', 0),
    'Net Income': current.get('Net income', 0),
}

# Calculate derived metrics
if metrics['Revenue'] > 0:
    metrics['Operating Margin'] = (
        metrics['Operating Income'] / metrics['Revenue'] * 100
    )
    metrics['Net Margin'] = (
        metrics['Net Income'] / metrics['Revenue'] * 100
    )
```

### Filter Line Items

```python
# Label-indexed frame of the period columns
df = amounts(balance)

# Filter for specific items
asset_items = df[df.index.str.contains('Asset', case=False)]
liability_items = df[df.index.str.contains('Liabilit', case=False)]

# Get subtotals
if 'Total current assets' in df.index:
    current_assets = df.loc['Total current assets']
```

### Time Series Analysis

```python
# Get multiple periods
df = amounts(income)

# Plot revenue trend
if 'Net sales' in df.index:
    revenue_series = df.loc['Net sales']

    # Oldest period first, then plot
    import matplotlib.pyplot as plt
    revenue_series[::-1].plot(kind='line', title='Revenue Trend')
    plt.show()
```

## Common Workflows

### Compare Current vs Prior Period

```python
# Get income statement
income = xbrl.statements.income_statement()
df = amounts(income)

# Ensure we have at least 2 periods
if len(df.columns) >= 2:
    # Create comparison
    comparison = pd.DataFrame({
        'Current': df.iloc[:, 0],
        'Prior': df.iloc[:, 1],
        'Change': df.iloc[:, 0] - df.iloc[:, 1],
        'Change %': ((df.iloc[:, 0] - df.iloc[:, 1]) / df.iloc[:, 1] * 100).round(2)
    })

    # Show key metrics
    key_items = ['Net sales', 'Operating income', 'Net income']
    for item in key_items:
        if item in comparison.index:
            print(f"\n{item}:")
            print(comparison.loc[item])
```

### Extract All Periods to CSV

```python
# Get statement
statement = xbrl.statements.income_statement()

# Convert and save
df = amounts(statement)
df.to_csv('income_statement.csv')

print(f"Exported {len(df)} line items across {len(df.columns)} periods")
```

### Build Financial Ratios

```python
# Get both income statement and balance sheet
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()

# Label-indexed frames of the period columns
income_df = amounts(income)
balance_df = amounts(balance)

# Extract values (most recent period)
revenue = income_df.loc['Net sales', income_df.columns[0]]
net_income = income_df.loc['Net income', income_df.columns[0]]
total_assets = balance_df.loc['Total assets', balance_df.columns[0]]
total_equity = balance_df.loc['Total shareholders’ equity', balance_df.columns[0]]

# Calculate ratios
ratios = {
    'Net Profit Margin': (net_income / revenue * 100).round(2),
    'ROA': (net_income / total_assets * 100).round(2),
    'ROE': (net_income / total_equity * 100).round(2),
    'Asset Turnover': (revenue / total_assets).round(2),
}

print("Financial Ratios:")
for ratio, value in ratios.items():
    print(f"  {ratio}: {value}")
```

### Search for Specific Items

```python
# Get statement as a label-indexed DataFrame
df = amounts(income)

# Search for items containing keywords
research_costs = df[df.index.str.contains('Research', case=False)]
tax_items = df[df.index.str.contains('Tax', case=False)]

# Or get raw data with concept names
raw = income.get_raw_data()
research_concepts = [
    item for item in raw
    if 'research' in item['label'].lower()
]
```

### Aggregate Subcategories

```python
# Get statement
df = amounts(balance)

# Define categories (adjust based on actual labels)
current_asset_categories = [
    'Cash and cash equivalents',
    'Marketable securities',
    'Accounts receivable, net',
    'Vendor non-trade receivables',
    'Inventories',
    'Other current assets'
]

# Sum categories
current_assets_sum = sum([
    df.loc[cat, df.columns[0]]
    for cat in current_asset_categories
    if cat in df.index
])

# Verify against reported total
if 'Total current assets' in df.index:
    reported_total = df.loc['Total current assets', df.columns[0]]
    print(f"Calculated: {current_assets_sum}")
    print(f"Reported: {reported_total}")
    print(f"Difference: {current_assets_sum - reported_total}")
```

## Integration with Analysis Tools

### With Pandas

```python
# Statement integrates seamlessly with pandas
df = amounts(statement)

# Use all pandas functionality
summary = df.describe()
correlations = df.T.corr()
rolling_avg = df.T.rolling(window=4).mean()
```

### With NumPy

```python
import numpy as np

# Convert to numpy array for numerical operations
df = amounts(statement)
values = df.dropna().to_numpy(dtype=float)

# Numerical analysis
mean_values = np.mean(values, axis=1)
std_values = np.std(values, axis=1)
growth_rates = np.diff(values, axis=1) / values[:, :-1]
```

### Export for Visualization

```python
# Prepare data for plotting
df = amounts(income)

# Select key items
plot_items = ['Net sales', 'Operating income', 'Net income']
plot_data = df.loc[plot_items].T

# Plot with matplotlib
import matplotlib.pyplot as plt
plot_data.plot(kind='bar', figsize=(12, 6))
plt.title('Income Statement Trends')
plt.xlabel('Period')
plt.ylabel('Amount (USD)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

## Error Handling

### Missing Line Items

```python
# Check if item exists before accessing
df = amounts(statement)

if 'Revenue' in df.index:
    revenue = df.loc['Revenue']
else:
    print("Revenue not found in statement")
    # Try alternative names
    for alt in ['Revenues', 'Total Revenue', 'Net sales']:
        if alt in df.index:
            revenue = df.loc[alt]
            break
```

### Handling Different Formats

```python
# Companies may use different labels
def find_item(df, possible_names):
    """Find item by trying multiple possible names."""
    for name in possible_names:
        if name in df.index:
            return df.loc[name]
    return None

# Usage
revenue_names = ['Revenue', 'Revenues', 'Total Revenue', 'Net sales']
revenue = find_item(df, revenue_names)

if revenue is not None:
    print(f"Found revenue: {revenue}")
else:
    print("Revenue not found under common names")
```

### Incomplete Period Data

```python
# Check data availability
df = amounts(statement)

# Check for null values
missing_data = df.isnull().sum()
if missing_data.any():
    print("Periods with missing data:")
    print(missing_data[missing_data > 0])

# Fill missing with 0 or forward fill
df_filled = df.fillna(0)  # Replace NaN with 0
# or
df_filled = df.ffill()  # Forward fill
```

## Best Practices

1. **Always convert to DataFrame for analysis**:
   ```python
   df = amounts(statement)  # Label-indexed, period columns only
   ```

2. **Check item names before accessing**:
   ```python
   if 'Revenue' in df.index:
       revenue = df.loc['Revenue']
   ```

3. **Handle multiple naming conventions**:
   ```python
   # Try variations
   for name in ['Revenue', 'Revenues', 'Total Revenue']:
       if name in df.index:
           revenue = df.loc[name]
           break
   ```

4. **Validate calculated values**:
   ```python
   # Check against reported totals (current period)
   df = amounts(income)
   calculated = df.loc[['Products', 'Services']].iloc[:, 0].sum()
   reported = df.loc['Net sales'].iloc[0]
   assert abs(calculated - reported) < 0.01, "Mismatch!"
   ```

5. **Use period filters appropriately**:
   ```python
   # Filter to one fiscal year (a period key, not a bare year)
   df_fy = statement.to_dataframe(period_filter='duration_2022-09-25_2023-09-30')
   ```

## Performance Tips

### Caching DataFrames

```python
# Cache the DataFrame if using repeatedly
df_cache = amounts(statement)

# Reuse cached version
revenue = df_cache.loc['Net sales']
net_income = df_cache.loc['Net income']
# ... more operations
```

### Selective Period Loading

```python
# If you only need one period, filter to its key
df = amounts(income, period_filter='duration_2022-09-25_2023-09-30')  # Smaller, faster
```

## Troubleshooting

### "KeyError: Line item not found"

**Cause**: Item label doesn't match exactly

**Solution**:
```python
# List all available items
print(df.index.tolist())

# Or search for pattern
matching = df[df.index.str.contains('keyword', case=False)]
```

### "Empty DataFrame"

**Cause**: Statement has no data or wrong period filter

**Solution**:
```python
# Check raw data
raw = statement.get_raw_data()
print(f"Statement has {len(raw)} items")

# Check periods (the dated columns)
print(f"Available periods: {[c for c in statement.to_dataframe().columns if c[:4].isdigit()]}")
```

### "Index error when accessing columns"

**Cause**: Fewer periods than expected

**Solution**:
```python
# Check column count first
if len(df.columns) >= 2:
    current = df.iloc[:, 0]
    prior = df.iloc[:, 1]
else:
    print("Insufficient periods for comparison")
```

This guide covers the essential patterns for working with Statement objects in edgartools. For information on accessing statements from XBRL, see the XBRL documentation.
