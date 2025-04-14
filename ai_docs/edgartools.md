# Edgartools

This is the documentation for **edgartools** a Python library for working with SEC filings and data

# Installing

```bash
pip install edgartools
```

# Using

1. Import from the main module `edgar`
2. Set your identity to identify yourself to the SEC

```python
from edgar import *
set_identity("user@domain.com") # Identify yourself to the SEC 
```

# Major Components

1. **Company API** - Work with public companies and their filings
2. **Filings API** - Search and filter SEC filings
3. **Fund Entity API** - Work with investment funds and their structure
4. **XBRL API** - Extract and analyze financial data
5. **Ownership API** - Track insider transactions

## High Level Patterns

- Get a `Company` then get their `Filings`
- Get `Filings` and then filter
- Select a `Filing` and convert it to a `Data Object`
- Find a `Filing` and convert it to a `Data Object`

## Get a Company 

---
### By ticker or CIK

```python
company = Company("AAPL")
# OR CIK
company = Company("0000320193") # OR Company(320193)
```

### Get company filings

The company has a `filings` property populated from the 1000 most recent filings for the company.

To get all filings for a company use `get_filings`:
```python
filings = company.get_filings()
```

### Filter by form type

To get all 10-K filings for a company:
```python
filings = company.get_filings(form='10-K')
```

## Get Filings

---

## Get filings
To get all filings 
```python
filings = get_filings()
```

By default this gets filings for current year and quarter.


## Filtering

Filtering can be done using parameters of `get_filings` or by using the `filter` method on a `Filings` object.

### Using `get_filings` parameters 

Filtering can be done using parameters of the `get_filings` function. 

```python
def get_filings(year: Optional[Years] = None, # The year of the filing
                quarter: Optional[Quarters] = None, # The quarter of the filing
                form: Optional[Union[str, List[IntString]]] = None, # The form or forms as a string e.g. "10-K" or a List ["10-K", "8-K"]
                amendments: bool = True, # Include filing amendments e.g. "10-K/A"
                filing_date: Optional[str] = None, # The filing date to filter by in YYYY-MM-DD format
                index="form", # The index type - "form" or "company" or "xbrl") -> Optional[Filings]:
```

### Using the `filter` method

Filtering can also be done using the `filter` method on a `Filings` object after retrieval.
Since this is downstream from the `get_filings` function, it will be affected by the filings already retrieved and possibly filtered in `get_filings`.


```python
    def filter(self, *,
        form: Optional[Union[str, List[IntString]]] = None, # The form or list of forms to filter by
        amendments: bool = None, # Whether to include amendments to the forms e.g. include "10-K/A"
        filing_date: Optional[str] = None, # The filing date as `YYYY-MM-DD`, `YYYY-MM-DD:YYYY-MM-DD`, or `YYYY-MM-DD:` or `:YYYY-MM-DD`
        date: Optional[str] = None, # Alias for filing_date
        cik: Union[IntString, List[IntString]] = None, # CIK or list of CIKs
        exchange: Union[str, List[str], Exchange, List[Exchange]] = None, # The exchange or list of exchanges values: Nasdaq|NYSE|OTC|CBOE
        ticker: Union[str, List[str]] = None, # The ticker or list of tickers
        accession_number: Union[str, List[str]] = None # The accession number or list of accession numbers
               ) -> Optional['Filings']:

```

# Fund Entity API

The Fund Entity API provides a comprehensive suite of tools for working with investment fund data from the SEC. It implements a domain model that reflects the hierarchical structure of investment funds:

- **Fund Company** → **Fund Series** → **Share Classes**

## Core Classes

```python
from edgar.funds import FundCompany, FundSeries, FundClass, find_fund

# Core classes for the fund hierarchy
company = FundCompany("0000102909")  # Vanguard (top-level entity)
series = FundSeries("S000584", "500 Index Fund", company)  # A specific fund product/strategy
fund_class = FundClass("C000065928", company, name="Admiral Shares", ticker="VFIAX")  # A specific share class
```

## Smart Factory Function

```python
from edgar.funds import find_fund

# Returns a FundClass for ticker symbols and class IDs
fund_class = find_fund("VFIAX")  # By ticker
fund_class = find_fund("C000065928")  # By class ID

# Returns a FundSeries for series IDs
fund_series = find_fund("S000584")

# Returns a FundCompany for CIKs
fund_company = find_fund("0000102909")
```

## Specialized Getter Functions

```python
from edgar.funds import get_fund_company, get_fund_series, get_fund_class, get_class_by_ticker, get_series_by_name

# Get entities directly by their identifiers
company = get_fund_company("0000102909")  # By CIK
series = get_fund_series("S000584")  # By series ID
fund_class = get_fund_class("C000065928")  # By class ID
fund_class = get_class_by_ticker("VFIAX")  # By ticker

# Find a series by name within a company
series = get_series_by_name(102909, "500 Index Fund")
```

## Navigation Between Entities

```python
# Start with a fund class
fund_class = find_fund("VFIAX")

# Navigate to parent series
series = fund_class.series
print(f"Parent series: {series.name}")

# Navigate to fund company
company = fund_class.company  # or fund_class.fund_company for backward compatibility
print(f"Fund company: {company.data.name}")

# Get all series offered by the company
all_series = company.get_series()

# Get all classes in a series
series_classes = series.get_classes()
```

For a complete guide to the Fund Entity API, see the [Fund Entity API Migration Guide](entity_migration_guide.md).


