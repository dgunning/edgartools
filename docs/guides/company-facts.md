---
description: Access historical financial data from SEC XBRL filings. Query revenue, earnings, assets, and any XBRL concept over time.
---

# Company Facts: Query Historical SEC Financial Data with Python

The Company Facts API provides comprehensive access to SEC financial data through an intuitive, AI-ready interface. Get financial statements, key metrics, and detailed company information with just a few lines of code.

✨ **Latest Features:**

- **Enhanced Value Formatting**: Full numbers with commas (1,000,000,000) by default, with optional concise format ($1.0B)
- **Multi-Period Statements**: Rich hierarchical display showing multiple periods side-by-side
- **LLM Integration**: Built-in `to_llm_context()` method for AI consumption
- **Web Rendering Support**: Easy iteration over statement items with comprehensive web API methods
- **Improved Visual Display**: Professional formatting with color-coded values and hierarchical structure

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

# Get enhanced multi-period financial statements
income_stmt = company.income_statement()  # Shows multiple periods with hierarchy
balance_sheet = company.balance_sheet()  
cash_flow = company.cashflow_statement()

print(income_stmt)  # Rich multi-period display

# Get concise format for quick overview
income_compact = company.income_statement(concise_format=True)
print(income_compact)  # Shows $1.0B instead of $1,000,000,000
```

## Key Features

- **🚀 Zero Setup** - Works immediately with existing Company objects
- **💰 Full Precision** - Full numbers with commas by default, optional concise formatting
- **📊 Enhanced Display** - Multi-period hierarchical statements with rich formatting
- **🛡️ Error Resilient** - Graceful handling of missing data with intelligent fallbacks
- **🤖 AI-Ready** - Built-in LLM context generation with structured data output
- **🌐 Web Integration** - Easy iteration methods and rendering support for web applications
- **⚡ Performance Optimized** - Intelligent caching and efficient data structures
- **🎨 Professional Formatting** - Color-coded values, hierarchical structure, and smart spacing

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

Get hierarchical income statement data with flexible period options:

```python
# Default: 4 annual periods, enhanced multi-period display
income_stmt = company.income_statement()
print(income_stmt)  # Rich hierarchical display with multiple periods

# Get 8 quarterly periods with full number formatting
quarterly = company.income_statement(periods=8, annual=False)

# Use concise format for quick analysis ($1.0B vs $1,000,000,000)
compact = company.income_statement(concise_format=True)

# Get raw DataFrame for analysis
df = company.income_statement(periods=4, as_dataframe=True)

# Convert to LLM-friendly format
llm_data = income_stmt.to_llm_context()
print(llm_data['key_metrics'])  # Automatic ratio calculations
```

### Balance Sheet

Access hierarchical balance sheet data for point-in-time or trend analysis:

```python
# Enhanced multi-period balance sheet with hierarchy
balance_sheet = company.balance_sheet(periods=4)
print(balance_sheet)  # Shows Assets, Liabilities, Equity sections

# Point-in-time snapshot as of specific date
from datetime import date
snapshot = company.balance_sheet(as_of=date(2024, 12, 31))

# Concise format for executive summaries
exec_summary = company.balance_sheet(concise_format=True)

# Raw data for calculations
df = company.balance_sheet(periods=3, as_dataframe=True)

# Web rendering support - iterate over items
for item in balance_sheet:
    print(f"{item.label}: {item.get_display_value(balance_sheet.periods[0])}")
```

### Cash Flow Statement

Analyze hierarchical cash flow patterns across periods:

```python
# Enhanced annual cash flow with operating/investing/financing sections
cash_flow = company.cashflow_statement(periods=5, annual=True)
print(cash_flow)  # Rich display with cash flow categories

# Quarterly cash flow analysis with full formatting
quarterly_cf = company.cashflow_statement(periods=8, annual=False)

# Executive dashboard format
exec_cf = company.cashflow_statement(concise_format=True)

# Generate analysis context for AI
ai_context = cash_flow.to_llm_context(include_metadata=True)
print(ai_context['key_metrics'])  # Automatic cash flow metrics
```

## Method Parameters

All financial statement methods support consistent parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `periods` | int | 4 | Number of periods to retrieve |
| `annual` | bool | True | If True, prefer annual periods; if False, get quarterly |
| `as_dataframe` | bool | False | If True, return raw DataFrame; if False, return MultiPeriodStatement |
| `concise_format` | bool | False | If True, display as $1.0B; if False, display as $1,000,000,000 |

**Special Parameters:**
- `balance_sheet()` also supports `as_of` parameter for point-in-time views

## Return Types

### MultiPeriodStatement Objects (Default)

When `as_dataframe=False` (default), methods return enhanced `MultiPeriodStatement` objects with:

- **Hierarchical Structure**: Organized sections with proper parent-child relationships
- **Multi-Period Display**: Side-by-side period comparison with rich formatting
- **Smart Value Formatting**: Full numbers ($1,000,000,000) by default, per-share amounts as decimals
- **Color-Coded Display**: Green/red values, bold totals, hierarchical indentation
- **Web Rendering Support**: Easy iteration and item access for web applications
- **LLM Integration**: Built-in context generation for AI analysis

```python
stmt = company.income_statement()

# Rich multi-period display (automatic in notebooks)
print(stmt)

# Convert to DataFrame for analysis
df = stmt.to_dataframe()
revenue_growth = df.loc['Revenue'].pct_change()

# Generate LLM-friendly context
llm_data = stmt.to_llm_context()
print(llm_data['key_metrics']['profit_margin_fy_2024'])

# Iterate over items for web rendering
for item in stmt.iter_with_values():
    print(f"{item.label}: {item.get_display_value(stmt.periods[0])}")

# Get specific item
revenue_item = stmt.find_item('Revenue')
if revenue_item:
    print(f"Revenue trend: {revenue_item.values}")
```

### DataFrame Objects

When `as_dataframe=True`, methods return pandas DataFrames with enhanced structure:

```python
df = company.income_statement(as_dataframe=True)

# Enhanced DataFrame with metadata columns
print(df.columns)  # Includes: periods, depth, is_total, section, confidence
print(df.dtypes)
print(df.describe()) 

# Access financial data
revenue_series = df.loc['us-gaap:Revenues']  # Full concept names as index
print(df[df['is_total']])  # Filter to total/subtotal rows only
print(df[df['section'] == 'Revenue'])  # Filter by statement section
```

## Enhanced Features

### Value Formatting Options

The API now provides flexible value formatting to suit different use cases:

```python
# Full precision formatting (default) - best for analysis
stmt_full = company.income_statement(concise_format=False)
print(stmt_full)  # Shows: $391,035,000,000

# Concise formatting - best for presentations and dashboards
stmt_concise = company.income_statement(concise_format=True)  
print(stmt_concise)  # Shows: $391.0B

# Per-share amounts are always displayed as decimals
# Example: Earnings Per Share shows as "2.97" not "$2.97" or "$2,970,000,000"
```

**Formatting Rules:**

- **Default (`concise_format=False`)**: Full numbers with commas ($1,000,000,000)
- **Concise (`concise_format=True`)**: Scaled format ($1.0B, $500.3M)
- **Per-Share Values**: Always decimal format (2.97) regardless of setting
- **Negative Values**: Properly formatted with minus signs
- **Zero/Null Values**: Displayed as "-" for clean presentation

### LLM Integration and AI Context

Generate structured data optimized for AI and LLM consumption:

```python
stmt = company.income_statement(periods=4)

# Generate LLM-friendly context
llm_context = stmt.to_llm_context(
    include_metadata=True,      # Include data quality metrics
    include_hierarchy=False,    # Flatten for simplicity (default)
    flatten_values=True         # Create period-prefixed keys (default)
)

print("LLM Context Structure:")
print(f"Company: {llm_context['company']}")
print(f"Statement Type: {llm_context['statement_type']}")
print(f"Periods: {llm_context['periods']}")
print(f"Data Quality: {llm_context['metadata']['quality_indicators']}")

# Access flattened financial data
financial_data = llm_context['data']
print(f"Revenue FY 2024: ${financial_data.get('revenue_fy_2024', 0):,.0f}")
print(f"Revenue FY 2023: ${financial_data.get('revenue_fy_2023', 0):,.0f}")

# Automatic ratio calculations
key_metrics = llm_context.get('key_metrics', {})
if 'profit_margin_fy_2024' in key_metrics:
    print(f"Current Profit Margin: {key_metrics['profit_margin_fy_2024']:.1%}")

# Feed to LLM for analysis
import json
analysis_prompt = f"""
Analyze this financial data for {llm_context['company']}:
{json.dumps(llm_context, indent=2)}

Provide insights on profitability trends and growth patterns.
"""
```

### Web Application Integration

Easy iteration and rendering support for web applications:

```python
stmt = company.income_statement(periods=4)

# Basic iteration over all items
for item in stmt:
    print(f"{item.label}: {item.get_display_value(stmt.periods[0])}")

# Iterate with hierarchy information  
for item in stmt.iter_hierarchy():
    indent = "  " * item.depth
    parent_info = f" (parent: {item.parent.label})" if item.parent else ""
    print(f"{indent}{item.label}{parent_info}")

# Only items with values (skip empty rows)
for item in stmt.iter_with_values():
    values_summary = ", ".join([
        f"{period}: {item.get_display_value(period)}" 
        for period in stmt.periods 
        if item.values.get(period)
    ])
    print(f"{item.label} -> {values_summary}")

# Find specific items
revenue_item = stmt.find_item('Revenue')
if revenue_item:
    print(f"Found Revenue: {revenue_item.values}")

# Convert to web-friendly format
web_data = stmt.to_dict()  # Nested dictionary
flat_data = stmt.to_flat_list()  # Flat list for tables

# Period comparison analysis
comparison = stmt.get_period_comparison()
for concept, analysis in comparison.items():
    if analysis['growth_rate']:
        print(f"{concept}: {analysis['growth_rate']:.1%} growth")
```

### Advanced Statement Features

#### Smart Hierarchical Organization

Statements now display with intelligent hierarchy based on accounting standards:

```python
stmt = company.income_statement()
print(stmt)  # Shows:
# Revenue
#   Product Revenue
#   Service Revenue
# Cost of Revenue
#   Cost of Product Sales
#   Cost of Services
# Gross Profit  [calculated]
# Operating Expenses
#   Research and Development
#   Sales and Marketing
# Operating Income [calculated]
```

#### Professional Visual Display

- **Color Coding**: Green for positive values, red for negative
- **Bold Formatting**: Totals and subtotals are emphasized
- **Hierarchical Indentation**: Clear parent-child relationships
- **Confidence Indicators**: Low-confidence items marked with ◦
- **Smart Spacing**: Separators after major sections

#### Enhanced Data Quality

Statements include data quality metadata:

```python
stmt = company.income_statement()

# Check overall statement quality
if hasattr(stmt, 'canonical_coverage'):
    print(f"Canonical Coverage: {stmt.canonical_coverage:.1%}")

# Item-level confidence scores
for item in stmt.iter_with_values():
    if hasattr(item, 'confidence') and item.confidence < 0.8:
        print(f"Low confidence: {item.label} ({item.confidence:.2f})")
```

## Discovering Available Data

Not sure what a company reports? Use the discovery methods to explore before querying:

```python
facts = company.get_facts()

# Search for concepts by keyword
facts.search_concepts("revenue")      # Find all revenue-related concepts
facts.search_concepts("debt")         # Find debt-related concepts

# See what periods have data for a concept
facts.available_periods("Revenue")    # List all periods with Revenue data
```

These methods are especially useful when `get_fact()` returns `None` — the warnings will suggest using `search_concepts()` to find the right concept name and `available_periods()` to find valid periods.

Both period formats work interchangeably: `"2023-FY"` and `"FY 2023"` are equivalent.

## Advanced Usage

### Working with EntityFacts Directly

For advanced analysis, access the enhanced EntityFacts object with rich display:

```python
facts = company.facts
print(facts)  # Rich console display with summary statistics and key metrics

# Query specific facts with enhanced query interface
revenue_facts = facts.query().by_concept('Revenue').execute()

# Get time series for any concept
revenue_ts = facts.time_series('Revenue', periods=20)

# Get DEI (Document and Entity Information) facts
dei_info = facts.dei_facts()
entity_summary = facts.entity_info()

# Generate comprehensive LLM context
llm_context = facts.to_llm_context(
    focus_areas=['profitability', 'growth'], 
    time_period='5Y'
)
print(llm_context['focus_analysis']['profitability'])

# Export as AI agent tools (MCP-compatible)
agent_tools = facts.to_agent_tools()
print(agent_tools[0])  # Tool definition for AI agents
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

# Enhanced query with rich display
revenue_query = facts.query().by_concept('Revenue')
print(revenue_query)  # Rich representation of the query
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

### Enhanced Period Selection Logic

The API intelligently handles period selection with improved consistency:

```python
# Annual periods preferred - gets FY 2024, FY 2023, etc.
annual = company.income_statement(annual=True)
print(annual)  # Rich display with period headers

# Quarterly periods - gets most recent quarters
quarterly = company.income_statement(annual=False)

# Mixed periods automatically detected and handled
mixed = company.income_statement(periods=8, annual=False)
# API intelligently selects best available periods
```

**Enhanced Period Features:**

- **Smart Labeling**: Periods labeled by fiscal quarters and years
- **Consistency**: "Q2 2024" means period ending in company's fiscal Q2 of 2024
- **Hierarchy**: "FY 2024" means full fiscal year ending in 2024
- **Quality Indicators**: Period data quality shown in metadata
- **Automatic Selection**: API selects best available periods when requested periods aren't available

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

### Compare Revenue Growth with Enhanced Display

```python
from edgar import Company

companies = ['AAPL', 'MSFT', 'GOOGL']
for ticker in companies:
    company = Company(ticker)
    if company.facts:
        # Get enhanced multi-period statement
        stmt = company.income_statement(periods=2)
        print(f"\n{ticker} Revenue Analysis:")
        print(stmt)  # Rich multi-period display
        
        # Calculate growth using new methods
        df = stmt.to_dataframe()
        if not df.empty:
            revenue_row = df[df['label'].str.contains('Revenue', case=False, na=False)].iloc[0]
            periods = stmt.periods
            if len(periods) >= 2:
                current = revenue_row[periods[0]]
                prior = revenue_row[periods[1]]
                if current and prior:
                    growth = ((current - prior) / prior) * 100
                    print(f"{ticker}: {growth:.1f}% revenue growth")
        
        # Generate LLM context for deeper analysis
        llm_data = stmt.to_llm_context()
        if 'key_metrics' in llm_data:
            print(f"AI Analysis Available: {list(llm_data['key_metrics'].keys())}")
            
            # Display some automatic calculations
            if 'profit_margin_fy_2024' in llm_data['key_metrics']:
                margin = llm_data['key_metrics']['profit_margin_fy_2024']
                print(f"{ticker} Profit Margin: {margin:.1%}")
```

### Build Enhanced Comparison Dashboard

```python
import pandas as pd

def compare_companies_enhanced(tickers, periods=2):
    results = []
    for ticker in tickers:
        company = Company(ticker)
        if company.facts:
            # Get enhanced multi-period statement
            stmt = company.income_statement(periods=periods)
            
            # Extract LLM context for automated metrics
            llm_data = stmt.to_llm_context(include_metadata=True)
            
            # Build comprehensive comparison data
            company_data = {
                'Company': company.name,
                'Ticker': ticker,
                'Periods': len(stmt.periods),
                'Data_Quality': llm_data.get('metadata', {}).get('quality_indicators', []),
            }
            
            # Add revenue data for all periods
            revenue_item = stmt.find_item('Revenue')
            if revenue_item:
                for period in stmt.periods:
                    value = revenue_item.values.get(period)
                    if value:
                        company_data[f'Revenue_{period.replace(" ", "_")}'] = value
            
            # Add key metrics if available
            if 'key_metrics' in llm_data:
                for metric, value in llm_data['key_metrics'].items():
                    company_data[f'Metric_{metric}'] = value
            
            results.append(company_data)
    
    return pd.DataFrame(results)

# Compare with enhanced analytics
comparison = compare_companies_enhanced(['AAPL', 'MSFT', 'GOOGL', 'AMZN'])
print(comparison)

# Web rendering example
def render_for_web(ticker):
    company = Company(ticker)
    stmt = company.income_statement()
    
    web_data = []
    for item in stmt.iter_with_values():
        web_data.append({
            'concept': item.concept,
            'label': item.label, 
            'depth': getattr(item, 'depth', 0),
            'is_total': item.is_total,
            'values': {period: item.get_display_value(period) 
                      for period in stmt.periods if item.values.get(period)}
        })
    return web_data

web_ready_data = render_for_web('AAPL')
print(f"Generated {len(web_ready_data)} items for web display")
```

### Extract Enhanced Key Metrics

```python
def company_snapshot_enhanced(ticker):
    company = Company(ticker)
    snapshot = {
        'name': company.name,
        'ticker': ticker,
        'shares_outstanding': company.shares_outstanding,
        'public_float': company.public_float,
        'has_facts': company.facts is not None
    }
    
    if company.facts:
        # Get entity information
        entity_info = company.facts.entity_info()
        snapshot.update(entity_info)
        
        # Get financial statement summaries with LLM context
        income_stmt = company.income_statement(periods=2)
        if income_stmt:
            llm_context = income_stmt.to_llm_context()
            snapshot.update({
                'revenue_latest': llm_context['data'].get('revenue_fy_2024') or llm_context['data'].get('revenue_q4_2024'),
                'key_metrics': llm_context.get('key_metrics', {}),
                'data_quality': llm_context.get('metadata', {}).get('quality_indicators', [])
            })
        
        # Get balance sheet strength indicators
        balance_sheet = company.balance_sheet(periods=1)
        if balance_sheet:
            bs_context = balance_sheet.to_llm_context()
            assets_key = next((k for k in bs_context['data'].keys() if 'assets' in k.lower() and 'total' in k.lower()), None)
            if assets_key:
                snapshot['total_assets'] = bs_context['data'][assets_key]
            
            # Add balance sheet metrics if available
            if 'key_metrics' in bs_context:
                snapshot['balance_sheet_metrics'] = bs_context['key_metrics']
    
    return snapshot

# Get enhanced snapshots with auto-calculated metrics
tickers = ['AAPL', 'TSLA', 'NVDA']
snapshots = [company_snapshot_enhanced(t) for t in tickers]
df = pd.DataFrame(snapshots)
print(df[['name', 'ticker', 'revenue_latest', 'total_assets']].to_string())

# Display detailed metrics for one company
print("\nDetailed metrics for AAPL:")
aapl_snapshot = snapshots[0]
for key, value in aapl_snapshot.get('key_metrics', {}).items():
    print(f"{key}: {value}")

# Show data quality indicators
if 'data_quality' in aapl_snapshot:
    print(f"Data Quality: {', '.join(aapl_snapshot['data_quality'])}")

# Show balance sheet metrics if available
if 'balance_sheet_metrics' in aapl_snapshot:
    print("\nBalance Sheet Metrics:")
    for key, value in aapl_snapshot['balance_sheet_metrics'].items():
        print(f"{key}: {value}")
```

## Performance Tips

1. **Cache Company Objects**: Reuse Company instances to leverage enhanced caching
2. **Use as_dataframe=True**: For bulk calculations, raw DataFrames are faster
3. **Limit Periods**: Request only the periods you need for analysis
4. **Check Availability**: Use `if company.facts:` before accessing financial data
5. **Choose Format Wisely**: Use `concise_format=True` for display, `False` for calculations
6. **Cache LLM Context**: Store `to_llm_context()` results for repeated AI analysis
7. **Batch Web Rendering**: Use `iter_with_values()` to skip empty items

```python
# Good: Reuse company object with enhanced features
company = Company('AAPL')
if company.facts:
    print(company.facts)  # Rich display with summary statistics
    
    # Get multiple statements efficiently
    income = company.income_statement()
    balance = company.balance_sheet()
    cash = company.cashflow_statement()
    
    # Cache LLM context for AI applications
    llm_context = income.to_llm_context()
    # Reuse llm_context for multiple AI queries

# Good: Use DataFrame for bulk analysis
df = company.income_statement(periods=10, as_dataframe=True)
analysis = df.select_dtypes(include=[np.number]).pct_change()

# Good: Efficient web rendering
web_items = [item for item in stmt.iter_with_values()]  # Only items with data
rendered_data = stmt.to_dict()  # Single conversion for web APIs

# Good: Format choice based on use case
exec_dashboard = company.income_statement(concise_format=True)   # For presentations
analysis_data = company.income_statement(concise_format=False)   # For calculations
```

## Integration with Other EdgarTools Features

The enhanced Facts API works seamlessly with other EdgarTools features:

```python
company = Company('AAPL')

# Combine with filings for comprehensive analysis
latest_10k = company.latest('10-K')
facts_stmt = company.income_statement()

# Generate cross-referenced analysis
analysis_context = {
    'filing_info': {
        'form': latest_10k.form,
        'filing_date': latest_10k.filing_date,
        'accession': latest_10k.accession_no
    },
    'financial_data': facts_stmt.to_llm_context(),
    'data_sources': 'SEC Company Facts API + EDGAR Filings'
}

# Compare with traditional XBRL (if available)
try:
    xbrl = latest_10k.xbrl()  # Traditional XBRL approach
    xbrl_stmt = xbrl.statements.income_statement
    facts_stmt = company.income_statement()  # Enhanced Facts API
    
    print("Data Source Comparison:")
    print(f"XBRL Concepts: {len(xbrl_stmt) if xbrl_stmt else 0}")
    print(f"Facts API Items: {len(facts_stmt.items)}")
    print(f"Facts API Quality: {getattr(facts_stmt, 'canonical_coverage', 'N/A')}")
except:
    print("XBRL data not available - Facts API provides comprehensive coverage")
```

## Migration Guide

Upgrading from previous versions is straightforward with enhanced features:

```python
# Previous approach (still works)
old_facts = company.get_facts()  # Returns basic format
old_stmt = company.income_statement(as_dataframe=True)

# Enhanced approach with new features
facts = company.facts            # Rich EntityFacts with console display
stmt = company.income_statement()  # MultiPeriodStatement with hierarchy

# New formatting options
compact_stmt = company.income_statement(concise_format=True)  # $1.0B format
full_stmt = company.income_statement(concise_format=False)    # $1,000,000,000 format

# New LLM integration
llm_data = stmt.to_llm_context()  # AI-ready structured data

# New web integration
web_items = list(stmt.iter_with_values())  # Easy web rendering
specific_item = stmt.find_item('Revenue')  # Direct item access

# Enhanced property access with full context
shares_fact = facts.shares_outstanding_fact  # Full FinancialFact object
shares_value = facts.shares_outstanding       # Direct numeric value
```

**Key Improvements:**

- **Backward Compatible**: All existing code continues to work
- **Enhanced Display**: Rich console formatting with colors and hierarchy
- **Better Formatting**: Smart value formatting with concise options
- **AI Integration**: Built-in LLM context generation
- **Web Support**: Easy iteration and rendering methods
- **Performance**: Optimized caching and data structures

## Troubleshooting

**Q: `get_fact()` or `get_concept()` returned None — how do I find the right concept?**
A: These methods now emit a warning when a concept is not found, including suggestions for similar concept names. Use `search_concepts()` to find what the company actually reports, and `available_periods()` to see what periods have data:

```python
facts = company.get_facts()
facts.search_concepts("revenue")      # Shows all revenue-related concepts
facts.available_periods("Revenue")    # Shows periods with Revenue data
```

**Q: Why do some companies return None for financial statements?**
A: Not all companies have facts data available through the SEC API. This is normal for some entity types. The enhanced API provides better error handling and fallback strategies.

**Q: What's the difference between concise_format=True and False?**
A: `concise_format=False` (default) shows full numbers with commas ($1,000,000,000) for precision. `concise_format=True` shows scaled format ($1.0B) for presentations. Per-share amounts are always decimals regardless of setting.

**Q: How do I use the hierarchical structure in web applications?**
A: Use the iteration methods: `stmt.iter_hierarchy()` for parent-child relationships, `stmt.iter_with_values()` for items with data, or `stmt.to_dict()` for nested JSON structure.

**Q: How do I get the most recent quarter with the new format?**
A: Use `company.income_statement(periods=1, annual=False)` to get the latest quarterly period with enhanced formatting and hierarchy.

**Q: Can I get historical data beyond what's shown?**
A: Yes, increase the `periods` parameter: `company.income_statement(periods=20)` for extensive historical data with consistent formatting.

**Q: How do I integrate with AI/LLM applications?**
A: Use `stmt.to_llm_context()` to get structured, AI-ready data with automatic metric calculations and clean formatting optimized for language models.

## API Reference

### MultiPeriodStatement Methods

| Method | Description |
|--------|-------------|
| `to_dataframe()` | Convert to pandas DataFrame with metadata |
| `to_llm_context()` | Generate AI-ready structured context |
| `iter_hierarchy()` | Iterate with depth and parent information |
| `iter_with_values()` | Iterate only items with values |
| `find_item(concept)` | Find specific item by concept or label |
| `to_dict()` | Convert to nested dictionary structure |
| `to_flat_list()` | Convert to flat list for web APIs |
| `get_period_comparison()` | Get period-over-period analysis |

### EntityFacts Enhanced Methods

| Method | Description |
|--------|-------------|
| `to_llm_context()` | Comprehensive AI context with focus areas |
| `to_agent_tools()` | Export as MCP-compatible agent tools |
| `calculate_ratios()` | Financial ratio calculations |
| `peer_comparison()` | Compare with peer companies |
| `detect_anomalies()` | Identify unusual patterns |

### New Parameters

| Parameter | Methods | Description |
|-----------|---------|-------------|
| `concise_format` | All statement methods | Value display format control |
| `include_metadata` | `to_llm_context()` | Include data quality metrics |
| `flatten_values` | `to_llm_context()` | Flatten multi-period values |
| `focus_areas` | `to_llm_context()` | Emphasize specific analysis areas |

For complete API documentation of the underlying EntityFacts class and query interface, see the [EntityFacts API Reference](../api/entity-facts-reference.md).

---

*The enhanced Company Facts API is part of EdgarTools' comprehensive SEC data platform, now with AI integration, web rendering support, and professional formatting. For more information, visit the [EdgarTools Documentation](https://edgartools.dev).*