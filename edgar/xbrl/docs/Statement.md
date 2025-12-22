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
# - Index: Line item labels or concepts
# - Columns: Period dates
# - Values: Financial amounts
```

### With Period Filter

```python
# Filter to specific periods
df = income.to_dataframe(period_filter='2024')

# Only includes periods matching the filter
```

### Accessing Specific Data

```python
# Convert to DataFrame for easy analysis
df = income.to_dataframe()

# Access specific line items
revenue = df.loc['Revenue']
net_income = df.loc['Net Income']

# Access specific periods
current_period = df.iloc[:, 0]  # First column (most recent)
prior_period = df.iloc[:, 1]    # Second column

# Specific cell
current_revenue = df.loc['Revenue', df.columns[0]]
```

## Statement Properties

### Available Periods

```python
# Get list of periods in the statement
periods = statement.periods

# Each period is a date string (YYYY-MM-DD)
for period in periods:
    print(f"Data available for: {period}")
```

### Statement Name and Type

```python
# Get statement information
name = statement.name           # Statement display name
concept = statement.concept     # XBRL concept identifier
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
# Convert to DataFrame
df = income.to_dataframe()

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
df = income.to_dataframe()

# Extract key metrics from most recent period
current = df.iloc[:, 0]

metrics = {
    'Revenue': current.get('Revenue', 0),
    'Operating Income': current.get('Operating Income', 0),
    'Net Income': current.get('Net Income', 0),
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
# Convert to DataFrame
df = balance.to_dataframe()

# Filter for specific items
asset_items = df[df.index.str.contains('Asset', case=False)]
liability_items = df[df.index.str.contains('Liabilit', case=False)]

# Get subtotals
if 'Current Assets' in df.index:
    current_assets = df.loc['Current Assets']
```

### Time Series Analysis

```python
# Get multiple periods
df = income.to_dataframe()

# Plot revenue trend
if 'Revenue' in df.index:
    revenue_series = df.loc['Revenue']

    # Convert to numeric and plot
    import matplotlib.pyplot as plt
    revenue_series.plot(kind='line', title='Revenue Trend')
    plt.show()
```

## Common Workflows

### Compare Current vs Prior Period

```python
# Get income statement
income = xbrl.statements.income_statement()
df = income.to_dataframe()

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
    key_items = ['Revenue', 'Operating Income', 'Net Income']
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
df = statement.to_dataframe()
df.to_csv('income_statement.csv')

print(f"Exported {len(df)} line items across {len(df.columns)} periods")
```

### Build Financial Ratios

```python
# Get both income statement and balance sheet
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()

# Convert to DataFrames
income_df = income.to_dataframe()
balance_df = balance.to_dataframe()

# Extract values (most recent period)
revenue = income_df.loc['Revenue', income_df.columns[0]]
net_income = income_df.loc['Net Income', income_df.columns[0]]
total_assets = balance_df.loc['Assets', balance_df.columns[0]]
total_equity = balance_df.loc['Equity', balance_df.columns[0]]

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
# Get statement as DataFrame
df = income.to_dataframe()

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
df = balance.to_dataframe()

# Define categories (adjust based on actual labels)
current_asset_categories = [
    'Cash and Cash Equivalents',
    'Accounts Receivable',
    'Inventory',
    'Other Current Assets'
]

# Sum categories
current_assets_sum = sum([
    df.loc[cat, df.columns[0]]
    for cat in current_asset_categories
    if cat in df.index
])

# Verify against reported total
if 'Current Assets' in df.index:
    reported_total = df.loc['Current Assets', df.columns[0]]
    print(f"Calculated: {current_assets_sum}")
    print(f"Reported: {reported_total}")
    print(f"Difference: {current_assets_sum - reported_total}")
```

## Integration with Analysis Tools

### With Pandas

```python
# Statement integrates seamlessly with pandas
df = statement.to_dataframe()

# Use all pandas functionality
summary = df.describe()
correlations = df.T.corr()
rolling_avg = df.T.rolling(window=4).mean()
```

### With NumPy

```python
import numpy as np

# Convert to numpy array for numerical operations
df = statement.to_dataframe()
values = df.values

# Numerical analysis
mean_values = np.mean(values, axis=1)
std_values = np.std(values, axis=1)
growth_rates = np.diff(values, axis=1) / values[:, :-1]
```

### Export for Visualization

```python
# Prepare data for plotting
df = income.to_dataframe()

# Select key items
plot_items = ['Revenue', 'Operating Income', 'Net Income']
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
df = statement.to_dataframe()

if 'Revenue' in df.index:
    revenue = df.loc['Revenue']
else:
    print("Revenue not found in statement")
    # Try alternative names
    for alt in ['Revenues', 'Total Revenue', 'Net Revenue']:
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
revenue_names = ['Revenue', 'Revenues', 'Total Revenue', 'Net Sales']
revenue = find_item(df, revenue_names)

if revenue is not None:
    print(f"Found revenue: {revenue}")
else:
    print("Revenue not found under common names")
```

### Incomplete Period Data

```python
# Check data availability
df = statement.to_dataframe()

# Check for null values
missing_data = df.isnull().sum()
if missing_data.any():
    print("Periods with missing data:")
    print(missing_data[missing_data > 0])

# Fill missing with 0 or forward fill
df_filled = df.fillna(0)  # Replace NaN with 0
# or
df_filled = df.fillna(method='ffill')  # Forward fill
```

## Best Practices

1. **Always convert to DataFrame for analysis**:
   ```python
   df = statement.to_dataframe()  # Easier to work with
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
   # Check against reported totals
   calculated = sum(components)
   reported = df.loc['Total']
   assert abs(calculated - reported) < 0.01, "Mismatch!"
   ```

5. **Use period filters appropriately**:
   ```python
   # Filter to specific years
   df_2024 = statement.to_dataframe(period_filter='2024')
   ```

## Performance Tips

### Caching DataFrames

```python
# Cache the DataFrame if using repeatedly
df_cache = statement.to_dataframe()

# Reuse cached version
revenue = df_cache.loc['Revenue']
net_income = df_cache.loc['Net Income']
# ... more operations
```

### Selective Period Loading

```python
# If you only need recent data
current_only = xbrl.current_period.income_statement()
df = current_only.to_dataframe()  # Smaller, faster
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

# Check periods
print(f"Available periods: {statement.periods}")
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
