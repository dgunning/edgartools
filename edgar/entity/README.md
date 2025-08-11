# EdgarTools Entity Package

The `edgar.entity` package provides a comprehensive, intuitive API for working with SEC entities like companies, funds, and individuals that file with the SEC.

## Key Features

- **Hierarchical Design**: Clear class hierarchy that matches the real-world domain model
- **Specialized Classes**: Tailored implementations for companies, funds, and other SEC filers
- **Type Annotations**: Strong typing for better IDE support and validation
- **Factory Functions**: Convenient creation methods for common use cases
- **Lazy Loading**: Efficient data retrieval with automatic pagination
- **Rich Display**: Beautiful terminal output with detailed entity information

## Class Hierarchy

- `SecFiler` (abstract base class)
  - `Entity` (concrete class for any SEC filer)
    - `Company` (specialized for public companies)
    - `Fund` (specialized for investment funds)
      - `FundClass` (for specific fund share classes)

## Getting Started

### Working with Companies

Companies can be created using their ticker symbol or CIK number:

```python
from edgar.entity import Company

# Create by ticker symbol
apple = Company("AAPL")

# Create by CIK number
microsoft = Company("0000789019")

# Access basic information
print(f"Name: {apple.data.name}")
print(f"CIK: {apple.cik}")
print(f"Ticker: {apple.get_ticker()}")
print(f"Industry: {apple.data.sic_description}")
```

### Getting Company Filings

The entity package makes it easy to retrieve and filter filings:

```python
# Get all filings for a company
all_filings = apple.get_filings()

# Filter by form type
annual_reports = apple.get_filings(form="10-K")
quarterly_reports = apple.get_filings(form=["10-Q"])

# Filter by date
recent_filings = apple.get_filings(filing_date="2022-01-01:")
specific_period = apple.get_filings(filing_date="2020-01-01:2020-12-31")

# Get the latest filing of a specific type
latest_10k = apple.get_filings(form="10-K").latest()

# Shortcut for latest filings
latest_10k = apple.latest_tenk
latest_10q = apple.latest_tenq

# Pagination is available for large result sets
filings_page = all_filings.head(10)
next_page = filings_page.next()
previous_page = next_page.previous()
```

### Accessing Financial Data

Financial information is easily accessible through specialized methods:

```python
# Get all financial statements from the latest 10-K
financials = apple.get_financials()

# Get quarterly financials from the latest 10-Q
quarterly = apple.get_quarterly_financials()

# Access specific financial statements
balance_sheet = financials.balance_sheet
income_statement = financials.income_statement
cash_flow = financials.cashflow_statement

# Convert to pandas DataFrame for analysis
income_df = income_statement.to_dataframe()
```

### Working with Generic Entities

For cases where the entity type is unknown or when working with non-company filers:

```python
from edgar.entity import Entity, get_entity

# Create an entity by CIK
entity = Entity("0000320193")

# Use factory function for automatic type detection
entity = get_entity("0000320193")

# Check entity type
if entity.is_company:
    print(f"{entity.data.name} is a company")
elif entity.is_individual():
    print(f"{entity.data.name} is an individual")

# Get the latest filings
latest_filings = entity.get_filings().latest(5)
```

### Working with Investment Funds

Specialized classes are available for working with investment funds:

```python
from edgar.entity import Fund, FundClass, FundSeries, get_fund

# Create a fund by CIK
vanguard_index = Fund("0000036405")

# Get fund by ticker (returns either Fund or FundClass)
fund_or_class = get_fund("VFINX")

# Get fund classes
if isinstance(fund_or_class, FundClass):
    # It's a fund class
    parent_fund = fund_or_class.fund
    all_classes = parent_fund.get_classes()
else:
    # It's a fund
    all_classes = fund_or_class.get_classes()

# Get fund series information
series = vanguard_index.get_series()
if series:
    print(f"Series: {series.name} [{series.series_id}]")
    
# Get portfolio holdings
portfolio = vanguard_index.get_portfolio()
if not portfolio.empty:
    print(portfolio.head())
```

### Fund Class and Series Information

Access detailed fund structure information:

```python
from edgar.entity import get_fund

# Get a fund by CIK or ticker
fund = get_fund("0000036405")  # Vanguard fund

# Get fund series information
series = fund.get_series()
if series:
    # Get classes within this series
    classes = series.get_classes()
    for cls in classes:
        print(f"Class: {cls.name} - {cls.ticker}")
        
# Get filings for a specific fund class
if classes:
    class_filings = classes[0].get_filings(form="N-CSR")
    latest_report = class_filings.latest()
```

## Factory Functions

The package provides convenient factory functions for creating entities:

```python
from edgar.entity import get_entity, get_company, get_fund

# Get any entity type (auto-detection)
entity = get_entity("0000320193")

# Get specifically a company
company = get_company("AAPL")

# Get a fund or fund class
fund_or_class = get_fund("VFINX")
```

## Search Functionality

Search for entities by name or ticker:

```python
from edgar.entity import find_company

# Search for companies
results = find_company("Apple")

# Access search results
if not results.empty:
    first_match = results[0]  # Returns a Company object
    print(f"Found: {first_match.data.name} ({first_match.get_ticker()})")
    
    # Display all matches
    print(results)  # Uses rich formatting in terminals
```

## XBRL Facts and Concepts

Access structured XBRL data for companies:

```python
# Get all XBRL facts for a company
facts = company.get_facts()

```

## Migration from Previous API

### From entities.py to entity package

If you're migrating from the old `entities.py` API, simply update your imports from:

```python
from edgar.entities import Entity, Company
```

To:

```python
from edgar.entity import Entity, Company
```

Most method signatures remain unchanged, but specialized methods are now available on the appropriate classes.

### From funds.py to entity package

If you're migrating from using the `funds.py` module, here's how to update your code:

```python
# Old code using funds.py:
from edgar.funds import get_fund

fund_info = get_fund("VFINX")
company_cik = fund_info.company_cik
fund_name = fund_info.name
fund_ticker = fund_info.ticker
```

```python
# New code using entity package:
from edgar.entity import get_fund

fund_or_class = get_fund("VFINX")

# Check if we got a fund or fund class
if hasattr(fund_or_class, 'fund'):
    # It's a fund class
    fund_class = fund_or_class
    fund = fund_class.fund
    fund_name = fund_class.name
    fund_ticker = fund_class.ticker
else:
    # It's a fund
    fund = fund_or_class
    fund_name = fund.data.name
    fund_ticker = fund.get_ticker()

company_cik = fund.cik
```

Key differences:
1. `get_fund()` now returns either a `Fund` or `FundClass` object depending on the input
2. Fund identifiers (CIK, ticker, series ID, class ID) are handled transparently 
3. More object-oriented API with proper type information
4. Better integration with the rest of the entity package

## Advanced Usage

### Creating Entities from Local Files

For testing or offline use, entities can be created from local JSON files:

```python
from edgar.entity.submissions import create_entity_from_file, create_company_from_file

# Create a generic entity
entity = create_entity_from_file("path/to/submissions.json")

# Create specifically a company
company = create_company_from_file("path/to/submissions.json")
```

### Working with Local Storage

Configure the library to use local storage for improved performance:

```python
import os
os.environ["EDGAR_USE_LOCAL_DATA"] = "true"

# Now all API calls will use local storage when available
company = Company("AAPL")
```

## Performance Considerations

- Entity data is lazily loaded upon first access
- Filing history follows a special lazy-loading pattern:
  - Initially, only the most recent filings are loaded
  - When `get_filings()` is called with `trigger_full_load=True` (default), additional historical filings are loaded
  - Subsequent calls use the cached data