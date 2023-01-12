# Using the Filings API

The **Filings API** allows you to get the Edgar filing indexes published by the SEC.
You would use it to get a bulk dataset of SEC filings for a given time period. With this dataset, you could filter by form type, by date or by company, 
though if you intend to filter by a singe company, you should use the Company API.

## The get_filings function
The main way to use the Filings API is by `get_filings`

`get_filings` accepts the following parameters
- **year** a year `2015`, a List of years `[2013, 2015]` or a `range(2013, 2016)` 
- **quarter** a quarter `2`, a List of quarters `[1,2,3]` or a `range(1,3)` 
- **index** this is the type of index. By default it is `"form"`. If you want only XBRL filings use `"xbrl"`. 
You can also use `"company"` but this will give you the same dataset as `"form"`, sorted by company instead of by form

### Get filings for 2021

```python
filings = get_filings(2021)
```

![Filings in 2021](https://raw.githubusercontent.com/dgunning/edgartools/main/filings_2021.jpg)

### Get filings for 2021 quarter 4
Instead of getting the filings for an entire year, you can get the filings for a quarter.
```python
filings = get_filings(2021, 4)
```

### Get filings between 2010 and 2019
You can get the filings for a range of years, since the `year` parameter accepts a value, a list or a range.
```python
filings = get_filings(range(2010, 2020))
```

### Get XBRL filings for 2022
```python
filings = get_filings(2022, index="xbrl")
```

## The Filings class

The `get_filings` returns a `Filings` class, which wraps the data returned and provide convenient ways for working with filings.

### Convert the filings to a pandas dataframe

The filings data is stored in the `Filings` class as a `pyarrow.Table`. You can get the data as a pandas dataframe using
`to_pandas`
```python
df = filings.to_pandas()
```
