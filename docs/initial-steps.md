# Initial Steps

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
```

You can also get a company by CIK. For example:

```python
c = Company("0000320193")
```

To get a Company by ticker, the library first does a lookup of the CIK for the ticker and then gets filings for the CIK. So if you know the CIK, it is faster to use that directly.

### Company Filings

You can get the filings for a company by using the `get_filings()` function. For example:

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

You can get financials for a company using the `get_financials` function. For example:

```python
financials = c.get_financials()
financials.income_statement()
```

## Viewing unpublished filings


The SEC publishes the filing indexes week nights by 10:30 PM EST. To get the latest filings not yet in the index use the `get_latest_filings` function. For example:

```python
filings = get_latest_filings()
```
