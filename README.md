# edgartools 

[![PyPI - Version](https://img.shields.io/pypi/v/edgar.svg)](https://pypi.org/project/edgar)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/edgar.svg)](https://pypi.org/project/edgar)

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
            <li><a href="#using-the-company-api">Using the Company API</a></li>
            <li><a href="#using-the-filings-api">Using the Filings API</a></li>
      </ul>
    </li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

# About the project

**`edgartools`** makes working with Edgar filings easy and fun.

## Demo

Get the Common Shares Issued amount from Snowflake's latest 10-Q filing

```python
(Company.for_ticker("SNOW")
 .get_filings(form="10-Q")
 .latest()
 .xbrl()
 .to_duckdb().execute(
    """select fact, value, units from facts 
       where fact = 'CommonStockSharesIssued' limit 1
    """
).df()
 )
```

![Common Shares Issued](https://github.com/dgunning/edgartools/blob/main/common-shares-issued.png)

## Features

- Download listings of Edgar filing by year, quarter since 1994
- Select an individual filing and download the html, XML or content of any attached file
- View a filing XBRL as a dataframe and query it with SQL
- Search for company by ticker or CIK
- Get a company's filings 
- Get a dataset of company's **facts** e.g. **CommonSharesOutstanding**
- Query a company's fact as SQL

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
```bash
export EDGAR_IDENTITY="Michael Mccallum mcalum@gmail.com"
```
Alternatively, you can call `set_identity` which does the same thing.

```python
from edgar import set_identity
set_identity("Michael Mccallum mcalum@gmail.com")
```


For more detail see https://www.sec.gov/os/accessing-edgar-data

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
company = Company.for_cik(1318605)
```
![expe](https://github.com/dgunning/edgartools/blob/main/expe.png)



### Find a company using ticker

You can get a company using a ticker e.g. **SNOW**. This will do a lookup for the company cik using the ticker, then load the company using the cik.
This makes it two calls versus one for the cik company lookup, but is sometimes more convenient since tickers are easier to remember that ciks.

Note that some companies have multiple tickers, so you technically cannot get SEC filings for a ticker.
You instead get the SEC filings for the company to which the ticker belongs.

The ticker is case-insensitive so you can use `Company.for_ticker("snow")`
or `Company.for_ticker("SNOW")`
```python
snow = Company.for_ticker("snow")
```

![snow inspect](https://github.com/dgunning/edgartools/blob/main/snow-inspect.png)
### 


```python
Company.for_cik(1832950)
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

## Working with a Filing

Once you have a filing you can do many things with it including getting the html text of the filing, get xbrl or xml, or list all the files in the filing.

### Getting the html text of a filing

```python
html = filing.html()
```


To get the html text of the filing call `filing.html()`

### Get the Homepage Url

`filing.homepage_url` returns the homepage url of the filing. This is the main index page which lists
all the files attached in the filing

### Get the filing homepage

To get access to all the documents on the filing you would call `filing.get_homepage()`.
This gives you access to the `FilingHomepage` class that you can use to list all the documents
and datafiles on the filing.


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

## Using the Filings API

The **Filings API** allows you to get the Edgar filing indexes published by the SEC.
You would use it to get a bulk dataset of SEC filings for a given time period. With this dataset, you could filter by form type, by date or by company, 
though if you intend to filter by a singe company, you should use the Company API.

### The get_filings function
The main way to use the Filings API is by `get_filings`

`get_filings` accepts the following parameters
- **year** a year `2015`, a List of years `[2013, 2015]` or a `range(2013, 2016)` 
- **quarter** a quarter `2`, a List of quarters `[1,2,3]` or a `range(1,3)` 
- **index** this is the type of index. By default it is `"form"`. If you want only XBRL filings use `"xbrl"`. 
You can also use `"company"` but this will give you the same dataset as `"form"`, sorted by company instead of by form

#### Get filings for 2021

```python
filings = get_filings(2021)
```

#### Get filings for 2021 quarter 4
```python
filings = get_filings(2021, 4)
```

#### Get filings between 2010 and 2019
```python
filings = get_filings(range(2010, 2020))
```

#### Get XBRL filings for 2022
```python
filings = get_filings(2022, index="xbrl")
```

### The Filings class

The `get_filings` returns a `Filings` class, which wraps the data returned and provide convenient ways for working with filings.

#### Convert the filings to a pandas dataframe

The filings data is stored in the `Filings` class as a `pyarrow.Table`. You can get the data as a pandas dataframe using
`to_pandas`
```python
df = filings.to_pandas()
```

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

# Contributing


# License

`edgartools` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Contact

[LinkedIn](https://www.linkedin.com/in/dwight-gunning-860124/)