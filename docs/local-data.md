# Dowloading to Local Storage

When you use **edgartools** to get Company, or the html content of a filing, this usually results in one of more requests to the SEC. However, you can download data in bulk to local storage to minimize these requests and speed up processing. 

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
def download_edgar_data(submissions: bool = True,
                        facts: bool = True,
                        reference: bool = True):
```

## Downloading Complete Filings

You can download filings to local storage by calling the `download_filings()` function.
This will download for each filing a complete text file that contains all the attachments for that filing.

These will be placed in the directory `EDGAR_LOCAL_DATA_DIR/filings/YYYYMMDD`

### Accessing the attachments




