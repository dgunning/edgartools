# Using the Company API

With the company API you find a company using the **cik** or **ticker**. 
From the company you can access all their historical **filings**,
and a dataset of the company **facts**.
The SEC's company API also supplies a lot more details about a company including industry, the SEC filer type,
the mailing and business address and much more.

## Find a company using the cik
The **cik** is the id that uniquely identifies a company at the SEC.
It is a number, but is sometimes shown in SEC Edgar resources as a string padded with leading zero's.
For the edgar client API, just use the numbers and omit the leading zeroes.

```python
company = Company.for_cik(1318605)
```
![expe](https://raw.githubusercontent.com/dgunning/edgartools/main/expe.png)



## Find a company using ticker

You can get a company using a ticker e.g. **SNOW**. This will do a lookup for the company cik using the ticker, then load the company using the cik.
This makes it two calls versus one for the cik company lookup, but is sometimes more convenient since tickers are easier to remember that ciks.

Note that some companies have multiple tickers, so you technically cannot get SEC filings for a ticker.
You instead get the SEC filings for the company to which the ticker belongs.

The ticker is case-insensitive so you can use `Company.for_ticker("snow")`
or `Company.for_ticker("SNOW")`
```python
snow = Company.for_ticker("snow")
```

![snow inspect](https://raw.githubusercontent.com/dgunning/edgartools/main/snow-inspect.png)



```python
Company.for_cik(1832950)
```

## Get filings for a company
To get the company's filings use `get_filings()`. This gets all the company's filings that are available from the Edgar submissions endpoint.

```python
company.get_filings()
```
## Filtering filings
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


### The CompanyFilings class
The result of `get_filings()` is a `CompanyFilings` class. This class contains a pyarrow table with the filings
and provides convenient functions for working with filings.
You can access the underlying pyarrow `Table` using the `.data` property

```python
filings = company.get_filings()

# Get the underlying Table
data: pa.Table = filings.data
```

### Get a filing by index
To access a filing in the CompanyFilings use the bracket `[]` notation e.g. `filings[2]`
```python
filings[2]
```

### Get the latest filing

The `CompanyFilings` class has a `latest` function that will return the latest `Filing`. 
So, to get the latest **10-Q** filing, you do the following
```python
# Latest filing makes sense if you filter by form  type e.g. 10-Q
snow_10Qs = snow.get_filings(form='10-Q')
latest_10Q = snow_10Qs.latest()

# Or chain the function calls
snow.get_filings(form='10-Q').latest()
```


## Get company facts

Facts are an interesting and important dataset about a company accumlated from data the company provides to the SEC.
Company facts are available for a company on the Company Facts`f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010}.json"`
It is a JSON endpoint and `edgartools` parses the JSON into a structured dataset - a `pyarrow.Table`.

### Getting facts for a company
To get company facts, first get the company, then call `company.get_facts()`
```python
company = Company.for_ticker("SNOW")
company_facts = company.get_facts()
```
The result is a `CompanyFacts` object which wraps the underlying facts and provides convenient ways of working
with the facts data. To get access to the underyling data use the `facts` property.

You can get the facts as a pandas dataframe by calling `to_pandas`

```python
df = company_facts.to_pandas()
```

Facts differ among companies. To see what facts are available you can use the `facts_meta` property.

### Getting the facts as a DuckDB table
Ypu can convert the facts to a DuckDB database which allows you to query the facts using SQL.

```python
    company_facts: CompanyFacts = get_company_facts(1318605)
    db = company_facts.to_duckdb()
    df = db.execute("""
    select * from facts
    """).df()
```



# Working with a Filing

Once you have a filing you can do many things with it including getting the html text of the filing, get xbrl or xml, or list all the files in the filing.

## Getting the html text of a filing

```python
html = filing.html()
```


To get the html text of the filing call `filing.html()`

## Get the Homepage Url

`filing.homepage_url` returns the homepage url of the filing. This is the main index page which lists
all the files attached in the filing

## Get the filing homepage

To get access to all the documents on the filing you would call `filing.get_homepage()`.
This gives you access to the `FilingHomepage` class that you can use to list all the documents
and datafiles on the filing.
