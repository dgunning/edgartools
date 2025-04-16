# Edgartools Documentation

**edgartools** is a Python library for navigating SEC filings. 


# Getting Started

---

## 1. Install
```bash
pip install edgartools
```
There are frequent releases so it is a good idea to use `pip install -U edgartools` to get new features and bug fixes.
That being said we try to keep the API stable and backwards compatible.

If you prefer **uv** instead of **pip** you can use the following command:

```bash
uv pip install edgartools
```

## 2. Import edgar

The main way to use the library is to import everything with `from edgar import *`. This will give you access to most of the functions and classes you need.

```
from edgar import *
```

If you prefer a minimal import you can use the following:


## 3. Set your identity

Before you can access the SEC Edgar API you need to set the identity that you will use to access Edgar.
This is usually your **name** and **email**, but you can also just use an email.

You can set your identity in Python before you start using the library. 

### Setting your identity in Python
```python
from edgar import *
set_identity("mike.mccalum@indigo.com")
```

### Setting your identity using an environment variable
You can also set your identity using an environment variable. This is useful if you are using the library in a script or notebook.

```bash 
export EDGAR_IDENTITY="mike.mccalum@indigo.com"
```
# Usage

---

## Getting Filings
The library is designed to be easy to use and flexible. You can start by getting all filings for the current year and quarter with `get_filings()`.

```python
filings = get_filings()
```

![Get Filings Image](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/get_filings.png)

You can expand beyond the current year and quarter by using the parameters of the `get_filings` function.

For example you can specify the year you want to get filings for:

```python
filings = get_filings(year=2021)
```
For more details on filtering filings see the **[Filtering Filings](https://edgartools.readthedocs.io/en/latest/filtering-filings/)** docs

### Selecting a filing

You can select a filing using the `[]` operator. For example to get the third filing in the list:

```python
filing = filings[3]
```

### Paginating filings
The `Filings` object is a container for a list of filings. The list of filings can  be large but by default you can only see the first page of filings. 

To change the page, you can paginate filings using the `next` and `prev` methods. For example:

```python
filings = get_filings()
filings.next()
filings.previous()
```

### Looping through filings

You can loop through filings using the `for` loop. For example:

```python

filings = get_filings()
for filing in filings:
    # Do something with the filing
```

### Getting Related Filings

Filings can be related to other filings using the file number. In some cases this relationship can be meaningful, as in they represent a group of filings for a specific securities offering.
The link between the filing is via the `file_number` attribute of the filing, which is an identifier that the SEC uses to group filings.

You can get related filings using the `get_related_filings` method. For example:

```python
filing = get_filing('0000320193-22-000002')
filings = filing.related_filings()
```

## Getting a Company

You can start by getting a company by CIK or Ticker with `Company()`. For example:

```python
c = Company("AAPL")
filings = c.filings
```

You can also get a company by CIK. For example:

```python
c = Company("0000320193")
filings = c.filings
```

To get a Company by ticker, the library first does a lookup of the CIK for the ticker and then gets filings for the CIK. So if you know the CIK, it is faster to use that directly.

### Company Filings

You can get the filings for a company by using the `filings` property. For example:

```python
filings = c.filings     
```

This property returns a `Filings` object that you can use to filter and manipulate the filings.
Initially the `filings` property lists around 1000 filings for the company that were returned from the API call to the SEC.
Normally this is OK since these are the 1000 most recent filings. However, some companies have more than 1000 filings, and you might need to get older filings.
To trigger the retrieval of older filings you can use the `get_filings()` method. For example:

```python
filings = c.get_filings()
```

### Getting Company Facts

You can get facts for a company using the `get_facts()` method. For example:

```python
facts = c.get_facts()
```

The result is an `EntityFacts` object that wraps the data returned from the SEC API. To get the data as a dataframe
use the `to_pandas()` method. For example:

```python
facts_df = facts.to_pandas()
```


### Getting Company Financials

You can get financials for a company using the `financials` property. For example:

```python
financials = c.financials
financials.income_statement 
```

## Viewing unpublished filings


The SEC publishes the filing indexes week nights by 10:30 PM EST. To get the latest filings not yet in the index use the `get_latest_filings` function. For example:

```python
filings = get_latest_filings()
```
