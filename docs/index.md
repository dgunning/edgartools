# Overview

**edgartools** is a library for working with SEC Edgar filings.
It has a lot of convenient features for working with filings. 
You can use it to download listing of filings, single filings as well as 
parse XML and XBRL into structured data.

# Getting Started
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


# Getting Filings

You can get filings using the Filings API or the Company API 

# Working with an individual Filing

Once you have retrieved Filings you can access individual filings using the bracket `[]` notation.
```python
filings = get_filings(2021)
filing = filings[0]
```
![Filings in 2021](https://raw.githubusercontent.com/dgunning/edgartools/main/images/filings_2021.jpg)
Pay attention to the index value displayed for the filings. This is the value you 
will use to get the individual filing.
```python
filing = filings[0]
```
![A single filing](https://raw.githubusercontent.com/dgunning/edgartools/main/images/single_filing.png)

## Open a filing

You can open the filing in your browser using `filing.open()`
```python
filing.open()
```

## Open the Filing Homepage
You can open the filing homepage in the browser using `filing.open_homepage()`
```python
filing.open()
```