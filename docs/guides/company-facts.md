# Company Facts API

The Company Facts API provides comprehensive access to SEC financial data through an intuitive, AI-ready interface. Get financial statements, key metrics, and detailed company information with just a few lines of code.

## Quick Start

```python
from edgar import Company

# Get any public company
company = Company('AAPL')  # Ticker symbol
# or
company = Company(320193)  # CIK number

# Access key metrics instantly
print(f"Shares Outstanding: {company.shares_outstanding:,.0f}")
print(f"Public Float: ${company.public_float:,.0f}")

# Get financial statements
income_stmt = company.income_statement()
balance_sheet = company.balance_sheet()  
cash_flow = company.cash_flow()

print(income_stmt)  # Displays beautifully formatted statement
```

## Key Features

- **🚀 Zero Setup** - Works immediately with existing Company objects
- **💰 Full Precision** - No information loss from scaled formatting  
- **📊 Rich Display** - Professional formatting for Jupyter notebooks
- **🛡️ Error Resilient** - Graceful handling of missing data
- **🤖 AI-Ready** - Structured data perfect for analysis and LLMs

## Core Properties

### Company Metrics

Access essential company information through simple properties:

```python
company = Company('TSLA')

# Key financial metrics
print(f"Shares Outstanding: {company.shares_outstanding:,.0f}")
print(f"Public Float: ${company.public_float:,.0f}")

# Check if facts are available
if company.facts:
    print(f"Total facts available: {len(company.facts):,}")
```

**Available Properties:**
- `company.facts` - Access to the full EntityFacts object
- `company.shares_outstanding` - Number of shares outstanding
- `company.public_float` - Public float value in dollars

## Financial Statements

### Income Statement

Get income statement data with flexible period options:

```python
# Default: 4 annual periods, formatted display
income_stmt = company.income_statement()

# Get 8 quarterly periods  
quarterly = company.income_statement(periods=8, annual=False)

# Get raw DataFrame for analysis
df = company.income_statement(periods=4, as_dataframe=True)
```

### Balance Sheet

Access balance sheet data for point-in-time or trend analysis:

```python
# Multi-period balance sheet trends
balance_sheet = company.balance_sheet(periods=4)

# Point-in-time snapshot as of specific date
from datetime import date
snapshot = company.balance_sheet(as_of=date(2024, 12, 31))

# Raw data for calculations
df = company.balance_sheet(periods=3, as_dataframe=True)
```

### Cash Flow Statement

Analyze cash flow patterns across periods:

```python
# Annual cash flow trends
cash_flow = company.cash_flow(periods=5, annual=True)

# Quarterly cash flow analysis
quarterly_cf = company.cash_flow(periods=8, annual=False)
```

## Method Parameters

All financial statement methods support consistent parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `periods` | int | 4 | Number of periods to retrieve |
| `annual` | bool | True | If True, prefer annual periods; if False, get quarterly |
| `as_dataframe` | bool | False | If True, return raw DataFrame; if False, return formatted FinancialStatement |

**Special Parameters:**
- `balance_sheet()` also supports `as_of` parameter for point-in-time views

## Return Types

### FinancialStatement Objects (Default)

When `as_dataframe=False` (default), methods return `FinancialStatement` objects with:

- **Rich Display**: Professional formatting in Jupyter notebooks
- **Full Precision**: No loss of decimal precision  
- **Context Aware**: Different formatting for EPS vs Revenue vs Ratios
- **Data Access**: Use `.to_numeric()` to get underlying numbers

```python
stmt = company.income_statement()

# Display formatted (automatic in notebooks)
print(stmt)

# Access raw numbers for calculations
data = stmt.to_numeric()
revenue_growth = data.loc['Revenue'].pct_change()
```

### DataFrame Objects

When `as_dataframe=True`, methods return pandas DataFrames:

```python
df = company.income_statement(as_dataframe=True)

# Standard pandas operations
print(df.dtypes)
print(df.describe()) 
revenue_series = df.loc['Revenue']
```

## Advanced Usage

### Working with EntityFacts Directly

For advanced analysis, access the full EntityFacts object:

```python
facts = company.facts

# Query specific facts
revenue_facts = facts.query().by_concept('Revenue').execute()

# Get time series for any concept
revenue_ts = facts.time_series('Revenue', periods=20)

# Get DEI (Document and Entity Information) facts
dei_info = facts.dei_facts()
entity_summary = facts.entity_info()
```

## Advanced Querying

The Facts API includes a powerful query interface for sophisticated financial analysis. Access it through the `query()` method:

```python
facts = company.facts
query = facts.query()
```

### Basic Querying

#### Filter by Concept

```python
# Find all revenue-related facts
revenue_facts = facts.query().by_concept('Revenue').execute()

# Exact concept matching
exact_revenue = facts.query().by_concept('us-gaap:Revenue', exact=True).execute()

# Fuzzy matching (finds Revenue, Revenues, RevenueFromSales, etc.)
revenue_like = facts.query().by_concept('revenue').execute()
```

#### Filter by Time Period

```python
# Get facts from specific fiscal year
fy2024_facts = facts.query().by_fiscal_year(2024).execute()

# Get facts from specific quarter
q1_facts = facts.query().by_fiscal_period('Q1').execute()

# Get facts from date range
from datetime import date
recent_facts = facts.query().date_range(
    start=date(2023, 1, 1), 
    end=date(2024, 12, 31)
).execute()

# Get facts as of specific date (point-in-time)
snapshot_facts = facts.query().as_of(date(2024, 6, 30)).execute()
```

#### Filter by Statement Type

```python
# Income statement facts only
income_facts = facts.query().by_statement_type('IncomeStatement').execute()

# Balance sheet facts only  
balance_facts = facts.query().by_statement_type('BalanceSheet').execute()

# Cash flow facts only
cashflow_facts = facts.query().by_statement_type('CashFlow').execute()
```

#### Filter by Form Type

```python
# Only audited annual facts (10-K forms)
annual_facts = facts.query().by_form_type('10-K').execute()

# Only quarterly facts (10-Q forms)
quarterly_facts = facts.query().by_form_type('10-Q').execute()

# Multiple form types
periodic_facts = facts.query().by_form_type(['10-K', '10-Q']).execute()
```

### Advanced Filtering

#### Quality and Confidence Filters

```python
# Only high-quality, audited facts
high_quality = facts.query().high_quality_only().execute()

# Facts above confidence threshold
confident_facts = facts.query().min_confidence(0.9).execute()
```

#### Period Length Filtering

```python
# Only quarterly periods (3 months)
quarterly_only = facts.query().by_period_length(3).execute()

# Only annual periods (12 months)
annual_only = facts.query().by_period_length(12).execute()

# Only year-to-date periods (9 months)
ytd_facts = facts.query().by_period_length(9).execute()
```

#### Latest Facts

```python
# Get most recent facts by filing date
latest_facts = facts.query().by_concept('Revenue').latest(5)

# Get latest instant facts (for balance sheet items)
latest_balance = facts.query().by_statement_type('BalanceSheet').latest_instant().execute()

# Get latest periods with preference
latest_periods = facts.query().latest_periods(4, prefer_annual=True).execute()
```

### Method Chaining

Combine multiple filters for precise queries:

```python
# Revenue facts from 2024 10-K filings only
revenue_2024_annual = facts.query()\
    .by_concept('Revenue')\
    .by_fiscal_year(2024)\
    .by_form_type('10-K')\
    .execute()

# High-quality quarterly income statement facts
quality_quarterly = facts.query()\
    .by_statement_type('IncomeStatement')\
    .by_period_length(3)\
    .high_quality_only()\
    .execute()

# Recent balance sheet facts as of year-end
year_end_balance = facts.query()\
    .by_statement_type('BalanceSheet')\
    .as_of(date(2024, 12, 31))\
    .latest_instant()\
    .execute()
```

### Output Formats

#### Convert to DataFrame

```python
# Basic DataFrame with all columns
df = facts.query().by_concept('Revenue').to_dataframe()

# DataFrame with selected columns
df = facts.query().by_concept('Revenue').to_dataframe(
    'label', 'numeric_value', 'fiscal_period', 'fiscal_year'
)

print(df.head())
```

#### Pivot by Period

Create time-series views with periods as columns:

```python
# Get formatted financial statement
stmt = facts.query()\
    .by_statement_type('IncomeStatement')\
    .latest_periods(4)\
    .pivot_by_period()

# Get raw DataFrame pivot
pivot_df = facts.query()\
    .by_statement_type('IncomeStatement')\
    .latest_periods(4)\
    .pivot_by_period(return_statement=False)

print(pivot_df)
```

#### LLM-Ready Context

```python
# Get facts in LLM-friendly format
llm_context = facts.query().by_concept('Revenue').to_llm_context()

# Perfect for feeding to AI models
for fact_context in llm_context:
    print(f"Concept: {fact_context['concept']}")
    print(f"Value: {fact_context['value']}")
    print(f"Period: {fact_context['period']}")
```

### Query Utilities

#### Count Results

```python
# Count matching facts without loading them
revenue_count = facts.query().by_concept('Revenue').count()
print(f"Found {revenue_count} revenue facts")
```

#### Sort Results

```python
# Sort by filing date (newest first)
sorted_facts = facts.query()\
    .by_concept('Revenue')\
    .sort_by('filing_date', ascending=False)\
    .execute()

# Sort by fiscal year
sorted_by_year = facts.query()\
    .by_concept('Assets')\
    .sort_by('fiscal_year')\
    .execute()
```

### Real-World Query Examples

#### Track Revenue Growth Over Time

```python
# Get quarterly revenue for trend analysis
quarterly_revenue = facts.query()\
    .by_concept('Revenue')\
    .by_period_length(3)\
    .sort_by('period_end')\
    .to_dataframe('fiscal_year', 'fiscal_period', 'numeric_value', 'period_end')

# Calculate quarter-over-quarter growth
quarterly_revenue['growth'] = quarterly_revenue['numeric_value'].pct_change() * 100
print(quarterly_revenue[['fiscal_period', 'fiscal_year', 'numeric_value', 'growth']])
```

#### Compare Audited vs Unaudited Numbers

```python
# Get both 10-K (audited) and 10-Q (unaudited) revenue for same period
revenue_2024_q4 = facts.query()\
    .by_concept('Revenue')\
    .by_fiscal_year(2024)\
    .by_fiscal_period('Q4')\
    .by_form_type(['10-K', '10-Q'])\
    .to_dataframe('form_type', 'numeric_value', 'filing_date')

print(revenue_2024_q4)
```

#### Find Restatements

```python
# Look for the same period filed multiple times
eps_facts = facts.query()\
    .by_concept('EarningsPerShare')\
    .by_fiscal_year(2024)\
    .by_fiscal_period('Q1')\
    .sort_by('filing_date')\
    .to_dataframe('filing_date', 'numeric_value', 'form_type')

if len(eps_facts) > 1:
    print("Potential restatement found:")
    print(eps_facts)
```

#### Build Custom Financial Ratios

```python
# Get components for current ratio calculation
current_assets = facts.query()\
    .by_concept('CurrentAssets')\
    .latest_instant()\
    .execute()

current_liabilities = facts.query()\
    .by_concept('CurrentLiabilities')\
    .latest_instant()\
    .execute()

if current_assets and current_liabilities:
    assets_value = current_assets[0].numeric_value
    liabilities_value = current_liabilities[0].numeric_value
    current_ratio = assets_value / liabilities_value
    print(f"Current Ratio: {current_ratio:.2f}")
```

### Query Performance Tips

1. **Use Specific Filters**: More specific queries run faster
```python
# Good: Specific concept and year
facts.query().by_concept('us-gaap:Revenue', exact=True).by_fiscal_year(2024)

# Less efficient: Broad concept search
facts.query().by_concept('revenue')
```

2. **Limit Results Early**: Use `latest()` or `count()` when appropriate
```python
# Good: Get just what you need
recent_revenue = facts.query().by_concept('Revenue').latest(4)

# Less efficient: Get all then slice
all_revenue = facts.query().by_concept('Revenue').execute()[:4]
```

3. **Chain Filters Logically**: Put most selective filters first
```python
# Good: Narrow down quickly
facts.query().by_fiscal_year(2024).by_form_type('10-K').by_concept('Revenue')

# Less efficient: Broad filter first
facts.query().by_concept('Revenue').by_fiscal_year(2024).by_form_type('10-K')
```

The query interface provides powerful flexibility for financial analysis while maintaining simplicity for common use cases.

### Period Selection Logic

The API intelligently handles period selection:

```python
# Annual periods preferred - gets FY 2024, FY 2023, etc.
annual = company.income_statement(annual=True)

# Quarterly periods - gets Q2 2024, Q1 2024, etc.  
quarterly = company.income_statement(annual=False)
```

**Period Labeling:**
- Periods are labeled by calendar quarters based on end dates
- "Q2 2024" means period ending in Apr/May/Jun 2024
- "FY 2024" means full fiscal year ending in 2024

## Error Handling

The API is designed for graceful error handling:

```python
company = Company('INVALIDTICKER')

# These will return None instead of raising exceptions
income_stmt = company.income_statement()  # Returns None
shares = company.shares_outstanding       # Returns None  
facts = company.facts                     # Returns None

# Check before using
if company.facts:
    # Facts are available
    stmt = company.income_statement()
else:
    print("No facts available for this company")
```

## Real-World Examples

### Compare Revenue Growth

```python
from edgar import Company

companies = ['AAPL', 'MSFT', 'GOOGL']
for ticker in companies:
    company = Company(ticker)
    if company.facts:
        stmt = company.income_statement(as_dataframe=True)
        if 'Revenue' in stmt.index:
            revenue = stmt.loc['Revenue']
            growth = revenue.pct_change().iloc[0] * 100
            print(f"{ticker}: {growth:.1f}% revenue growth")
```

### Build Comparison Dashboard

```python
import pandas as pd

def compare_companies(tickers, metric='Revenue'):
    results = []
    for ticker in tickers:
        company = Company(ticker)
        stmt = company.income_statement(as_dataframe=True)
        if stmt is not None and metric in stmt.index:
            latest_value = stmt.loc[metric].iloc[0]
            results.append({
                'Company': company.name,
                'Ticker': ticker,
                metric: latest_value
            })
    return pd.DataFrame(results)

# Compare revenue across tech companies
comparison = compare_companies(['AAPL', 'MSFT', 'GOOGL', 'AMZN'])
print(comparison.sort_values('Revenue', ascending=False))
```

### Extract Key Metrics

```python
def company_snapshot(ticker):
    company = Company(ticker)
    return {
        'name': company.name,
        'ticker': ticker,
        'shares_outstanding': company.shares_outstanding,
        'public_float': company.public_float,
        'has_facts': company.facts is not None
    }

# Get snapshot for multiple companies
tickers = ['AAPL', 'TSLA', 'NVDA']
snapshots = [company_snapshot(t) for t in tickers]
df = pd.DataFrame(snapshots)
print(df)
```

## Performance Tips

1. **Cache Company Objects**: Reuse Company instances to leverage caching
2. **Use as_dataframe=True**: For bulk calculations, raw DataFrames are faster
3. **Limit Periods**: Request only the periods you need
4. **Check Availability**: Use `if company.facts:` before accessing financial data

```python
# Good: Reuse company object
company = Company('AAPL')
if company.facts:
    income = company.income_statement()
    balance = company.balance_sheet()
    cash = company.cash_flow()

# Good: Use DataFrame for calculations
df = company.income_statement(periods=10, as_dataframe=True)
analysis = df.pct_change()
```

## Integration with Other EdgarTools Features

The Facts API works seamlessly with other EdgarTools features:

```python
company = Company('AAPL')

# Combine with filings
latest_10k = company.latest('10-K')
facts_data = company.income_statement()

# Use with existing financials
financials = company.get_financials()  # Traditional XBRL approach
facts_stmt = company.income_statement()  # New Facts API approach
```

## Migration Guide

If you're using the old facts API, migration is straightforward:

```python
# Old approach
old_facts = company.get_facts()  # Returns different format

# New approach  
company.facts                    # EntityFacts object
company.income_statement()       # Formatted financial statements
company.shares_outstanding       # Direct property access
```

The new API is designed to be more intuitive and powerful while maintaining full backward compatibility.

## Troubleshooting

**Q: Why do some companies return None for financial statements?**
A: Not all companies have facts data available through the SEC API. This is normal for some entity types.

**Q: Why do I see mixed period warnings?**
A: This happens when a company has periods of different lengths (quarterly vs annual). Use `annual=True` to prefer consistent annual periods.

**Q: How do I get the most recent quarter?**
A: Use `company.income_statement(periods=1, annual=False)` to get the latest quarterly period.

**Q: Can I get historical data beyond what's shown?**
A: Yes, increase the `periods` parameter: `company.income_statement(periods=20)` for more historical data.

## API Reference

For complete API documentation of the underlying EntityFacts class and query interface, see the [EntityFacts API Reference](../api/entity-facts-reference.md).

---

*The Company Facts API is part of EdgarTools' comprehensive SEC data platform. For more information, visit the [EdgarTools Documentation](https://edgartools.dev).*