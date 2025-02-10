# About edgartools 

**edgartools** is a Python library for navigating SEC filings and data. With edgartools you can

- Find and view any SEC filing since 1994
- Locate any company and see its filings
- Automatically extract data from **XBRL**, **HTML**, **SGML**, and **XML**
- Get reference data like **CUSIP**, **CIK**, and **Ticker** for companies


# Install

---

### 1. Install using pip

```bash
pip install edgartools
```

### 2. Import and set identity  

Use `from edgar import *` to import most of what you need. 

### 3. Set your identity

Before you can access the SEC Edgar API you need to set the identity that you will use to access Edgar.
This is usually your **name** and **email**, but you can also just use an email.

```python
from edgar import *
set_identity("mike.mccalum@indigo.com")
```

# Usage

---

## Starting with a Company

You can start by getting a company by CIK or Ticker with `Company()`. For example:

```python
c = Company("AAPL")
filings = c.get_filings()
```

## Starting with filings

You can start by getting filings with `get_filings`. By default this will get all filings for the current year and quarter, but there are a lot of filtering options. 

```python
filings = get_filings()
```

The `get_filings` function takes the following parameters:

- **`year`** - A year or list of years to get filings for. Defaults to the current year.
- **`quarter`** - The quarter or list of quarters to get filings for. Defaults to the current quarter.
- **`form`** - The form to get filings for. Default to all forms.
- **`amendments`** - Whether to include amended filings e.g. include "10-K/A". Default is True.
- **`filing_date`** - The filing date to get filings for.
- **`index`** - Use `index="xbrl"` to limit to only filings published using XBRL.


### Examples

```python

from edgar import get_filings

# Get filings for 2021
filings_ = get_filings(2021) 

# Get filings for 2021 Q4
filings_ = get_filings(2021, 4) 

# Get filings for 2021 Q3 and Q4
filings_ = get_filings(2021, [3,4]) 

# Get filings for 2020 and 2021
filings_ = get_filings([2020, 2021]) 

# Get filings for Q4 of 2020 and 2021
filings_ = get_filings([2020, 2021], 4) 

# Get filings between 2010 and 2021 - does not include 2021
filings_ = get_filings(range(2010, 2021)) 

# Get filings for 2021 Q4 for form D
filings_ = get_filings(2021, 4, form="D") 

# Get filings for 2021 Q4 on "2021-10-01"
filings_ = get_filings(2021, 4, filing_date="2021-10-01") 

# Get filings for 2021 Q4 between "2021-10-01" and "2021-10-10"
filings_ = get_filings(2021, 4, filing_date="2021-10-01:2021-10-10") 
                                                                       
```

## Viewing unpublished filings

The SEC publishes the filing indexes week nights by 10:30 PM EST. To get the latest filings not yet in the index use the `get_latest_filings` function. For example:

```python
get_latest_filings()
```
