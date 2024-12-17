# Edgar Tools Documentation

EdgarTools is a Python library designed to interact with and process SEC EDGAR filings and data. It provides a comprehensive set of tools for analyzing various SEC forms, financial data, and regulatory disclosures.

## Usage

### Install using pip
```bash
pip install edgartools
```

### Import the library  
Import the library using `from edgar import *`. You also need to set your identity using `set_identity` so that the SEC knows who you are and allows you to access their data. This can just be an email address or a name and email.

```python
from edgar import *
set_identity("mike.mccalum@indigo.com")
```

### Getting filings
You can get the filings for a company using the `get_filings` function. By default this will get all filings for the current year and quarter. 

```python
filings = get_filings()
```

#### Parameters for get_filings

The `get_filings` function takes the following parameters:

- **`year`** - The year **2025** or list of years **[2024,2024]** to get filings for. Default is the current year.
- **`quarter`** - The quarter **1** or list of quarters **[1,2,3,4]** to get filings for. Default is the current quarter.
- **`form`** - The form to get filings for. Default is all forms.
- **`amendments`** - Whether to include amendments e.g. include "10-K/A" if filtering for "10-K".. Default is True.
- **`filing_date`** - The filing date to get filings for. Default is all filings. Can be a single date or a range of dates.
- **`index`** - The index type - "form" or "xbrl". Default is "form". Use index="xbrl" to limit to only filings published using XBRL.

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
### Get the latest unpublished filings
The `get_filings` function downloads the filing indexes from the SEC EDGAR website. The data is generallly available by **10:30 PM EST** on the day of the filing and so will not include filings filed after this time but not yet released. To get the latest unpublished filings use the `get_unpublished_filings` function. For example:

```python
filings = get_latest_filings()
```

### Filtering filings
After getting filings, you can filter filings using the `filter` method. 
You can filter filings by form, date, CIK, ticker, and accession number.
For example:

```python

        >>> filings = get_filings()

        Filter the filings

        On a date
        >>> filings.filter(date="2020-01-01")

        Up to a date
        >>> filings.filter(date=":2020-03-01")

        From a date
        >>> filings.filter(date="2020-01-01:")

        # Between dates
        >>> filings.filter(date="2020-01-01:2020-03-01")

        :param form: The form or list of forms to filter by
        :param amendments: Whether to include amendments to the forms e.g. include "10-K/A" if filtering for "10-K"
        :param filing_date: The filing date
        :param date: An alias for the filing date
        :param cik: The CIK or list of CIKs to filter by
        :param ticker: The ticker or list of tickers to filter by
        :param accession_number: The accession number or list of accession numbers to filter by
        :return: The filtered filings

```

### Paginating filings
The `Filings` object is a container for a list of filings. The list of filings can  be large but by default you can only see the first page of filings. 

To change the page, you can paginate filings using the `next` and `prev` methods. For example:

```python
filings = get_filings()
filings.next()
filings.prev()
```
### Subsetting filings
You can subset filings using the `head` and `tail` and `sample` methods. For example:

```python
filings = get_filings()
filings.head(10)
filings.tail(10)
filings.sample(10)
```
### Looping through filings
You can loop through filings using the `for` loop. For example:

```python
filings = get_filings()
for filing in filings:
    print(filing)
```

## Working with a Filing
A filing is a handle to a single SEC EDGAR filing. With it you can access all the documents and datafiles on the filing.

### Getting a Filing
You can get a filing using the `[]` operator. For example:

```python
filings = get_filings()
filing = filings[0]
```

### Open a Filing in your browser
The `open` method opens the main document of a filing in your browser
```python
filing.open()
``` 

### Open the Filing homepage
The filing homepage is the landing page for a filing. It links to all the documents and datafiles on the filing.
```python
filing.open_homepage()
```

### View the Filing
This downloads the filing's HTML content, parses it and displays it as close to the original as is possible in the console or in a Jupyter notebook. This is a good way to preview a filing, but won't be perfect so if you need a perfect copy of the filing, you should use the `open` method to view it in the browser.
```python
filing.view()
```

### Get the HTML of a Filing
This downloads the filing's HTML content and returns it as a string.
```python
html = filing.html()
```

### Getting the text of a Filing
The `text` method returns the text of a filing
```python
text = filing.text()
```

## Working with Attachments

The `attachments` attribute returns a list of the attachments on a filing
```python
attachments = filing.attachments
```

### Looping through Attachments
You can loop through attachments using the `for` loop.
```python
for attachment in filings.attachments:
    print(attachment)
```

### Getting an Attachment
The `[]` operator returns an attachment by index
```python
attachment = filing.attachments[0]
```

### Viewing an Attachment
The `view` method displays the text of an attachment in the console. This works for text and html attachments
```python
attachment.view()
```

### Downloading Attachments
The `download` method downloads all the attachments to a folder of your choice.
```python
filing.attachments.download(path)
```

Last Updated: December 16, 2024