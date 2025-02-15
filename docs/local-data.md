# Downloading to Local Storage

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
This will download for each filing a complete SGML text file that contains all the attachments for that filing.
These will be placed in the directory `EDGAR_LOCAL_DATA_DIR/filings/YYYYMMDD`. 

If local storage is enabled, edgartools will first check if the filing is available in local storage before making a request to the SEC.
This will speed up processing and for the most part calls like `html()` and `text()` will behave transparently.

Note that there are some differences between local attachments and attachments when doownloaded from the SEC.

### Downloading by dates

The `download_filings(filing_date)` function accepts a filing date that can be a single date or a range of dates.
The date format must be `YYYY-MM-DD` or `YYYY-MM-DD:YYYY-MM-DD`. You can also use open ended ranges like `YYYY-MM-DD:`  
or `:YYYY-MM-DD`. 

Note that downloading filing attachment files can take a long time so be prepared when downloading for a range of dates.

## Accessing the downloaded filings

When you call `filing.attachments` on a locally downloaded filing, you will have access to the attachments that were downloaded.
If you want to have each file independently you can use `attachments.download()`.

```python
    def download(self, path: Union[str, Path], archive: bool = False):
        """
        Download all the attachments to a specified path.
        If the path is a directory, the file is saved with its original name in that directory.
        If the path is a file, the file is saved with the given path name.
        If archive is True, the attachments are saved in a zip file.
        path: str or Path - The path to save the attachments
        archive: bool (default False) - If True, save the attachments in a zip file
        """
```





