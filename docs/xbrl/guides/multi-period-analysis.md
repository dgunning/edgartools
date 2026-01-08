# Multi-Period Financial Analysis with XBRLS

## Overview

Multi-period financial analysis allows you to compare a company's performance across multiple years or quarters. The `XBRLS` class in edgartools makes this easy by automatically stitching together financial statements from multiple SEC filings.

### Why Use Multi-Period Analysis?

Financial analysts need to see trends over time:
- **Revenue growth** over 3-5 years
- **Margin expansion or compression**
- **Balance sheet evolution**
- **Cash flow patterns**

### When to Use XBRLS vs Single XBRL

| Use Case | Tool | Why |
|----------|------|-----|
| Analyze current quarter | `XBRL.from_filing()` | One filing, faster |
| Compare 2+ periods | `XBRLS.from_filings()` | Multi-filing stitching |
| Historical trends (3-5 years) | `XBRLS.from_filings()` | Handles concept changes |
| Quick annual comparison | `Company.income_statement()` | EntityFacts API (simpler) |

**Key Difference**: XBRLS works with individual filings and stitches them together, preserving the original XBRL structure. The Company API uses the EntityFacts API, which is pre-aggregated by the SEC but may have different period selections.

## Quick Example

Here's how to analyze Apple's revenue trend over 3 years:

```python
from edgar import Company
from edgar.xbrl import XBRLS

# Get the last 3 annual filings
company = Company("AAPL")
filings = company.get_filings(form="10-K").head(3)

# Create XBRLS object (automatically stitches statements)
xbrls = XBRLS.from_filings(filings)

# Access stitched income statement
income = xbrls.statements.income_statement()
print(income)

# Or convert to DataFrame for analysis
df = income.to_dataframe()
print(df[['Revenue']])
```

This automatically:
- Parses XBRL from all 3 filings
- Aligns periods correctly
- Handles concept name changes between years
- Creates a unified view

## Getting Started with XBRLS

### Creating an XBRLS Object

There are two ways to create an XBRLS object:

**Method 1: From Filings (Recommended)**

```python
from edgar import Company
from edgar.xbrl import XBRLS

# Get multiple filings
company = Company("MSFT")
filings = company.get_filings(form="10-K").latest(3)

# Create XBRLS
xbrls = XBRLS.from_filings(filings)
```

**Method 2: From XBRL Objects**

```python
from edgar.xbrl import XBRL, XBRLS

# If you already have XBRL objects
xbrl_list = [XBRL.from_filing(f) for f in filings]
xbrls = XBRLS.from_xbrl_objects(xbrl_list)
```

### Understanding What XBRLS Does

When you create an XBRLS object, it:

1. **Collects all periods** from each filing
2. **Identifies optimal periods** (e.g., fiscal year-ends)
3. **Normalizes concept names** (e.g., "Total Revenue" vs "Net Sales")
4. **Aligns values** across periods
5. **Fills gaps** when a line item appears in some years but not others

## Accessing Stitched Statements

The `statements` property provides a simple interface to all statement types:

```python
# Get stitched statements
balance_sheet = xbrls.statements.balance_sheet()
income_statement = xbrls.statements.income_statement()
cash_flow = xbrls.statements.cash_flow_statement()

# Print statements (uses rich formatting)
print(balance_sheet)
print(income_statement)
```

**Available statement methods:**
- `balance_sheet()` - Assets, Liabilities, Equity
- `income_statement()` - Revenue, Expenses, Net Income
- `cash_flow_statement()` - Operating, Investing, Financing Cash Flows
- `statement_of_equity()` - Changes in shareholders' equity
- `comprehensive_income()` - Other comprehensive income items

### How Stitching Works Conceptually

Think of stitching as creating a unified view across filings:

```
Filing 1 (2024 10-K)        Filing 2 (2023 10-K)        Filing 3 (2022 10-K)
------------------          ------------------          ------------------
Revenue: $100M (2024)       Revenue: $85M (2023)        Net Sales: $70M (2022)
  COGS: $60M                  COGS: $50M                  COGS: $42M
------------------          ------------------          ------------------

                    XBRLS Stitching Process
                    ↓
        Unified Statement (Most Recent → Oldest)
        ----------------------------------------
        Revenue: $100M (2024) | $85M (2023) | $70M (2022)
          COGS: $60M          | $50M        | $42M
```

Notice:
- "Net Sales" in 2022 was recognized as "Revenue" (concept normalization)
- Periods are aligned by fiscal year-end
- Labels use the most recent terminology

## Working with Multi-Period DataFrames

### Converting to DataFrame

DataFrames are ideal for quantitative analysis:

```python
# Get income statement as DataFrame
df = income.to_dataframe()

# DataFrame structure:
# - Rows: Financial line items (Revenue, Cost of Goods Sold, etc.)
# - Columns: Time periods (2024, 2023, 2022)
# - Index: Concept names

print(df.head())
```

**Example output:**

```
                                    2024-09-28  2023-09-30  2022-09-24
Revenue                             391035000   383285000   394328000
Cost of Goods Sold                  210352000   214137000   223546000
Gross Profit                        180683000   169148000   170782000
Operating Expenses                   55013000    51345000    51345000
Operating Income                    125670000   117803000   119437000
```

### Understanding Column Structure

Period columns use fiscal year-end dates:

```python
# Examine available periods
print(df.columns.tolist())
# ['2024-09-28', '2023-09-30', '2022-09-24']

# Access specific period
revenue_2024 = df.loc['Revenue', '2024-09-28']

# Access all periods for a line item
revenue_trend = df.loc['Revenue']
print(revenue_trend)
```

### Working with Dimensions

By default, XBRLS excludes dimensional (segment) data for cleaner consolidated statements. To include segments:

```python
# Include dimensional breakdown (e.g., by product line)
income = xbrls.statements.income_statement(include_dimensions=True)
df = income.to_dataframe()

# Now you'll see rows like:
# Revenue [Americas]
# Revenue [Europe]
# Revenue [Asia]
```

**When to use `include_dimensions=True`**:
- Analyzing segment performance
- Geographic breakdown
- Product line analysis

**When to use default (`include_dimensions=False`)**:
- Consolidated company-level analysis
- Trend analysis
- Comparative analysis across companies

## Period Selection

### Automatic Optimal Period Selection

By default, XBRLS selects the best periods for comparison:

```python
# Automatically selects 3 annual periods
xbrls = XBRLS.from_filings(filings)  # filings = 3 annual reports
income = xbrls.statements.income_statement()

# XBRLS picks the fiscal year-end period from each filing
# For Apple: Sep 30, Sep 24, Sep 25 (Saturday year-ends)
```

**How XBRLS Selects Periods:**

1. **Identifies fiscal year-end** from each filing's document period end date
2. **Prefers annual periods** (duration > 300 days) over quarterly
3. **Sorts newest first** for trend analysis
4. **De-duplicates** periods that appear in multiple filings

### Controlling Period Count

Use `max_periods` to control how many periods appear:

```python
# Get 5 years instead of 3
filings = company.get_filings(form="10-K").head(5)
xbrls = XBRLS.from_filings(filings)

# Limit to 5 periods even if more are available
income = xbrls.statements.income_statement(max_periods=5)

# Or get all available periods
income = xbrls.statements.income_statement(max_periods=10)
```

### Quarterly Analysis

For quarterly trends, use 10-Q filings:

```python
# Get last 8 quarters
filings = company.get_filings(form="10-Q").head(8)
xbrls = XBRLS.from_filings(filings)

# Quarterly income statement
income = xbrls.statements.income_statement(max_periods=8)
print(income)
```

### Manual Period Inspection

To see what periods are available:

```python
# Get all available periods
periods = xbrls.get_periods()

for period in periods:
    print(f"Type: {period['type']}")
    print(f"Label: {period['label']}")
    if period['type'] == 'duration':
        print(f"Duration: {period['days']} days")
    print()

# Get just the end dates
end_dates = xbrls.get_period_end_dates()
print(end_dates)
# ['2024-09-28', '2023-09-30', '2022-09-24']
```

## Common Use Cases

### 1. Revenue Trend Analysis

Track revenue growth over time:

```python
from edgar import Company
from edgar.xbrl import XBRLS

company = Company("AAPL")
filings = company.get_filings(form="10-K").head(5)
xbrls = XBRLS.from_filings(filings)

# Get income statement
income = xbrls.statements.income_statement(max_periods=5)
df = income.to_dataframe()

# Extract revenue trend
revenue = df.loc['Revenue']
print(revenue)

# Calculate year-over-year growth
yoy_growth = revenue.pct_change() * 100
print("\nYear-over-Year Growth:")
print(yoy_growth)
```

### 2. Margin Analysis Over Time

Compare profitability trends:

```python
# Get income statement
df = income.to_dataframe()

# Calculate gross margin for each period
revenue = df.loc['Revenue']
gross_profit = df.loc['Gross Profit']
gross_margin = (gross_profit / revenue) * 100

print("Gross Margin Trend:")
print(gross_margin)

# Operating margin
operating_income = df.loc['Operating Income']
operating_margin = (operating_income / revenue) * 100

print("\nOperating Margin Trend:")
print(operating_margin)
```

### 3. Balance Sheet Evolution

Track how balance sheet composition changes:

```python
# Get balance sheet
balance = xbrls.statements.balance_sheet(max_periods=5)
df = balance.to_dataframe()

# Asset composition
total_assets = df.loc['Assets']
cash = df.loc['Cash and Cash Equivalents']
cash_ratio = (cash / total_assets) * 100

print("Cash as % of Total Assets:")
print(cash_ratio)

# Leverage analysis
total_liabilities = df.loc['Liabilities']
equity = df.loc['Stockholders Equity']
debt_to_equity = total_liabilities / equity

print("\nDebt-to-Equity Ratio:")
print(debt_to_equity)
```

### 4. Cash Flow Pattern Analysis

Understand cash generation and usage:

```python
# Get cash flow statement
cash_flow = xbrls.statements.cash_flow_statement(max_periods=5)
df = cash_flow.to_dataframe()

# Operating cash flow trend
operating_cf = df.loc['Net Cash Provided by Operating Activities']
print("Operating Cash Flow:")
print(operating_cf)

# Free cash flow (Operating CF - Capex)
capex = df.loc['Capital Expenditures']
free_cash_flow = operating_cf + capex  # capex is negative
print("\nFree Cash Flow:")
print(free_cash_flow)

# Cash conversion ratio
net_income = income.to_dataframe().loc['Net Income']
cash_conversion = (operating_cf / net_income) * 100
print("\nCash Conversion (Operating CF / Net Income):")
print(cash_conversion)
```

### 5. Year-over-Year Comparative Analysis

Compare specific line items across years:

```python
import pandas as pd

# Get 3 years of data
filings = company.get_filings(form="10-K").head(3)
xbrls = XBRLS.from_filings(filings)

# Create comparison DataFrame
income_df = xbrls.statements.income_statement().to_dataframe()

# Select key metrics
key_metrics = [
    'Revenue',
    'Gross Profit',
    'Operating Income',
    'Net Income'
]

comparison = income_df.loc[key_metrics]

# Add year-over-year changes
for i in range(len(comparison.columns) - 1):
    current_col = comparison.columns[i]
    prior_col = comparison.columns[i + 1]
    change_col = f"{current_col[:4]} vs {prior_col[:4]}"

    comparison[change_col] = (
        (comparison[current_col] - comparison[prior_col]) / comparison[prior_col] * 100
    )

print(comparison)
```

## Comparison: XBRLS vs Company API

Both XBRLS and the Company API can provide multi-period statements, but they serve different purposes:

### Feature Comparison

| Feature | XBRLS | Company.income_statement() |
|---------|-------|---------------------------|
| **Data Source** | Individual XBRL filings | EntityFacts API |
| **Setup Complexity** | More code | One-liner |
| **Flexibility** | High (custom periods) | Medium (predefined periods) |
| **Period Selection** | Filing-based | API-aggregated |
| **Concept Stitching** | Automatic | Pre-aggregated by SEC |
| **Speed** | Slower (parsing XBRL) | Faster (JSON API) |
| **Dimensions** | Full control | Limited access |
| **Offline Use** | Possible with caching | Requires API access |
| **Best For** | Deep analysis, custom periods | Quick lookups, standard views |

### When to Use XBRLS

Use XBRLS when you need:
- **Full control over period selection**
- **Access to filing-specific details**
- **Custom stitching logic**
- **Dimensional segment analysis**
- **To work with specific filings** (e.g., amended returns)

Example:

```python
from edgar.xbrl import XBRLS

# Full control over which filings
filings = company.get_filings(form="10-K", filing_date="2020-01-01:2024-12-31").head(4)
xbrls = XBRLS.from_filings(filings)
income = xbrls.statements.income_statement()
```

### When to Use Company API

Use Company API when you need:
- **Quick standard views**
- **Simple multi-year comparisons**
- **Less code**
- **Faster performance**

Example:

```python
from edgar import Company

# Simple and fast
company = Company("AAPL")
income = company.income_statement(period='annual', periods=5)
print(income)
```

### Hybrid Approach

You can use both for different purposes:

```python
from edgar import Company

company = Company("AAPL")

# Quick check with Company API
income_quick = company.income_statement(period='annual', periods=3)
print("Quick view:", income_quick)

# Deep dive with XBRLS
filings = company.get_filings(form="10-K").head(5)
xbrls = XBRLS.from_filings(filings)
income_detailed = xbrls.statements.income_statement(max_periods=5)
df = income_detailed.to_dataframe()

# Now do custom analysis
# ...
```

## Troubleshooting

### Missing Periods

**Problem**: Some periods are missing from stitched statements

```python
# Check available periods
periods = xbrls.get_periods()
print(f"Found {len(periods)} periods")
for p in periods:
    print(p)

# Check if filings have XBRL data
for xbrl in xbrls.xbrl_list:
    print(f"Entity: {xbrl.entity_name}")
    print(f"Period: {xbrl.period_of_report}")
    print(f"Statements: {len(xbrl.get_all_statements())}")
```

**Solutions:**
- Ensure filings have XBRL data (pre-2009 filings may not)
- Check that filings are the same form type (don't mix 10-K and 10-Q)
- Filter amendments: `filings.filter(amendments=False)`

### Stitching Errors

**Problem**: Statement fails to stitch or shows unexpected values

```python
# Check individual XBRL objects first
for xbrl in xbrls.xbrl_list:
    print(f"\n{xbrl.entity_name} - {xbrl.period_of_report}")
    try:
        stmt = xbrl.statements.income_statement()
        print(stmt)
    except Exception as e:
        print(f"Error: {e}")
```

**Common causes:**
- Company changed fiscal year-end
- Different statement structures across years
- Missing required concepts in some years

**Solution:** Use standardization (enabled by default):

```python
# Standardization normalizes concept names
income = xbrls.statements.income_statement(standard=True)

# Or disable if you want raw company labels
income = xbrls.statements.income_statement(standard=False)
```

### Concept Alignment Issues

**Problem**: Same line item appears multiple times with different names

This usually happens when standardization is disabled. Enable it:

```python
# Use standardized labels (default)
income = xbrls.statements.income_statement(standard=True)

# Check what concepts are being merged
from edgar.xbrl.standardization import ConceptMapper
mapper = ConceptMapper()

# See if concepts are recognized
print(mapper.standardize_label("Total Revenues"))
print(mapper.standardize_label("Net Sales"))
# Both should map to "Revenue"
```

### Performance Tips

**Problem**: Stitching is slow for many filings

```python
# 1. Reduce number of periods
income = xbrls.statements.income_statement(max_periods=3)  # Instead of 10

# 2. Filter amendments before creating XBRLS
filings = company.get_filings(form="10-K").filter(amendments=False).head(3)

# 3. Use caching for repeated access
# Statements are cached automatically within XBRLS object
income = xbrls.statements.income_statement()  # First call: slow
income = xbrls.statements.income_statement()  # Second call: fast (cached)

# 4. For bulk analysis, create XBRLS once and reuse
for statement_type in ['IncomeStatement', 'BalanceSheet', 'CashFlowStatement']:
    stmt = xbrls.statements[statement_type]
    # ... analyze ...
```

## Advanced Topics

### Querying Stitched Facts

For advanced analysis, you can query the underlying facts:

```python
# Query across all filings
query = xbrls.query(max_periods=5)

# Filter to specific concepts
revenue_facts = query.by_standardized_concept("Revenue").execute()

# Convert to DataFrame for analysis
df = query.to_dataframe()

# Filter to concepts across all periods
consistent_facts = query.across_periods(min_periods=5).execute()
```

### Trend Analysis

```python
# Setup trend analysis for specific concept
trend_query = xbrls.query().trend_analysis("Revenue")

# Get results sorted by period
results = trend_query.execute()

# Or get as DataFrame with periods as columns
trend_df = trend_query.to_trend_dataframe()
print(trend_df)
```

### Custom Period Selection

```python
# Get statement data with custom period control
statement_data = xbrls.get_statement(
    statement_type='IncomeStatement',
    max_periods=5,
    standard=True,
    use_optimal_periods=True
)

# Examine period structure
print(statement_data['periods'])

# Work with raw data
for item in statement_data['statement_data']:
    print(f"{item['label']}: {item['values']}")
```

## Best Practices

### 1. Always Filter Amendments

Amendments can cause duplicate periods:

```python
# GOOD
filings = company.get_filings(form="10-K").filter(amendments=False).head(5)

# AVOID
filings = company.get_filings(form="10-K").head(5)  # May include amendments
```

### 2. Use Consistent Form Types

Don't mix annual and quarterly filings:

```python
# GOOD: All 10-K
filings_annual = company.get_filings(form="10-K").head(5)

# GOOD: All 10-Q
filings_quarterly = company.get_filings(form="10-Q").head(8)

# AVOID: Mixed forms
filings_mixed = company.get_filings(form=["10-K", "10-Q"]).head(10)
```

### 3. Check Period Alignment

Always verify periods align as expected:

```python
xbrls = XBRLS.from_filings(filings)

# Check periods before analysis
end_dates = xbrls.get_period_end_dates()
print("Analyzing periods:", end_dates)

# Should be consistent fiscal year-ends
# e.g., all December 31 or all September 30
```

### 4. Handle Missing Data

Not all line items appear in all periods:

```python
df = income.to_dataframe()

# Check for missing values
print("\nMissing data by period:")
print(df.isnull().sum())

# Fill missing values if appropriate
df_filled = df.fillna(0)  # Or use forward-fill: df.ffill()
```

### 5. Validate Results

Cross-check with SEC filings:

```python
# Print statement to visually verify
print(income)

# Check against filing
filing = filings[0]
print(f"\nCompare with: {filing.filing_date}")
print(filing.homepage_url)

# Verify key metrics
df = income.to_dataframe()
revenue = df.loc['Revenue'].iloc[0]
print(f"Revenue (most recent): ${revenue:,.0f}")
```

## Related Documentation

- **[Dimension Handling](../dimension-handling.md)** - Working with segment data
- **[Standardization Concepts](../standardization-concepts.md)** - How concept normalization works
- **[XBRL Basics](../xbrl-basics.md)** - Understanding XBRL structure
- **[Company API Reference](../../api/company.md)** - Alternative approach using EntityFacts

## Summary

Multi-period analysis with XBRLS enables powerful trend analysis:

**Key Takeaways:**
- Use `XBRLS.from_filings()` to create multi-period view
- Access statements via `xbrls.statements.income_statement()`
- Convert to DataFrame with `.to_dataframe()` for analysis
- Control periods with `max_periods` parameter
- Always filter amendments for cleaner data
- Use standardization (enabled by default) for consistent labels

**Quick Reference:**

```python
from edgar import Company
from edgar.xbrl import XBRLS

# Setup
company = Company("AAPL")
filings = company.get_filings(form="10-K").filter(amendments=False).head(5)
xbrls = XBRLS.from_filings(filings)

# Access statements
income = xbrls.statements.income_statement(max_periods=5)
balance = xbrls.statements.balance_sheet(max_periods=5)
cash_flow = xbrls.statements.cash_flow_statement(max_periods=5)

# Convert to DataFrame
df = income.to_dataframe()

# Analyze
revenue_trend = df.loc['Revenue']
print(revenue_trend.pct_change() * 100)
```

For quick lookups, consider the Company API:

```python
# Simpler alternative for standard views
income = company.income_statement(period='annual', periods=5)
```

Choose XBRLS when you need full control and deep analysis. Use Company API for quick standard views.
