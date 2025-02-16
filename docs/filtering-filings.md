# Filtering filings

Filings can be filtered in many different ways like by `form`, `date`, `CIK`, `ticker`, and **accession number**.
You also filter while getting filings using the `get_filings` function or after getting filings using the `filter` method.

For the most part these approaches will give identical results, except that with get_filings you are filtering from all available filings in the SEC, while with `filter` you are reducing the nu,ber of filings in a `Filings` object.


## Filtering using parameters of `get_filings`
You can filter using parameters of the `get_filings` function. 

### Get filings by form

To get filings of a specific form type like 10-K, you can use the `form` parameter. For example:
```python
filings = get_filings(form='10-K')
```

The `form` can also be a list of forms. For example:
```python
filings = get_filings(form=['10-K', '10-Q'])
```

By default the `amendments` parameter is set to `True` so that amended filings are included. You can set it to `False` to exclude amended filings. For example:
```python
filings = get_filings(form='10-K', amendments=False)
```


### Filtering by date

You can filter filings by date using the `filing_date` parameter. For example:
```python
filings = get_filings(filing_date='2022-01-01')
```

You can also filter by a range of dates. For example:
```python
filings = get_filings(filing_date='2022-01-01:2022-01-10')
```

You can filter up to a date. For example:
```python
filings = get_filings(filing_date=':2022-01-10')
```

as well as after a date. For example:
```python
filings = get_filings(filing_date='2022-01-10:')
```

#### More filtering examples

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
### Filtering by CIK

You can filter filings by CIK using the `cik` parameter to get all filings for a company. For example:
```python 
filings = get_filings(cik='0000320193')
```

### Filtering by ticker

You can filter filings by ticker using the `ticker` parameter. For example:
```python
filings = get_filings(ticker='AAPL')
```
Note that this first does a lookup of the CIK for the ticker and then gets filings for the CIK.
So if you know the CIK, it is better to use that directly.

### Filtering by exchange

You can filter companies using the `exchange` parameter. 

```python
filings = get_filings(exchange='NASDAQ')
```
There are the following exchanges available:

| Exchange |
|----------|
| Nasdaq   | 
| NYSE     | 
| CBOE     | 
| OTC      | 


## Filtering using `Filings.filter`

You can filter filings using the `filter` method after getting filings. This work mostly identically to filtering using `get_filings`.
The difference is that `filter` reduces from an existing `Filings` object rather that the entire SEC.

Example:
```python
filings().filter(form='10-K')
```


```python
    def filter(self, *,
        form: Optional[Union[str, List[IntString]]] = None,
        amendments: bool = None,
        filing_date: Optional[str] = None,
        date: Optional[str] = None,
        cik: Union[IntString, List[IntString]] = None,
        exchange: Union[str, List[str], Exchange, List[Exchange]] = None,
        ticker: Union[str, List[str]] = None,
        accession_number: Union[str, List[str]] = None) -> Optional['Filings']:

        :param form: The form or list of forms to filter by
        :param amendments: Whether to include amendments to the forms e.g. include "10-K/A"
        :param filing_date: The filing date
        :param date: An alias for the filing date
        :param cik: The CIK or list of CIKs to filter by
        :param exchange: The exchange or list of exchanges to filter by
        :param ticker: The ticker or list of tickers to filter by
        :param accession_number: The accession number or list of accession numbers to filter by
```



## Using `head`, `tail`, and `sample`
You can subset filings using the `head` and `tail` and `sample` methods. For example:

```python
filings = get_filings()
filings.head(10)
filings.tail(10)
filings.sample(10)
```