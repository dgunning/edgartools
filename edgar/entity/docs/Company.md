# Company Class Documentation

## Overview

The `Company` class represents a public company that files with the SEC. It provides comprehensive access to company information, filings, financial data, and metadata. Company extends the `Entity` class with company-specific functionality like financial statements, ticker lookup, and enhanced data access.

**Key Features:**
- Access all company filings via SEC submissions API
- Retrieve structured financial data (facts)
- Get financial statements from 10-K and 10-Q filings
- Access company metadata (tickers, exchanges, addresses, industry)
- Simplified interface for common company analysis workflows

## Common Actions

Quick reference for the most frequently used Company methods:

### Get a Company
```python
# By ticker (case-insensitive)
company = Company("AAPL")
company = Company("aapl")  # Works the same

# By CIK (Central Index Key)
company = Company(320193)           # Integer
company = Company("320193")         # String (no padding)
company = Company("0000320193")     # String (zero-padded)
```

### Access Filings
```python
# Get all filings
filings = company.get_filings()

# Filter by form type
filings_10k = company.get_filings(form="10-K")
filings_8k = company.get_filings(form="8-K")
filings_multi = company.get_filings(form=["10-K", "10-Q"])

# Get latest filing
latest = company.get_filings(form="10-K").latest()

# Quick access to latest reports
latest_10k = company.latest_tenk  # Latest 10-K as TenK object
latest_10q = company.latest_tenq  # Latest 10-Q as TenQ object
```

### Access Financial Data
```python
# Get company facts (from SEC Company Facts API)
facts = company.get_facts()

# Access facts property (cached)
facts = company.facts

# Get financial statements from latest filings
financials = company.get_financials()           # From latest 10-K
quarterly = company.get_quarterly_financials()  # From latest 10-Q
```

### Company Information
```python
# Basic information
print(company.name)              # Company name
print(company.cik)               # Central Index Key
print(company.tickers)           # List of ticker symbols
print(company.get_ticker())      # Primary ticker

# Industry and classification
print(company.sic)               # SIC code
print(company.industry)          # Industry description
print(company.fiscal_year_end)   # Fiscal year end date

# Trading information
print(company.get_exchanges())   # List of exchanges
```

## Getting a Company

### By Ticker Symbol

The most common way to get a company is by ticker symbol:

```python
from edgar import Company

# Ticker is case-insensitive
apple = Company("AAPL")
tesla = Company("TSLA")
microsoft = Company("msft")  # Lowercase works too
```

**How it works**: EdgarTools looks up the ticker in SEC reference data to find the CIK, then loads company data using that CIK.

**Note**: Some companies have multiple tickers. The ticker lookup finds the company (CIK) that the ticker belongs to.

### By CIK (Central Index Key)

For direct access, use the CIK:

```python
# CIK as integer (preferred)
apple = Company(320193)

# CIK as string (no padding needed)
apple = Company("320193")

# CIK as zero-padded string (also works)
apple = Company("0000320193")
```

**Why use CIK?**
- Faster (one API call vs. two for ticker lookup)
- Unique identifier (never changes)
- Avoids ticker ambiguity

### Company Not Found

```python
from edgar import Company

try:
    company = Company("INVALID")
except Exception as e:
    print(f"Company not found: {e}")

# Or check after creation
company = Company("AAPL")
if company.not_found:
    print("Company not found")
```

## Core Properties

### Identity Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | str | Official company name |
| `cik` | int | Central Index Key (unique identifier) |
| `tickers` | List[str] | All ticker symbols for the company |
| `fiscal_year_end` | str | Fiscal year end date (e.g., "12-31") |

### Classification Properties

| Property | Type | Description |
|----------|------|-------------|
| `sic` | int | Standard Industrial Classification code |
| `industry` | str | Industry description from SIC |
| `is_company` | bool | True if entity is a company (vs. individual) |
| `is_individual` | bool | True if entity is an individual |

### Financial Data Properties

| Property | Type | Description |
|----------|------|-------------|
| `facts` | EntityFacts | Company facts from SEC API (cached) |
| `latest_tenk` | TenK | Latest 10-K filing object |
| `latest_tenq` | TenQ | Latest 10-Q filing object |
| `public_float` | float | Public float value (if available) |
| `shares_outstanding` | int | Outstanding shares (if available) |

### Status Properties

| Property | Type | Description |
|----------|------|-------------|
| `not_found` | bool | True if company was not found |

## Core Methods

### get_filings()

Get company filings with optional filtering:

```python
def get_filings(
    form: str | List[str] = None,
    accession_number: str | List[str] = None,
    file_number: str | List[str] = None,
    is_xbrl: bool = None,
    is_inline_xbrl: bool = None,
    sort_by: str = "filing_date"
) -> EntityFilings
```

**Parameters:**
- `form`: Form type(s) to filter (e.g., "10-K", ["10-K", "10-Q"])
- `accession_number`: Specific accession number(s)
- `file_number`: SEC file number(s) for tracking related filings
- `is_xbrl`: Filter for XBRL filings only
- `is_inline_xbrl`: Filter for inline XBRL filings only
- `sort_by`: Sort order (default: "filing_date")

**Returns**: `EntityFilings` collection

**Examples:**

```python
# Get all filings
all_filings = company.get_filings()

# Get specific form type
filings_10k = company.get_filings(form="10-K")
filings_10q = company.get_filings(form="10-Q")

# Multiple form types
annual_quarterly = company.get_filings(form=["10-K", "10-Q"])

# Filter by XBRL availability
xbrl_filings = company.get_filings(is_xbrl=True)
inline_xbrl = company.get_filings(is_inline_xbrl=True)

# Get specific filing by accession number
specific = company.get_filings(
    accession_number="0000320193-24-000123"
)

# Get related filings by file number
related = company.get_filings(file_number="001-36743")
```

### get_facts()

Get structured financial data from SEC Company Facts API:

```python
def get_facts() -> EntityFacts
```

**Returns**: `EntityFacts` object containing company financial data

**Examples:**

```python
# Get facts
facts = company.get_facts()

# Access via property (cached)
facts = company.facts

# Work with facts
income_stmt = facts.get_income_statement()
balance_sheet = facts.get_balance_sheet()
cash_flow = facts.get_cash_flow_statement()
```

**Note**: Facts are cached after first access. The `.facts` property provides convenient cached access.

### get_financials()

Get financial statements from latest 10-K:

```python
def get_financials() -> Optional[Financials]
```

**Returns**: `Financials` object from latest 10-K, or None if not available

**Examples:**

```python
# Get annual financials
financials = company.get_financials()

if financials:
    print(financials.income_statement)
    print(financials.balance_sheet)
    print(financials.cash_flow)
```

### get_quarterly_financials()

Get financial statements from latest 10-Q:

```python
def get_quarterly_financials() -> Optional[Financials]
```

**Returns**: `Financials` object from latest 10-Q, or None if not available

**Examples:**

```python
# Get quarterly financials
quarterly = company.get_quarterly_financials()

if quarterly:
    print(quarterly.income_statement)
```

### get_ticker()

Get the primary ticker symbol:

```python
def get_ticker() -> Optional[str]
```

**Returns**: Primary ticker symbol, or None if no tickers

**Examples:**

```python
ticker = company.get_ticker()
if ticker:
    print(f"Trading as: {ticker}")
```

### get_exchanges()

Get all exchanges where company is listed:

```python
def get_exchanges() -> List[str]
```

**Returns**: List of exchange names

**Examples:**

```python
exchanges = company.get_exchanges()
for exchange in exchanges:
    print(f"Listed on: {exchange}")
```

## Accessing Filings

### Get All Filings

```python
company = Company("AAPL")

# Get all filings (returns EntityFilings)
filings = company.get_filings()

print(f"Total filings: {len(filings)}")

# Iterate through filings
for filing in filings:
    print(f"{filing.form}: {filing.filing_date}")
```

### Filter by Form Type

```python
# Single form type
filings_10k = company.get_filings(form="10-K")
filings_8k = company.get_filings(form="8-K")
filings_def14a = company.get_filings(form="DEF 14A")

# Multiple form types
annual_reports = company.get_filings(form=["10-K", "10-K/A"])
periodic = company.get_filings(form=["10-K", "10-Q"])
```

### Get Latest Filing

```python
# Get latest 10-K
latest_10k = company.get_filings(form="10-K").latest()

# Get latest 8-K
latest_8k = company.get_filings(form="8-K").latest()

# Get multiple latest filings
latest_5_10ks = company.get_filings(form="10-K").latest(5)
```

### Quick Access to Latest Reports

```python
# Property access to latest reports (as form-specific objects)
latest_10k = company.latest_tenk  # Returns TenK object
latest_10q = company.latest_tenq  # Returns TenQ object

# Access financial statements directly
if latest_10k:
    print(latest_10k.financials.income_statement)
```

### Filter by XBRL

```python
# Get only XBRL filings
xbrl_filings = company.get_filings(is_xbrl=True)

# Get only inline XBRL filings
inline_xbrl = company.get_filings(is_inline_xbrl=True)

# Check specific form for XBRL
xbrl_10ks = company.get_filings(form="10-K", is_xbrl=True)
```

### Working with Filing Results

```python
# Get filings
filings = company.get_filings(form="10-K")

# Access by index
first_filing = filings[0]
tenth_filing = filings[9]

# Convert to DataFrame
df = filings.to_pandas()

# Get subset
recent_10 = filings.head(10)
last_10 = filings.tail(10)

# Filter further
filings_2024 = filings.filter(filing_date="2024-01-01:")
```

## Accessing Financial Data

### Company Facts API

The SEC provides structured financial data via the Company Facts API:

```python
company = Company("AAPL")

# Get facts
facts = company.get_facts()

# Or use cached property
facts = company.facts

# Build financial statements from facts
income = facts.get_income_statement()
balance = facts.get_balance_sheet()
cashflow = facts.get_cash_flow_statement()
```

### Financial Statements from Filings

Get financials directly from 10-K or 10-Q filings:

```python
# From latest 10-K
annual_financials = company.get_financials()

if annual_financials:
    income = annual_financials.income_statement
    balance = annual_financials.balance_sheet
    cashflow = annual_financials.cash_flow

# From latest 10-Q
quarterly_financials = company.get_quarterly_financials()

if quarterly_financials:
    income = quarterly_financials.income_statement
```

### XBRL from Filings

Access raw XBRL data:

```python
# Get latest 10-K filing
filing = company.get_filings(form="10-K").latest()

# Parse XBRL
xbrl = filing.xbrl()

# Access statements
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()

# Convert to DataFrame
df = income.to_dataframe()
```

## Company Metadata

### Identity and Contact

```python
company = Company("AAPL")

# Basic identity
print(f"Name: {company.name}")
print(f"CIK: {company.cik}")

# Access detailed data
data = company.data

# Addresses
if data.business_address:
    print(f"Business Address: {data.business_address}")
if data.mailing_address:
    print(f"Mailing Address: {data.mailing_address}")

# Contact information
if hasattr(data, 'phone'):
    print(f"Phone: {data.phone}")
if hasattr(data, 'website'):
    print(f"Website: {data.website}")
```

### Tickers and Exchanges

```python
# Get all tickers
tickers = company.tickers
print(f"Tickers: {', '.join(tickers)}")

# Get primary ticker
primary = company.get_ticker()
print(f"Primary ticker: {primary}")

# Get exchanges
exchanges = company.get_exchanges()
for exchange in exchanges:
    print(f"Listed on: {exchange}")
```

### Industry Classification

```python
# SIC code and description
print(f"SIC: {company.sic}")
print(f"Industry: {company.industry}")

# Fiscal year end
print(f"Fiscal Year End: {company.fiscal_year_end}")

# Entity type and category
data = company.data
if hasattr(data, 'entity_type'):
    print(f"Entity Type: {data.entity_type}")
if hasattr(data, 'category'):
    print(f"Category: {data.category}")
```

### Former Names

```python
data = company.data

if hasattr(data, 'former_names') and data.former_names:
    print("Former Names:")
    for former in data.former_names:
        print(f"  {former['name']}: {former['from']} to {former['to']}")
```

## Common Workflows

### Analyze Annual Reports Over Time

```python
company = Company("AAPL")

# Get all 10-K filings
filings_10k = company.get_filings(form="10-K")

# Get last 5 years
last_5_years = filings_10k.latest(5)

# Analyze each year
for filing in last_5_years:
    print(f"\n{filing.filing_date} - {filing.report_date}")

    # Get XBRL data
    xbrl = filing.xbrl()

    # Get income statement
    income = xbrl.statements.income_statement()
    df = income.to_dataframe()

    # Show revenue
    if 'Revenue' in df.index:
        revenue = df.loc['Revenue'].iloc[0]
        print(f"  Revenue: ${revenue:,.0f}")
```

### Track Quarterly Performance

```python
company = Company("AAPL")

# Get all 10-Q filings
filings_10q = company.get_filings(form="10-Q")

# Get last 4 quarters
last_4_quarters = filings_10q.latest(4)

# Analyze each quarter
quarterly_revenue = []

for filing in last_4_quarters:
    xbrl = filing.xbrl()

    # Get revenue from current period
    current = xbrl.current_period
    income = current.income_statement()

    # Extract revenue
    df = income.to_dataframe()
    if 'Revenue' in df.index:
        revenue = df.loc['Revenue'].iloc[0]
        quarterly_revenue.append({
            'period': filing.report_date,
            'revenue': revenue
        })

# Show trend
import pandas as pd
trend_df = pd.DataFrame(quarterly_revenue)
print(trend_df)
```

### Compare Multiple Companies

```python
companies = {
    'AAPL': Company("AAPL"),
    'MSFT': Company("MSFT"),
    'GOOGL': Company("GOOGL")
}

results = []

for ticker, company in companies.items():
    # Get latest 10-K
    filing = company.get_filings(form="10-K").latest()

    if filing and filing.is_xbrl:
        xbrl = filing.xbrl()
        income = xbrl.statements.income_statement()
        df = income.to_dataframe()

        # Extract key metrics
        results.append({
            'ticker': ticker,
            'company': company.name,
            'revenue': df.loc['Revenue'].iloc[0] if 'Revenue' in df.index else None,
            'net_income': df.loc['Net Income'].iloc[0] if 'Net Income' in df.index else None
        })

# Compare
import pandas as pd
comparison_df = pd.DataFrame(results)
print(comparison_df)
```

### Find Earnings Announcements

```python
company = Company("AAPL")

# Get 8-K filings
filings_8k = company.get_filings(form="8-K")

# Find earnings announcements (Item 2.02)
earnings_8ks = []

for filing in filings_8k:
    if filing.items and "2.02" in filing.items:
        earnings_8ks.append({
            'filing_date': filing.filing_date,
            'report_date': filing.report_date,
            'items': filing.items
        })

# Show recent earnings dates
import pandas as pd
earnings_df = pd.DataFrame(earnings_8ks).head(10)
print(earnings_df)
```

### Export Company Data

```python
company = Company("AAPL")

# Get all filings
filings = company.get_filings(form=["10-K", "10-Q"])

# Convert to DataFrame
df = filings.to_pandas()

# Export to CSV
df.to_csv("apple_filings.csv", index=False)

# Export facts
facts = company.get_facts()
facts_df = facts.to_pandas()
facts_df.to_csv("apple_facts.csv")

# Export specific statement
income = facts.get_income_statement()
income.to_csv("apple_income.csv")
```

### Build Custom Dashboard

```python
company = Company("AAPL")

# Collect key metrics
dashboard = {
    'company': company.name,
    'ticker': company.get_ticker(),
    'cik': company.cik,
    'industry': company.industry,
    'fiscal_year_end': company.fiscal_year_end
}

# Add latest filing info
latest_10k = company.get_filings(form="10-K").latest()
if latest_10k:
    dashboard['latest_10k_date'] = latest_10k.filing_date
    dashboard['latest_10k_period'] = latest_10k.report_date

latest_10q = company.get_filings(form="10-Q").latest()
if latest_10q:
    dashboard['latest_10q_date'] = latest_10q.filing_date
    dashboard['latest_10q_period'] = latest_10q.report_date

# Add financial metrics
try:
    facts = company.get_facts()
    income = facts.get_income_statement(annual=True, periods=1)

    # Extract metrics (adjust based on your needs)
    dashboard['latest_revenue'] = "See income statement"
    dashboard['latest_net_income'] = "See income statement"
except:
    dashboard['facts_available'] = False

print(dashboard)
```

## Best Practices

### 1. Use Ticker for Convenience, CIK for Performance

```python
# Good for interactive use
company = Company("AAPL")

# Better for production/scripts
company = Company(320193)
```

### 2. Cache the Company Object

```python
# Good - reuse company object
company = Company("AAPL")
filings_10k = company.get_filings(form="10-K")
filings_10q = company.get_filings(form="10-Q")
facts = company.facts

# Less efficient - creates company multiple times
filings_10k = Company("AAPL").get_filings(form="10-K")
filings_10q = Company("AAPL").get_filings(form="10-Q")
```

### 3. Use Latest Properties for Quick Access

```python
# Good - uses cached property
latest_10k = company.latest_tenk

# More verbose
latest_10k = company.get_filings(form="10-K").latest().obj()
```

### 4. Check XBRL Availability

```python
filing = company.get_filings(form="10-K").latest()

if filing.is_xbrl:
    xbrl = filing.xbrl()
    # Process XBRL data
else:
    # Fall back to text parsing or skip
    print("No XBRL data available")
```

### 5. Handle Missing Data Gracefully

```python
company = Company("AAPL")

# Check if facts are available
try:
    facts = company.get_facts()
    income = facts.get_income_statement()
except Exception as e:
    print(f"Facts not available: {e}")
    income = None

# Check if filings exist
filings = company.get_filings(form="10-K")
if not filings.empty:
    latest = filings.latest()
else:
    print("No 10-K filings found")
```

## Error Handling

### Company Not Found

```python
from edgar import Company

try:
    company = Company("INVALIDTICKER")
except Exception as e:
    print(f"Error: {e}")

# Or check after creation
company = Company("AAPL")
if company.not_found:
    print("Company not found")
    exit()
```

### No Filings Available

```python
filings = company.get_filings(form="RARE-FORM")

if filings.empty:
    print("No filings of this type found")
else:
    latest = filings.latest()
```

### Facts Not Available

```python
try:
    facts = company.get_facts()
except Exception as e:
    print(f"Facts not available: {e}")
    facts = None

# Some companies may not have facts data
if facts is None:
    print("Using alternative data source")
```

### Missing Financial Statements

```python
financials = company.get_financials()

if financials is None:
    print("No 10-K with financials found")
    # Try quarterly
    financials = company.get_quarterly_financials()

if financials:
    # Process financials
    pass
```

## Performance Considerations

### Minimize API Calls

```python
# Good - one company object, reused
company = Company("AAPL")
filings = company.get_filings()
facts = company.facts
latest_10k = company.latest_tenk

# Less efficient - creates company 3 times
filings = Company("AAPL").get_filings()
facts = Company("AAPL").facts
latest_10k = Company("AAPL").latest_tenk
```

### Use Facts Property (Cached)

```python
# First call fetches data
facts = company.facts

# Subsequent calls use cache
income = company.facts.get_income_statement()
balance = company.facts.get_balance_sheet()
```

### Filter Filings Early

```python
# Good - filter at source
recent_10ks = company.get_filings(form="10-K", is_xbrl=True)

# Less efficient - get all then filter
all_filings = company.get_filings()
recent_10ks = [f for f in all_filings if f.form == "10-K" and f.is_xbrl]
```

### Use EntityFilings Methods

```python
filings = company.get_filings(form="10-K")

# Good - use built-in methods
latest = filings.latest()
recent_5 = filings.latest(5)

# Less efficient - manual slicing
sorted_filings = sorted(filings, key=lambda f: f.filing_date, reverse=True)
latest = sorted_filings[0]
```

## Display and Representation

### Rich Display

Company has a rich display showing comprehensive information:

```python
company = Company("AAPL")
print(company)
```

Shows:
- Company name and ticker
- CIK and entity type
- Category and industry (SIC)
- Fiscal year end
- Trading exchanges and symbols
- Business and mailing addresses
- Contact information
- Former names (if any)

### String Representation

```python
# Simple string representation
str(company)  # Returns "Company(name='Apple Inc.', cik=320193)"

# Display in console
print(company)  # Shows rich formatted display
```

## Integration with Other Classes

### Company → EntityFilings → EntityFiling

```python
company = Company("AAPL")           # Company object

filings = company.get_filings()     # EntityFilings collection
# Type: EntityFilings (maintains company context)

filing = filings[0]                 # EntityFiling instance
# Type: EntityFiling (has entity-specific metadata)

# EntityFiling knows its company
entity = filing.get_entity()        # Returns the Company
```

### Company → Facts → Statements

```python
company = Company("AAPL")

facts = company.get_facts()         # EntityFacts object

income = facts.get_income_statement()    # Statement object
balance = facts.get_balance_sheet()      # Statement object
```

### Company → Filing → XBRL

```python
company = Company("AAPL")

filing = company.get_filings(form="10-K").latest()

xbrl = filing.xbrl()                # XBRL object

statements = xbrl.statements        # Statements collection
income = statements.income_statement()
```

## Comparison: Company vs Entity

Company extends Entity with company-specific features:

| Feature | Entity | Company |
|---------|--------|---------|
| Basic identity (name, CIK) | ✅ | ✅ (inherited) |
| Get filings | ✅ | ✅ (inherited) |
| Tickers | ✅ | ✅ (enhanced) |
| Facts | ❌ | ✅ |
| Financial statements | ❌ | ✅ |
| latest_tenk / latest_tenq | ❌ | ✅ |
| get_financials() | ❌ | ✅ |
| get_quarterly_financials() | ❌ | ✅ |

**When to use Company**: 95% of use cases (public companies)
**When to use Entity**: Individual filers or when entity type is unknown

## Troubleshooting

### "Company not found"

**Cause**: Ticker or CIK doesn't exist or is misspelled

**Solution**:
```python
# Verify ticker
from edgar import find_company

results = find_company("APPL")  # Search for similar
for result in results:
    print(f"{result.name}: {result.ticker}")
```

### "No filings found"

**Cause**: Company may be newly registered or form type is wrong

**Solution**:
```python
# Check what filings exist
all_filings = company.get_filings()
print(f"Total filings: {len(all_filings)}")

# Check form types
df = all_filings.to_pandas()
print(df['form'].value_counts())
```

### "Facts not available"

**Cause**: Company may be investment company, foreign filer, or recently registered

**Solution**:
```python
# Check entity type
print(f"Entity type: {company.data.entity_type}")

# Fall back to XBRL from filings
filing = company.get_filings(form="10-K").latest()
if filing and filing.is_xbrl:
    xbrl = filing.xbrl()
    # Use XBRL instead of facts
```

### "Ticker has multiple companies"

**Cause**: Some tickers may have had multiple owners over time

**Solution**:
```python
# Use CIK for specific company
company = Company(320193)  # Specific to Apple Inc.

# Or verify after ticker lookup
company = Company("AAPL")
print(f"Got: {company.name} (CIK: {company.cik})")
```

This comprehensive guide covers everything you need to work with Company objects in edgartools, from basic usage to advanced workflows and integration patterns.
