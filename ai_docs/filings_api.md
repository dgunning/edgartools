# Filings API

## Overview
The Filings API allows searching, filtering, and analyzing SEC filings across companies, time periods, and form types.

## Key Classes
- `Filings` - Collection of filing objects with filtering capabilities
- `Filing` - Individual SEC filing with methods for accessing content

## Core Functionality
- Search for filings by form type, date, company
- Filter filing collections
- Page through filing results
- Access filing content and metadata
- Convert filings to specialized data objects

## Common Patterns

### Getting Filings
```python
# All recent filings
filings = get_filings()

# Filings for specific year/quarter
filings = get_filings(year=2023, quarter=1)

# Filings of specific type
filings = get_filings(form="8-K")
```

### Filtering Filings
```python
# Filter by form
annual_reports = filings.filter(form="10-K")

# Filter by date range
recent_filings = filings.filter(filing_date="2023-01-01:2023-03-31")

# Filter by company
apple_filings = filings.filter(ticker="AAPL")
```

### Working with Filing Content
```python
# Get a specific filing
filing = filings[0]

# View filing content
html_content = filing.html()
text_content = filing.text()

# Access filing metadata
print(filing.company)
print(filing.form)
print(filing.filing_date)
```

## Filing Header

Every SEC filing includes a header section with structured metadata about the submission, filer, and related parties. This header is parsed and accessible as a `FilingHeader` object.

**Example:**
```python
header = filing.header  # or filing.filing_header
print(header)  # displays accession number, filing date, form type, company info, etc.
```

The header contains:
- Accession number
- Filing date
- Submission type
- Company/filer information
- Addresses
- Reporting owners
- Issuer and subject company info

You can access all of these fields programmatically for downstream analysis.

## Attachments

Filings can contain multiple attachments (documents), such as the main filing, exhibits, XBRL, HTML, and more. The primary interface for working with these is through the `Attachments` and `Attachment` classes.

- Use `filing.attachments` to access all documents in a filing.
- Iterate, filter, and extract content from each `Attachment`.
- Quickly get exhibits, primary documents, and download files.

**Example:**
```python
attachments = filing.attachments
for attachment in attachments:
    print(attachment.document, attachment.description)
```

For advanced filtering, querying, downloading, and full API details, see [attachments_api.md](attachments_api.md).


### Converting to Data Objects
```python
# Convert filing to appropriate data object
data_object = filing.obj()

# Examples for different form types
tenk = filing.obj()  # Returns TenK for 10-K filings
ownership = filing.obj()  # Returns Ownership for Forms 3,4,5
thirteenf = filing.obj()  # Returns ThirteenF for 13F-HR
```

## Relevant User Journeys
- SEC Filing Discovery Journey
- Regulatory Filing Monitoring Journey
- Company Financial Analysis Journey