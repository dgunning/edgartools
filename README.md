

![edgar-tools-logo](https://raw.githubusercontent.com/dgunning/edgartools/main/images/edgar-tools.png)

[![PyPI - Version](https://img.shields.io/pypi/v/edgartools.svg)](https://pypi.org/project/edgartools)
![GitHub last commit](https://img.shields.io/github/last-commit/dgunning/edgartools)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/dgunning/edgartools/python-hatch-workflow.yml)
[![CodeFactor](https://www.codefactor.io/repository/github/dgunning/edgartools/badge)](https://www.codefactor.io/repository/github/dgunning/edgartools)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)
![GitHub](https://img.shields.io/github/license/dgunning/edgartools)
-----

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#demo">Demo</a></li>
        <li><a href="#features">Features</a></li>
      </ul>
    </li>
    <li>
        <a href="#installation">Installation</a>
    </li>
    <li>
        <a href="#usage">Usage</a>
        <ul>
            <li><a href="#setting-your-edgar-user-identity">Setting your Edgar user identity</a></li>
            <li><a href="#getting-filings">Getting Filings</a></li>
            <li><a href="#using-the-company-api">Using the Company API</a></li>
      </ul>
    </li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

# About the project

**`edgartools`** is one of the nicest looking EDGAR libraries out there.
You can query, filter and select any filing since 1994 and view the filing's html, text, xml or structured data.


## Demo

#### Get the latest 10 form D filings and view the first in the browser

```python
from edgar import *

# Get form D filings for the last quarter of 2022 
filings = get_filings(2022, 4, form="D")

# Get the latest 10 filings from the list 
latest_10_filings = filings.latest(10)

# Of the 10 latest filings open the 1st in the browser
latest_10_filings[0].open()
```
![10 D Filings](https://raw.githubusercontent.com/dgunning/edgartools/main/images/10_D_filings.jpg)


## Features

### Start with filings, filter down to a filing

- View filings since 1994 to today
- Filter filings by **form e.g. 10K**, **filing date** etc.
- Page through filings using **next()** and **prev()**
- Select and view a filing in the terminal, or open in the browser
- Download any file from any filing
- Parse XML for **Offering, Ownership** and other filing types
- Automatically parse a filing's XBRL into a pandas dataframe

### Start with a Company, get their filings and Facts
- Search for company by ticker or CIK
- View a company's filings
- Page through filings using **next()** and **prev()**
- Get a company **facts** e.g. **CommonSharesOutstanding** as a dataframe

# Installation

```console
pip install edgartools
```

# Usage


## Set your Edgar user identity

Before you can access the SEC Edgar API you need to set the identity that you will use to access Edgar.
This is usually your name and email, or a company name and email.
```bash
Sample Company Name AdminContact@<sample company domain>.com
```

The user identity is sent in the User-Agent string and the Edgar API will refuse to respond to your request without it.

EdgarTools will look for an environment variable called `EDGAR_IDENTITY` and use that in each request.
So, you need to set this environment variable before using it.

### Setting EDGAR_IDENTITY in Linux/Mac
```bash
export EDGAR_IDENTITY="Michael Mccallum mcalum@gmail.com"
```

### Setting EDGAR_IDENTITY in Windows Powershell
```bash
 $Env:EDGAR_IDENTITY="Michael Mccallum mcalum@gmail.com"
```
Alternatively, you can call `set_identity` which does the same thing.

```python
from edgar import set_identity
set_identity("Michael Mccallum mcalum@gmail.com")
```
For more detail see https://www.sec.gov/os/accessing-edgar-data


## Getting filings
To get started import from edgar and use the `get_filings` function.
```python
from edgar import *

filings = get_filings()
```

This gets the list of filings for the current year and quarter into a `Filings` object. 

![Get Filings](https://raw.githubusercontent.com/dgunning/edgartools/main/images/get_filings.jpg)

If you need a different date range you can specify a year or years and a quarter or quarters.
These are valid ways to specify the date range or filter by form or by filing date.

```python

    >>> filings = get_filings(2021) # Get filings for 2021

    >>> filings = get_filings(2021, 4) # Get filings for 2021 Q4

    >>> filings = get_filings(2021, [3,4]) # Get filings for 2021 Q3 and Q4

    >>> filings = get_filings([2020, 2021]) # Get filings for 2020 and 2021

    >>> filings = get_filings([2020, 2021], 4) # Get filings for Q4 of 2020 and 2021

    >>> filings = get_filings(range(2010, 2021)) # Get filings between 2010 and 2021 - does not include 2021

    >>> filings = get_filings(2021, 4, form="D") # Get filings for 2021 Q4 for form D

    >>> filings = get_filings(2021, 4, filing_date="2021-10-01") # Get filings for 2021 Q4 on "2021-10-01"

    >>> filings = get_filings(2021, 4, filing_date="2021-10-01:2021-10-10") # Get filings for 2021 Q4 between
                                                                            # "2021-10-01" and "2021-10-10"
```

### Convert the filings to a pandas dataframe

The filings data is stored in the `Filings` class as a `pyarrow.Table`. You can get the data as a pandas dataframe using
`to_pandas`
```python
df = filings.to_pandas()
```


## Navigating filings

The Filings object allows you to navigate through filings using `filings.next()` and `filings.prev()`. 
This shows you pages of the data - the page size is about 50. 

```python
# To see the next page of data
filings.next()

# To see the previous page
filings.prev()

# To see the current page
filings.current()
```

![Get next filings](https://raw.githubusercontent.com/dgunning/edgartools/main/images/filings_next.jpg)

## Getting the latest filings

You can get the latest **n** filings by filing_date from a filings using `filings.latest()`.

If you provide the parameter `n` it will return the latest `n` filings.

```python
filing = filings.latest(n=5)
filing
```
![Latest filings](https://raw.githubusercontent.com/dgunning/edgartools/main/images/latest_filings.jpg)


If you omit this parameter, or set `n=1` it will return a single `Filings object.

```python
filing = filings.latest()
filing
```
![Latest filing](https://raw.githubusercontent.com/dgunning/edgartools/main/images/latest_filing.jpg)


## Filtering filings

You can filter the filings object using te `filter()` function. This allows you to filter
by filing date, or by form.

### Filtering filings by date

To filter by filing date specify the filing date in **YYYY-MM-DD** format e.g. **2022-01-24**
(Note the parameters `date` and `filing_date` are equivalent aliases for each other)
```python
filings.filter(date="2021-01-24") # or filings.filter(filing_date="2021-01-24")
```
You can specify a filing date range using the colon

```python
filings.filter(date="2021-01-12:2021-02-28") 
```
To filter by dates before a specified date use `:YYYY-MM-DD'

```python
filings.filter(date=":2021-02-28") 
```

To filter by dates after a specified date use `YYYY-MM-DD:'

```python
filings.filter(date="2021-02-28:") 
```

### Filtering filings by form

You can filter filings by form using the `form` parameter. 

```python
filings.filter(form="10-K") 
```

To filter by form e.g. **10-K** and include form amendments use `amendments = True`. 

```python
filings.filter(form="10-K", amendments=True) 
```
![Filter with amendments](https://raw.githubusercontent.com/dgunning/edgartools/main/images/filter_amendments.jpg)

## Getting a single filing

You can get a single filing from the filings using the bracket operator `[]`, 
specifying the index of the filing. The index is the value displayed in the leftmost
position in the filings table. For example, to get the **10-Q** for **Costco** in the table above
use `filings[3]`

```python
filing = filings[3]
```

![Costco 10Q filing](https://raw.githubusercontent.com/dgunning/edgartools/main/images/costco_10Q.jpg)

### View the filing homepage
You can view the filing homepage in the terminal using `filing.homepage`

This gives you access to the `FilingHomepage` class that you can use to list all the documents
and datafiles on the filing.

```python
filing.homepage
```
![Filing homepage](https://raw.githubusercontent.com/dgunning/edgartools/main/images/filing_homepage.jpg)

### Open a filing

You can open the filing in your browser using `filing.open()`. This will work on environments with access to the browser, 
will probably not work on a remote server.
```python
filing.open()
```

### Open the Filing Homepage
You can open the filing homepage in the browser using `filing.homepage.open()`.
```python
filing.homepage.open()
```

### Working with XBRL filings

Some filings are in **XBRL (eXtensible Business Markup Language)** format. 
These are mainly the newer filings, as the SEC has started requiring this for newer filings.

If a filing is in XBRL format then it opens up a lot more ways to get structured data about that specific filing and also 
about the company referred to in that filing.

The `Filing` class has an `xbrl` function that will download, parse and structure the filing's XBRL document if one exists.
If it does not exist, then `filing.xbrl()` will return `None`.

The function `filing.xbrl()` returns a `FilingXbrl` instance, which wraps the data, and provides convenient
ways of working with the xbrl data.


```python
filing_xbrl = filing.xbrl()
```

![Filing homapage](https://raw.githubusercontent.com/dgunning/edgartools/main/images/10Q_xbrl.jpg)


#### Use DuckDB to query the filings

A conveient way to query the filings data is to use **DuckDB**. If you call the `to_duckdb` function, you get an in-memory
DuckDB database instance, with the filings registered as a table called `filings`.
Then you can work directy with the DuckDB database, and run SQL against the filings data.

In this example, we filter filings for **S-1** form types.

```python
db = filings.to_duckdb()
# a duckdb.DuckDBPyConnection

# Query the filings for S-1 filings and return a dataframe
db.execute("""
select * from filings where Form == 'S-1'
""").df()
```


## Using the Company API

With the company API you find a company using the **cik** or **ticker**. 
From the company you can access all their historical **filings**,
and a dataset of the company **facts**.
The SEC's company API also supplies a lot more details about a company including industry, the SEC filer type,
the mailing and business address and much more.

### Find a company using the cik
The **cik** is the id that uniquely identifies a company at the SEC.
It is a number, but is sometimes shown in SEC Edgar resources as a string padded with leading zero's.
For the edgar client API, just use the numbers and omit the leading zeroes.

```python
company = Company(1324424)
```
![expe](https://raw.githubusercontent.com/dgunning/edgartools/main/images/expe.png)



### Find a company using ticker

You can get a company using a ticker e.g. **SNOW**. This will do a lookup for the company cik using the ticker, then load the company using the cik.
This makes it two calls versus one for the cik company lookup, but is sometimes more convenient since tickers are easier to remember that ciks.

Note that some companies have multiple tickers, so you technically cannot get SEC filings for a ticker.
You instead get the SEC filings for the company to which the ticker belongs.

The ticker is case-insensitive so you can use `Company("snow")`
or `Company("SNOW")`
```python
snow = Company("snow")
```

![snow](https://raw.githubusercontent.com/dgunning/edgartools/main/images/snow.jpg)
### 


```python
Company(1832950)
```

### Get filings for a company
To get the company's filings use `get_filings()`. This gets all the company's filings that are available from the Edgar submissions endpoint.

```python
company.get_filings()
```
### Filtering filings
You can filter the company filings using a number of different parameters.

```python
class CompanyFilings:
    
    ...
    
    def get_filings(self,
                    *,
                    form: str | List = None,
                    accession_number: str | List = None,
                    file_number: str | List = None,
                    is_xbrl: bool = None,
                    is_inline_xbrl: bool = None
                    ):
        """
        Get the company's filings and optionally filter by multiple criteria
        :param form: The form as a string e.g. '10-K' or List of strings ['10-Q', '10-K']
        :param accession_number: The accession number that uniquely identifies an SEC filing e.g. 0001640147-22-000100
        :param file_number: The file number e.g. 001-39504
        :param is_xbrl: Whether the filing is xbrl
        :param is_inline_xbrl: Whether the filing is inline_xbrl
        :return: The CompanyFiling instance with the filings that match the filters
        """
```


#### The CompanyFilings class
The result of `get_filings()` is a `CompanyFilings` class. This class contains a pyarrow table with the filings
and provides convenient functions for working with filings.
You can access the underlying pyarrow `Table` using the `.data` property

```python
filings = company.get_filings()

# Get the underlying Table
data: pa.Table = filings.data
```

#### Get a filing by index
To access a filing in the CompanyFilings use the bracket `[]` notation e.g. `filings[2]`
```python
filings[2]
```

#### Get the latest filing

The `CompanyFilings` class has a `latest` function that will return the latest `Filing`. 
So, to get the latest **10-Q** filing, you do the following
```python
# Latest filing makes sense if you filter by form  type e.g. 10-Q
snow_10Qs = snow.get_filings(form='10-Q')
latest_10Q = snow_10Qs.latest()

# Or chain the function calls
snow.get_filings(form='10-Q').latest()
```


### Get company facts

Facts are an interesting and important dataset about a company accumlated from data the company provides to the SEC.
Company facts are available for a company on the Company Facts`f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010}.json"`
It is a JSON endpoint and `edgartools` parses the JSON into a structured dataset - a `pyarrow.Table`.

#### Getting facts for a company
To get company facts, first get the company, then call `company.get_facts()`
```python
company = Company("SNOW")
company_facts = company.get_facts()
```
The result is a `CompanyFacts` object which wraps the underlying facts and provides convenient ways of working
with the facts data. To get access to the underyling data use the `facts` property.

You can get the facts as a pandas dataframe by calling `to_pandas`

```python
df = company_facts.to_pandas()
```

Facts differ among companies. To see what facts are available you can use the `facts_meta` property.

#### Getting the facts as a DuckDB table
Ypu can convert the facts to a DuckDB database which allows you to query the facts using SQL.

```python
    company_facts: CompanyFacts = get_company_facts(1318605)
    db = company_facts.to_duckdb()
    df = db.execute("""
    select * from facts
    """).df()
```



# Contributing

Contributions are welcome! We would love to hear your thoughts on how this library could be better at working with SEC Edgar.

## Reporting Issues
We use GitHub issues to track public bugs. 
Report a bug by [opening a new issue](https://github.com/dgunning/edgartools/issues); it's that easy!

## Making code changes
- Fork the repo and create your branch from master.
- If you've added code that should be tested, add tests.
- If you've changed APIs, update the documentation.
- Ensure the test suite passes.
- Make sure your code lints.
- Issue that pull request!



# License

`edgartools` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Contact

[LinkedIn](https://www.linkedin.com/in/dwight-gunning-860124/)