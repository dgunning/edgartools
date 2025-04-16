# Edgartools

This is the documentation for **edgartools**, a Python library for working with SEC filings and data.

# Installing

```bash
pip install edgartools
```

# Using

1. Import from the main module `edgar`
2. Set your identity to identify yourself to the SEC

```python
from edgar import *
set_identity("user@domain.com") # Identify yourself to the SEC 
```

# Major API Components

1. **[Company API](company_api.md)** - Work with public companies and their filings
2. **[Filings API](filings_api.md)** - Search and filter SEC filings
3. **[Attachments API](attachments_api.md)** - Access and extract content from filing documents
4. **[Funds API](funds_api.md)** - Work with investment funds and their structure
5. **[XBRL API](xbrl_api.md)** - Extract and analyze financial data
6. **[Financial Statements API](financial_statements_api.md)** - Access standardized financial statements
7. **[ThirteenF API](thirteenf_api.md)** - Access fund holdings data
8. **[Ownership API](ownership_api.md)** - Track insider transactions

Refer to [User Journeys](user_journeys.md) for common workflows and use cases.

## High Level Patterns

- Get a `Company` then get their `Filings`
- Get `Filings` and then filter
- Select a `Filing` and convert it to a `Data Object`
- Find a `Filing` and convert it to a `Data Object`

# Basic Usage Examples

## Getting Filings

```python
# Get all recent filings
filings = get_filings()

# Get filings by form type
filings = get_filings(form="10-K")

# Get filings for a specific company
company = Company("AAPL")
filings = company.get_filings()
```

## Working with a Filing

```python
# Select a filing
filing = filings[0]

# Get filing content
html_content = filing.html()
text_content = filing.text()
markdown_content = filing.markdown()

# Get filing attachments
attachments = filing.attachments

# Convert filing to data object
data_object = filing.obj()
```

## Financial Analysis

```python
# Get company financial data
company = Company("AAPL")
financials = company.financials

# Access financial statements
income_statement = financials.income_statement
balance_sheet = financials.balance_sheet
cashflow = financials.cashflow_statement
```

## Fund Analysis

```python
# Find a fund by ticker
from edgar.funds import find_fund
fund_class = find_fund("VFIAX")  # Returns a FundClass

# Navigate fund structure
series = fund_class.series
company = fund_class.company

# Get all share classes in a series
classes = series.get_classes()
```

For detailed documentation on each component, refer to the specific API documents linked above.