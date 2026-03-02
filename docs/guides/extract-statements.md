---
description: Extract income statements, balance sheets, and cash flow from SEC 10-K and 10-Q filings using Python and XBRL.
---

# Extract Financial Statements from SEC Filings with Python

Learn how to extract and work with financial statements from SEC filings using EdgarTools' powerful XBRL processing capabilities.

## Prerequisites

- Basic understanding of financial statements (balance sheet, income statement, cash flow)
- Familiarity with [finding companies](finding-companies.md) and [searching filings](searching-filings.md)

## Quick Start: Single Period Statements

### Get Latest Financial Statements

The fastest way to get financial statements is using the Company.financials property:

```python
from edgar import Company

# Get Apple's latest financials
company = Company("AAPL")
financials = company.get_financials()

# Access individual statements
balance_sheet = financials.balance_sheet
income_statement = financials.income_statement()
cash_flow = financials.cashflow_statement()
```


### Alternative: From Specific Filing

For more control, extract statements from a specific filing:

```python
from edgar import Company

# Get a specific filing
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()

# Parse XBRL data
xbrl = filing.xbrl()

# Access statements through the user-friendly API
statements = xbrl.statements

# Display financial statements
balance_sheet = statements.balance_sheet()
income_statement = statements.income_statement()
cash_flow = statements.cashflow_statement()

print(balance_sheet)  # Rich formatted output
```

### Enhanced Dimensional Display

EdgarTools now automatically surfaces rich dimensional segment data in financial statements when available:

```python
# Get Microsoft's income statement - now shows product/service breakdowns
company = Company("MSFT")
xbrl = company.get_filings(form="10-K").latest().xbrl()
income_stmt = xbrl.statements.income_statement()

print(income_stmt)
# Output shows both summary revenue AND detailed breakdowns:
# - Product revenue: $63.9B 
# - Service revenue: $217.8B
# - Business segment details (LinkedIn: $17.8B, Gaming: $23.5B, etc.)
```

**Control Dimensional Display:**

```python
# Default behavior - includes dimensional segment data
df_enhanced = income_stmt.to_dataframe()  # 48 rows for Microsoft
print(f"Enhanced view: {len(df_enhanced)} rows")

# Standard view - face presentation only
df_standard = income_stmt.to_dataframe(view="standard")  # 21 rows
print(f"Standard view: {len(df_standard)} rows")

# Summary view - non-dimensional totals only
df_summary = income_stmt.to_dataframe(view="summary")
print(f"Summary view: {len(df_summary)} rows")
```

**What Gets Enhanced:**
- Product/service revenue breakdowns
- Geographic segment data  
- Business unit financial details
- Any ProductOrServiceAxis dimensional facts

This enhancement works automatically across companies that provide segment data in their XBRL filings, including Microsoft, Apple, Amazon, Google, and many others.

## Standardized Financial Data Access

EdgarTools automatically standardizes XBRL data across companies, mapping ~2,000 different XBRL tags to 95 consistent concepts. This means you can compare Apple's revenue with Tesla's revenue using the same API, even though they use different underlying XBRL concepts.

**Why this matters:**
- Companies use different XBRL tags for the same concept (e.g., "Revenues", "RevenueFromContractWithCustomer", "SalesRevenueNet")
- EdgarTools normalizes these to standard concepts like "Revenue"
- Cross-company analysis becomes trivial

For the complete list of 95 standard concepts and their mappings, see [Standardization Concepts Reference](../xbrl/concepts/standardization.md).

### Simple Metric Extraction

The easiest way to get key financial metrics is using the standardized accessor methods:

```python
from edgar import Company

# Get a company's financials
company = Company("AAPL")
financials = company.get_financials()

# Extract key metrics directly - these work across all companies!
revenue = financials.get_revenue()
net_income = financials.get_net_income()
total_assets = financials.get_total_assets()

print(f"Revenue: ${revenue:,.0f}")
print(f"Net Income: ${net_income:,.0f}")
print(f"Total Assets: ${total_assets:,.0f}")
```

This simple API works consistently across all companies, regardless of their custom XBRL concepts!

### Available Standardized Methods

All methods support historical data via the `period_offset` parameter:

```python
# Income Statement Metrics
revenue_current = financials.get_revenue()           # Current period
revenue_previous = financials.get_revenue(1)        # Previous period
net_income = financials.get_net_income()

# Balance Sheet Metrics  
total_assets = financials.get_total_assets()
total_liabilities = financials.get_total_liabilities()
stockholders_equity = financials.get_stockholders_equity()
current_assets = financials.get_current_assets()
current_liabilities = financials.get_current_liabilities()

# Cash Flow Metrics
operating_cash_flow = financials.get_operating_cash_flow()
capital_expenditures = financials.get_capital_expenditures()
free_cash_flow = financials.get_free_cash_flow()    # Calculated automatically
```

### Comprehensive Financial Analysis

Get all key metrics at once with automatic ratio calculations:

```python
# Get comprehensive metrics dictionary
metrics = financials.get_financial_metrics()

# All the standard metrics are available
print(f"Revenue: ${metrics['revenue']:,.0f}")
print(f"Net Income: ${metrics['net_income']:,.0f}")
print(f"Total Assets: ${metrics['total_assets']:,.0f}")

# Plus calculated ratios
print(f"Current Ratio: {metrics['current_ratio']:.2f}")
print(f"Debt to Assets: {metrics['debt_to_assets']:.2f}")
print(f"Free Cash Flow: ${metrics['free_cash_flow']:,.0f}")
```

### Cross-Company Analysis Made Simple

Now comparing multiple companies is trivial:

```python
companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

print("Company\t\tRevenue\t\tNet Income\tTotal Assets")
print("-" * 60)

for ticker in companies:
    company = Company(ticker)
    financials = company.get_financials()
    
    if financials:
        revenue = financials.get_revenue()
        net_income = financials.get_net_income()
        total_assets = financials.get_total_assets()
        
        print(f"{ticker}\t\t${revenue/1e9:.1f}B\t\t${net_income/1e9:.1f}B\t\t${total_assets/1e9:.1f}B")
```

### Tesla Custom Concepts - No Problem!

The standardized methods automatically handle companies with custom concepts like Tesla:

```python
# Works even with companies that use non-standard XBRL concepts
tesla = Company("TSLA")
tsla_financials = tesla.get_financials()

# These work despite Tesla's custom concepts
tsla_revenue = tsla_financials.get_revenue()
tsla_net_income = tsla_financials.get_net_income()

print(f"Tesla Revenue: ${tsla_revenue:,.0f}")
print(f"Tesla Net Income: ${tsla_net_income:,.0f}")
```

### Growth Analysis with Historical Data

Calculate growth rates using the `period_offset` parameter:

```python
# Get current and previous year data
current_revenue = financials.get_revenue(0)    # Current period
previous_revenue = financials.get_revenue(1)   # Previous period

if current_revenue and previous_revenue:
    growth_rate = (current_revenue - previous_revenue) / previous_revenue * 100
    print(f"Revenue Growth: {growth_rate:.1f}%")

# Same pattern works for any metric
current_ni = financials.get_net_income(0)
previous_ni = financials.get_net_income(1)

if current_ni and previous_ni:
    ni_growth = (current_ni - previous_ni) / previous_ni * 100
    print(f"Net Income Growth: {ni_growth:.1f}%")
```

## Multi-Period Analysis

### Method 1: Using MultiFinancials

Get financials across multiple years for trend analysis:

```python
from edgar import Company, MultiFinancials

# Get multiple years of 10-K filings
company = Company("AAPL")
filings = company.get_filings(form="10-K").head(3)  # Last 3 annual reports

# Create multi-period financials
multi_financials = MultiFinancials.extract(filings)

# Access statements spanning multiple years
balance_sheet = multi_financials.balance_sheet()
income_statement = multi_financials.income_statement()
cash_flow = multi_financials.cashflow_statement()

# Use view="detailed" to include dimensional breakdowns (e.g., cost by segment)
income_detailed = multi_financials.income_statement(view="detailed")

print("Multi-Year Income Statement:")
print(income_statement)
```

### Method 2: Using XBRL Stitching

For more advanced multi-period analysis with intelligent period matching:

```python
from edgar import Company
from edgar.xbrl import XBRLS

# Get multiple filings for trend analysis
company = Company("AAPL")
filings = company.get_filings(form="10-K").head(3)

# Create stitched view across multiple filings
xbrls = XBRLS.from_filings(filings)

# Access stitched statements
stitched_statements = xbrls.statements

# Display multi-period statements with intelligent period selection
income_trend = stitched_statements.income_statement()
balance_sheet_trend = stitched_statements.balance_sheet()
cashflow_trend = stitched_statements.cashflow_statement()

print("Three-Year Revenue Trend:")
revenue_trend = income_trend.to_dataframe()
revenue_row = revenue_trend.loc[revenue_trend['label'] == 'Revenue']
print(revenue_row)
```

**Dimensional Data in Stitching:**

By default, stitching uses traditional statement structures for performance and compatibility.
Use the `view` parameter to control dimensional data:

```python
# Default stitching - standard face presentation for multi-period consistency
income_stmt = stitched_statements.income_statement()  # Clean, focused view

# Include dimensional breakdowns (e.g., cost of operations by segment)
income_stmt_detailed = stitched_statements.income_statement(view="detailed")

# Summary view - non-dimensional totals only
income_stmt_summary = stitched_statements.income_statement(view="summary")
```

**When to Use Each View:**

- **`"standard"`** (default): Best for trend analysis, ratios, and cross-period comparisons
- **`"detailed"`**: Use when you need segment data across periods (e.g., cost breakdowns by product line)
- **`"summary"`**: Quick overview of main line items only

## Working with Individual Statements

### Balance Sheet Analysis

```python
# Get balance sheet
balance_sheet = statements.balance_sheet()

# Convert to DataFrame for analysis
bs_df = balance_sheet.to_dataframe()

# Extract key balance sheet items
total_assets = bs_df[bs_df['label'] == 'Total Assets']
total_liabilities = bs_df[bs_df['label'] == 'Total Liabilities']
shareholders_equity = bs_df[bs_df['label'] == "Total Stockholders' Equity"]

print("Balance Sheet Summary:")
print(f"Total Assets: ${total_assets.iloc[0, -1]/1e9:.1f}B")
print(f"Total Liabilities: ${total_liabilities.iloc[0, -1]/1e9:.1f}B")
print(f"Shareholders' Equity: ${shareholders_equity.iloc[0, -1]/1e9:.1f}B")

# Calculate debt-to-equity ratio
debt_to_equity = total_liabilities.iloc[0, -1] / shareholders_equity.iloc[0, -1]
print(f"Debt-to-Equity Ratio: {debt_to_equity:.2f}")
```

### Income Statement Analysis

```python
# Get income statement
income_statement = statements.income_statement()

# Convert to DataFrame
is_df = income_statement.to_dataframe()

# Extract key income statement items
revenue = is_df[is_df['label'] == 'Revenue']
gross_profit = is_df[is_df['label'] == 'Gross Profit']
operating_income = is_df[is_df['label'] == 'Operating Income']
net_income = is_df[is_df['label'] == 'Net Income']

print("Income Statement Analysis:")
print(f"Revenue: ${revenue.iloc[0, -1]/1e9:.1f}B")
print(f"Gross Profit: ${gross_profit.iloc[0, -1]/1e9:.1f}B")
print(f"Operating Income: ${operating_income.iloc[0, -1]/1e9:.1f}B")
print(f"Net Income: ${net_income.iloc[0, -1]/1e9:.1f}B")

# Calculate margins
gross_margin = (gross_profit.iloc[0, -1] / revenue.iloc[0, -1]) * 100
operating_margin = (operating_income.iloc[0, -1] / revenue.iloc[0, -1]) * 100
net_margin = (net_income.iloc[0, -1] / revenue.iloc[0, -1]) * 100

print(f"\nMargin Analysis:")
print(f"Gross Margin: {gross_margin:.1f}%")
print(f"Operating Margin: {operating_margin:.1f}%")
print(f"Net Margin: {net_margin:.1f}%")
```

### Cash Flow Analysis

```python
# Get cash flow statement
cash_flow = statements.cashflow_statement()

# Convert to DataFrame
cf_df = cash_flow.to_dataframe()

# Extract cash flow components
operating_cf = cf_df[cf_df['label'] == 'Net Cash from Operating Activities']
investing_cf = cf_df[cf_df['label'] == 'Net Cash from Investing Activities']
financing_cf = cf_df[cf_df['label'] == 'Net Cash from Financing Activities']

print("Cash Flow Analysis:")
print(f"Operating Cash Flow: ${operating_cf.iloc[0, -1]/1e9:.1f}B")
print(f"Investing Cash Flow: ${investing_cf.iloc[0, -1]/1e9:.1f}B")
print(f"Financing Cash Flow: ${financing_cf.iloc[0, -1]/1e9:.1f}B")

# Calculate free cash flow (Operating CF - Capital Expenditures)
capex = cf_df[cf_df['label'].str.contains('Capital Expenditures', case=False, na=False)]
if not capex.empty:
    free_cash_flow = operating_cf.iloc[0, -1] + capex.iloc[0, -1]  # CapEx is usually negative
    print(f"Free Cash Flow: ${free_cash_flow/1e9:.1f}B")
```

## Advanced Statement Customization

### Period Views and Formatting

```python
# Get available period views for income statement
period_views = statements.get_period_views("IncomeStatement")
print("Available period views:")
for view in period_views:
    print(f"- {view['name']}: {view['description']}")

# Render with specific period view
annual_comparison = statements.income_statement(period_view="Annual Comparison")
quarterly_comparison = statements.income_statement(period_view="Quarterly Comparison")

# Show full date ranges for duration periods
income_with_dates = statements.income_statement(show_date_range=True)

print("Income Statement with Date Ranges:")
print(income_with_dates)
```

### Standardized vs Company-Specific Labels

When using stitched statements (multi-period analysis), you can control label standardization:

```python
from edgar import Company
from edgar.xbrl import XBRLS

# Get multiple filings for stitched analysis
company = Company("AAPL")
filings = company.get_filings(form="10-K").head(3)
xbrls = XBRLS.from_filings(filings)
stitched = xbrls.statements

# Get income statement with standard_concept metadata (default)
income = stitched.income_statement(standard=True)

# Labels always show original company presentation
# Use standard_concept for cross-company analysis
df = income.to_dataframe()
print("Labels with Standard Concept Mapping:")
print(df[['label', 'standard_concept']].head(10))

# Aggregate by standard concept for comparison
standardized = df.groupby('standard_concept')[df.columns[2:4]].sum()
print("\nAggregated by Standard Concept:")
print(standardized.head(10))
```

> **Note**: The `standard=True` parameter adds `standard_concept` metadata for cross-company analysis.
> Labels always preserve the company's original presentation.

## Cross-Company Analysis

### Compare Multiple Companies (Updated with New API!)

```python
import pandas as pd

def get_key_metrics(ticker):
    """Extract key financial metrics for a company using new standardized methods."""
    try:
        company = Company(ticker)
        financials = company.get_financials()
        
        if not financials:
            return None
            
        # Use the new standardized accessor methods - much simpler!
        return {
            'ticker': ticker,
            'revenue': financials.get_revenue(),
            'net_income': financials.get_net_income(),
            'total_assets': financials.get_total_assets(),
            'operating_cf': financials.get_operating_cash_flow(),
            'free_cf': financials.get_free_cash_flow()
        }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return None

# Analyze multiple companies
tech_companies = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
metrics = []

for ticker in tech_companies:
    result = get_key_metrics(ticker)
    if result:
        metrics.append(result)

# Create comparison DataFrame
comparison_df = pd.DataFrame(metrics)

# Convert to billions and calculate ratios
comparison_df['revenue_b'] = comparison_df['revenue'] / 1e9
comparison_df['net_income_b'] = comparison_df['net_income'] / 1e9
comparison_df['net_margin'] = (comparison_df['net_income'] / comparison_df['revenue']) * 100
comparison_df['roa'] = (comparison_df['net_income'] / comparison_df['total_assets']) * 100

print("Tech Giants Comparison:")
print(comparison_df[['ticker', 'revenue_b', 'net_income_b', 'net_margin', 'roa']].round(1))
```

The new standardized methods make cross-company analysis much more reliable and easier to implement!

## Notes and Disclosures

XBRL filings contain notes and disclosure sections beyond the primary financial statements. Access them with convenience methods:

```python
xbrl = filing.xbrl()

# Browse all note sections (e.g., accounting policies, segment data)
for note in xbrl.notes():
    print(note.title)

# Browse all disclosure sections (e.g., revenue disaggregation, debt details)
for disc in xbrl.disclosures():
    print(disc.title)
```

These return the same statement objects as `xbrl.statements`, filtered to notes and disclosures respectively.

## Advanced XBRL Features

### Access Raw XBRL Facts

```python
# Access the facts API for detailed XBRL data
facts = xbrl.facts

# Query facts by concept
revenue_facts = facts.query().by_concept('Revenue').to_dataframe()
print("Revenue facts across all periods:")
print(revenue_facts[['concept', 'label', 'period', 'value']])

# Search for specific concepts
earnings_facts = facts.search_facts("Earnings Per Share")
print("EPS-related facts:")
print(earnings_facts[['concept', 'label', 'value']])

# Get facts by statement type
balance_sheet_facts = facts.query().by_statement_type('BalanceSheet').to_dataframe()
print(f"Found {len(balance_sheet_facts)} balance sheet facts")
```

### Time Series Analysis

```python
# Get time series data for specific concepts
revenue_series = facts.time_series('Revenue')
net_income_series = facts.time_series('Net Income')

print("Revenue Time Series:")
print(revenue_series)

# Convert to DataFrame for analysis
import pandas as pd
ts_df = pd.DataFrame({
    'revenue': revenue_series,
    'net_income': net_income_series
})

# Calculate growth rates
ts_df['revenue_growth'] = ts_df['revenue'].pct_change() * 100
ts_df['income_growth'] = ts_df['net_income'].pct_change() * 100

print("Growth Analysis:")
print(ts_df[['revenue_growth', 'income_growth']].round(1))
```

### Dimensional Analysis

```python
# Query facts by dimensions (if available)
segment_facts = facts.query().by_dimension('Segment').to_dataframe()
if not segment_facts.empty:
    print("Segment-specific financial data:")
    print(segment_facts[['concept', 'label', 'dimension_value', 'value']].head())

# Get facts by geographic dimension
geographic_facts = facts.query().by_dimension('Geography').to_dataframe()
if not geographic_facts.empty:
    print("Geographic breakdown:")
    print(geographic_facts[['concept', 'dimension_value', 'value']].head())
```

## Export and Integration

### Export to Different Formats

```python
# Export statements to various formats
income_statement = statements.income_statement()

# Export to pandas DataFrame
df = income_statement.to_dataframe()

# Export to markdown
markdown_text = income_statement.render().to_markdown()

# Save to CSV
df.to_csv('apple_income_statement.csv', index=False)

# Save markdown to file
with open('apple_income_statement.md', 'w') as f:
    f.write(markdown_text)

print("Statements exported to CSV and Markdown")
```

### Integration with Analysis Libraries

```python
import matplotlib.pyplot as plt
import seaborn as sns

# Get multi-period data
filings = company.get_filings(form="10-K").head(5)
multi_financials = MultiFinancials.extract(filings)
income_df = multi_financials.income.to_dataframe()

# Extract revenue data for plotting
revenue_data = income_df[income_df['label'] == 'Revenue'].iloc[0, 1:].astype(float)
periods = revenue_data.index

# Create visualization
plt.figure(figsize=(10, 6))
plt.plot(periods, revenue_data / 1e9, marker='o', linewidth=2)
plt.title('Apple Revenue Trend (5 Years)')
plt.xlabel('Period')
plt.ylabel('Revenue (Billions USD)')
plt.xticks(rotation=45)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# Calculate year-over-year growth
revenue_growth = revenue_data.pct_change() * 100
print("Year-over-Year Revenue Growth:")
for period, growth in revenue_growth.dropna().items():
    print(f"{period}: {growth:.1f}%")
```

## Performance Optimization

### Efficient Multi-Company Analysis

```python
# Efficient batch processing
def batch_analyze_companies(tickers, max_workers=5):
    """Analyze multiple companies efficiently."""
    from concurrent.futures import ThreadPoolExecutor
    
    def analyze_single(ticker):
        try:
            company = Company(ticker)
            financials = company.financials
            return {
                'ticker': ticker,
                'revenue': financials.income.loc['Revenue'].iloc[0],
                'assets': financials.balance_sheet.loc['Total Assets'].iloc[0]
            }
        except Exception as e:
            return {'ticker': ticker, 'error': str(e)}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(analyze_single, tickers))
    
    return [r for r in results if 'error' not in r]

# Analyze S&P 100 companies efficiently
sp100_sample = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'JPM']
results = batch_analyze_companies(sp100_sample)

comparison_df = pd.DataFrame(results)
print("Batch Analysis Results:")
print(comparison_df.head())
```

### Caching for Repeated Analysis

```python
# Cache XBRL data for repeated use
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest()

# Parse once, use multiple times
xbrl = filing.xbrl()

# Perform different analyses on same data
balance_sheet = xbrl.statements.balance_sheet()
income_statement = xbrl.statements.income_statement()
cash_flow = xbrl.statements.cashflow_statement()

# Access facts for custom queries
facts = xbrl.facts
revenue_facts = facts.query().by_concept('Revenue').to_dataframe()
margin_facts = facts.search_facts("margin")
```

## Common Patterns and Best Practices

### Robust Financial Metric Extraction

```python
def safe_extract_metric(statement_df, label, column=-1, default=None):
    """Safely extract a metric from financial statement DataFrame."""
    try:
        rows = statement_df[statement_df['label'].str.contains(label, case=False, na=False)]
        if not rows.empty:
            return rows.iloc[0, column]
        return default
    except Exception:
        return default

# Use for robust metric extraction
income_df = statements.income_statement().to_dataframe()

revenue = safe_extract_metric(income_df, 'Revenue')
net_income = safe_extract_metric(income_df, 'Net Income')
operating_income = safe_extract_metric(income_df, 'Operating Income')

if revenue and net_income:
    net_margin = (net_income / revenue) * 100
    print(f"Net Margin: {net_margin:.1f}%")
```

### Handle Missing or Inconsistent Data

```python
def get_financial_metrics(company_ticker):
    """Get financial metrics with error handling."""
    try:
        company = Company(company_ticker)
        financials = company.financials
        
        metrics = {}
        
        # Try to get income statement metrics
        try:
            income = financials.income
            metrics['revenue'] = income.loc['Revenue'].iloc[0] if 'Revenue' in income.index else None
            metrics['net_income'] = income.loc['Net Income'].iloc[0] if 'Net Income' in income.index else None
        except Exception as e:
            print(f"Income statement error for {company_ticker}: {e}")
        
        # Try to get balance sheet metrics
        try:
            balance_sheet = financials.balance_sheet
            metrics['total_assets'] = balance_sheet.loc['Total Assets'].iloc[0] if 'Total Assets' in balance_sheet.index else None
        except Exception as e:
            print(f"Balance sheet error for {company_ticker}: {e}")
        
        return metrics
        
    except Exception as e:
        print(f"Company error for {company_ticker}: {e}")
        return {}

# Test with various companies
test_companies = ['AAPL', 'INVALID_TICKER', 'MSFT']
for ticker in test_companies:
    metrics = get_financial_metrics(ticker)
    if metrics:
        print(f"{ticker}: {metrics}")
```

## Troubleshooting Common Issues

### Statement Not Available

```python
# Check what statements are available
try:
    statements = xbrl.statements
    available_statements = statements.available_statements()
    print(f"Available statements: {available_statements}")
    
    # Try alternative statement access
    if 'IncomeStatement' in available_statements:
        income = statements.income_statement()
    elif 'ComprehensiveIncome' in available_statements:
        income = statements['ComprehensiveIncome']
    else:
        print("No income statement available")
        
except Exception as e:
    print(f"Error accessing statements: {e}")
```

### Period Selection Issues

```python
# Check available periods
reporting_periods = xbrl.reporting_periods
print("Available reporting periods:")
for period in reporting_periods[:5]:  # Show first 5
    print(f"- {period['date']} ({period['type']}): {period.get('duration', 'N/A')} days")

# Handle quarterly vs annual periods
if any(p.get('duration', 0) < 120 for p in reporting_periods):
    print("Quarterly periods detected")
    quarterly_income = statements.income_statement(period_view="Quarterly Comparison")
else:
    print("Annual periods only")
    annual_income = statements.income_statement(period_view="Annual Comparison")
```

## Next Steps

Now that you can extract financial statements, explore these advanced topics:

- **[XBRL Documentation Hub](../xbrl/index.md)** - Central navigation for all XBRL documentation
- **[Multi-Period Analysis](../xbrl/guides/multi-period-analysis.md)** - Compare financials across multiple years
- **[Choosing the Right API](../xbrl/getting-started/choosing-the-right-api.md)** - Decision guide for which API to use
- **[Dimension Handling Guide](../xbrl/concepts/dimension-handling.md)** - Understanding dimensional data (segments, breakdowns)
- **[Standardization Concepts](../xbrl/concepts/standardization.md)** - 95 standard concepts for cross-company comparison

## Related Documentation

- **[Getting XBRL from Filings](../getting-xbrl.md)** - Original XBRL documentation
- **[Company Financials](../company-financials.md)** - Company financials API
- **[XBRL API Reference](../api/xbrl.md)** - Complete XBRL class documentation
- **[StatementType Quick Reference](../StatementType-Quick-Reference.md)** - Statement type enums and API comparison