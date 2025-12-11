# Why Choose EdgarTools?

EdgarTools makes working with SEC data straightforward. Here's what sets it apart.

## The SEC Data Challenge

Working with SEC filings is harder than it should be:

- **Complex file formats**: Raw XBRL is verbose and difficult to parse
- **Inconsistent data**: Companies use different concepts for the same items
- **Poor tooling**: Existing solutions are either too basic or overly complex
- **Rate limits**: SEC enforces strict access limits that require careful handling

EdgarTools addresses these problems.

## How EdgarTools is Different

### Clean, Intuitive API

Get company financials in a few lines:

```python
from edgar import Company

apple = Company("AAPL")
financials = apple.get_financials()

# Get key metrics directly
revenue = financials.get_revenue()           # 416,161,000,000
net_income = financials.get_net_income()     # 93,736,000,000
total_assets = financials.get_total_assets() # 352,583,000,000
```

Access filings just as easily:

```python
# Get recent 10-K filings
filings = apple.get_filings(form="10-K")

# Work with the latest filing
latest_10k = filings[0]
tenk = latest_10k.obj()  # Parsed TenK object

# Access specific sections
print(tenk.business)          # Item 1 - Business description
print(tenk.risk_factors)      # Item 1A - Risk factors
```

### Standardized Financial Data

EdgarTools normalizes financial concepts across companies:

```python
from edgar import Company

# Different companies use different XBRL concepts
# EdgarTools standardizes them
for ticker in ["AAPL", "MSFT", "GOOGL"]:
    company = Company(ticker)
    financials = company.get_financials()

    # Same API works for all companies
    revenue = financials.get_revenue()
    print(f"{ticker}: ${revenue:,.0f}")
```

### Rich Filing Support

Access structured data from various SEC forms:

```python
from edgar import Company

company = Company("AAPL")

# 10-K Annual Reports
tenk = company.get_filings(form="10-K")[0].obj()
print(tenk.financials.income_statement())

# 10-Q Quarterly Reports
tenq = company.get_filings(form="10-Q")[0].obj()

# 8-K Current Reports (events)
eightk = company.get_filings(form="8-K")[0].obj()
print(eightk.items)  # List of reported items

# Insider Trading (Form 4)
form4s = company.get_filings(form="4")

# Institutional Holdings (13F)
from edgar import get_filings
thirteenf = get_filings(form="13F-HR")[0].obj()
print(thirteenf.holdings)  # DataFrame of holdings
```

### Developer-Friendly Features

**Type hints and autocomplete:**
```python
from edgar import Company, Filing

company: Company = Company("AAPL")
filings = company.get_filings()  # Returns Filings object
filing: Filing = filings[0]      # Full type support
```

**Rich display in Jupyter notebooks:**
```python
# Objects render nicely in notebooks
company          # Shows company info card
filings          # Interactive table
filing.obj()     # Formatted report view
```

**Built-in rate limiting:**
```python
# EdgarTools handles SEC rate limits automatically
# No need to add delays or retry logic
filings = company.get_filings(form="10-K")  # Just works
```

### XBRL Made Simple

Access structured financial data without dealing with raw XBRL:

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Get XBRL data
xbrl = filing.xbrl()

# Access financial statements
income_stmt = xbrl.statements.income_statement
balance_sheet = xbrl.statements.balance_sheet
cash_flow = xbrl.statements.cashflow_statement

# Query specific facts
facts = xbrl.facts
revenue_facts = facts.get_facts_by_concept("Revenues")
```

## Feature Overview

| Feature | Description |
|---------|-------------|
| **Company Data** | Look up any public company by ticker or CIK |
| **Filing Access** | Search and filter SEC filings by form type, date, company |
| **Financial Statements** | Parsed income statement, balance sheet, cash flow |
| **XBRL Data** | Structured access to all XBRL facts and dimensions |
| **Insider Trading** | Parse Forms 3, 4, 5 for ownership transactions |
| **Fund Holdings** | 13F institutional holdings reports |
| **Document Extraction** | Extract text and exhibits from filings |
| **Local Caching** | Intelligent caching reduces API calls |
| **Rate Limiting** | Automatic compliance with SEC limits |

## Getting Started

Install and try it:

```bash
pip install edgartools
```

```python
from edgar import Company, set_identity

# SEC requires identification
set_identity("Your Name your.email@example.com")

# Start exploring
company = Company("AAPL")
print(company)
```

**Next steps:**

- [Installation Guide](installation.md) - Setup instructions
- [Quick Start](quickstart.md) - Your first 5 minutes
- [Financial Statement Analysis](guides/extract-statements.md) - Work with financials
- [Insider Trading](guides/track-form4.md) - Monitor Form 4 filings

## Open Source

EdgarTools is free and open source under the MIT license. Contributions welcome on [GitHub](https://github.com/dgunning/edgartools).

---

[Get started with EdgarTools](installation.md)
