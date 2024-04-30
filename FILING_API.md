# Using the Filings API

---

## Getting filings
```python

# Get filings for the current year and quarter
filings = get_filings() 

# Get filings for 2022
filings = get_filings(2022)                 # OR filings = get_filings(year=2022)

# Get filings for 2022 quarter 4
filings = get_filings(2022, 4)              # OR filings = get_filings(year=2022, quarter=4)

# Get filings for 2020, 2021 and 2022
filings = get_filings([2020, 2021, 2022])   # OR filings = get_filings(year=range(2020, 2023))

# Get filings for 2020 quarters 1 and 2
filings = get_filings(2020, quarter=[1,2])
```
![Get filings](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/get_filings.jpg)



## Filtering filings

```python
# Filter for form D
filings.filter(form="D")

# Filter for form 10-K and 10-Q 
filings.filter(form=["10-K", "10-Q"])

# When you filter by form e.g. "D" it includes amendments e.g. "D\A". You can omit amendments
filings.filter(form="D", amendments=False)

# Filter by filing_date. date and filing_date mean the same thing
# Get all filings on 2023-02-23
filings.filter(date="2023-02-23")                      
# OR
filings.filter(filing_date="2023-02-23")

# Filter to get all filings between 2023-01-23 and 2023-02-23     
filings.filter(date="2023-01-23:2023-02-23")

# Filter to get all filings since 2023-01-23   
filings.filter(date="2023-01-23")

# Filter to get all filings before 2023-02-23     
filings.filter(date=":2023-02-23")
```

## Combining getting and filtering
```python
get_filings(2022, form="D")
```

## Convert the filings to a pandas dataframe

The filings data is stored in the `Filings` class as a `pyarrow.Table`. You can get the data as a pandas dataframe using
`to_pandas`
```python
df = filings.to_pandas()
```


# Navigating filings

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

![Get next filings](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/filings_next.jpg)

## Getting the latest filings

You can get the latest **n** filings by filing_date from a filings using `filings.latest()`.

If you provide the parameter `n` it will return the latest `n` filings.

```python
filing = filings.latest(n=5)
filing
```
![Latest filings](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/latest_filings.jpg)


If you omit this parameter, or set `n=1` it will return a single `Filings object.

```python
filing = filings.latest()
filing
```
![Latest filing](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/latest_filing.jpg)


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
![Filter with amendments](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/filter_amendments.jpg)

## Working with a single filing

You can get a single filing from the filings using the bracket operator `[]`, 
specifying the index of the filing. The index is the value displayed in the leftmost
position in the filings table. For example, to get the **10-Q** for **Costco** in the table above
use `filings[3]`

```python
filing = filings[3]
```

![Costco 10Q filing](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/costco_10Q.jpg)

### View the filing homepage
You can view the filing homepage in the terminal using `filing.homepage`

This gives you access to the `FilingHomepage` class that you can use to list all the documents
and datafiles on the filing.

```python
filing.homepage
```
![Filing homepage](https://raw.githubusercontent.com/dgunning/edgartools/main/docs/images/filing_homepage.jpg)

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

### View the filing as Markdown
You can view the filing's HTML content as markdown in the console using `view()`. It works for all filing types
but can be a little slow for filings with large HTML files
```python
filing.view()
```

### Get the filing's html
You can get the html content of the filing using`.html()`
```python
filing.html()
```

### Get the filing's html as Markdown
You can get the html content as markdown using`.markdown()`
```python
filing.markdown()
```