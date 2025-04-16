# Company API

## Overview
The Company API provides access to public company information, filings, and financial data through the SEC EDGAR system.

## Key Classes
- `Company` - Main class for working with company data

## Core Functionality
- Find companies by ticker or CIK
- Access company filings
- Get company facts and financials
- Navigate to related entities

## Common Patterns

### Finding a Company
```python
# By ticker
company = Company("AAPL")

# By CIK
company = Company("0000320193")
company = Company(320193)
```

### Getting Company Filings
```python
# All filings (always sorted by most recent first)
filings = company.get_filings()

# Filtered by form type (still sorted)
annual_reports = company.get_filings(form="10-K")
quarterly_reports = company.get_filings(form="10-Q")

# Get the latest filing(s) directly
latest_10k = annual_reports.latest()  # Most recent 10-K
latest_10qs = quarterly_reports.latest(3)  # 3 most recent 10-Qs

# Get the first N filings (head)
first_five = filings.head(5)
```

#### Method Reference
- `.latest(n=1)`: Returns the latest `n` filings (default 1). If `n=1`, returns a single filing object; otherwise returns a Filings collection.
- `.head(n)`: Returns the first `n` filings (most recent, since filings are sorted descending).
- `.sort(field, ascending=False)`: Returns filings sorted by the specified field.

Filings returned by `get_filings()` are always sorted by most recent date unless otherwise specified.

### Accessing Financial Information
```python
# Get company financials
financials = company.financials

# Access specific statements
income_statement = financials.income_statement()
balance_sheet = financials.balance_sheet()
cashflow = financials.cashflow_statement()
```

## Relevant User Journeys
- Company Financial Analysis Journey
- Financial Data Extraction Journey
- Regulatory Filing Monitoring Journey