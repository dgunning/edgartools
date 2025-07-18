# Downloading to Local Storage

**edgartools** is designed for interactive query against **SEC Edgar** which means in normal operation it will make HTTP requests to the SEC website to retrieve data.
For example, when you call `company.submissions` or `filing.attachments`, it will make a request to the SEC to retrieve the data.

There are times when you want to minimize or even eliminate these requests.

1. You already have the data downloaded and want to use it locally
2. You want to speed up processing by avoiding network requests
3. You want to work offline or in an environment with limited internet access

For these cases, **edgartools** provides a way to download data to local storage and use it without making requests to the SEC.

This includes the following data


| Data                    | Descriptionn                                                       |
|-------------------------|--------------------------------------------------------------------|
| **Company Submissions** | Company metadata, their 1000 most recent filings                   |
| **Company Facts**       | Company facts                                                      |
| **Filing Attachments**  | Filing attachments                                                 |
| **Reference data**      | Reference data like company and mutual fund tickers, exchanges etc |


## Local Data Directory

The local data directory is the directory where the data is stored. The default directory is

`<USER_HOME>/.edgar`

You can change this directory by setting the `EDGAR_LOCAL_DATA_DIR` environment variable.

```bash
export EDGAR_LOCAL_DATA_DIR="/path/to/local/data"
```

## Using local storage
By default local storage is not used and the library will access the data from the SEC website. 
To use local storage you have to 

1. Download data using `download_edgar_data()`
2. Turn on local storage using the environment variable `EDGAR_USE_LOCAL_DATA` or by calling `use_local_storage()`


## Downloading data to local storage

You can download data to local storage by calling the `download_edgar_data()` function. 
The function takes the following parameters so you have the option to download only the data you need.

```python
download_edgar_data(submissions: bool = True,
                    facts: bool = True,
                    reference: bool = True):
    ...
```

## Downloading Complete Filings

You can download filings to local storage by calling the `download_filings()` function.
This will download for each filing a complete SGML text file that contains all the attachments for that filing.
These will be placed in the directory `EDGAR_LOCAL_DATA_DIR/filings/YYYYMMDD`. 

If local storage is enabled, edgartools will first check if the filing is available in local storage before making a request to the SEC.
This will speed up processing and for the most part calls like `html()` and `text()` will behave transparently.

Note that there are some differences between local attachments and attachments when downloaded from the SEC.

### Downloading by dates

The `download_filings(filing_date)` function accepts a filing date that can be a single date or a range of dates.
The date format must be `YYYY-MM-DD` or `YYYY-MM-DD:YYYY-MM-DD`. You can also use open ended ranges like `YYYY-MM-DD:`  
or `:YYYY-MM-DD`. 

Note that downloading filing attachment files can take a long time so be prepared when downloading for a range of dates.


## Using Filings to filter which filings to download

Normal usage of the `download_filings()` function will download all filings for the given date range.
If you want to filter which filings to download, you can use the `Filings` class to create a query that filters the filings based on various criteria like form type, company name, etc.

For example, to download all 10-K filings for companies on the **NYSE** you can use the following code:
```python
from edgar import Filings
filings = get_filings(form="10-K").filter(exchange="NYSE")
filings.download()
```

Note that this will still download the bulk filing files but on save it will filter and save only the filings that match the query.
This means that there will be no difference in time saved but it will save disk space as only the relevant filings will be saved.





