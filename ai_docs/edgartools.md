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




