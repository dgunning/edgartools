# Building Company Pages with EdgarTools

A focused guide for SaaS developers building company information pages.

## Quick Reference: Data Sources

| Section | EdgarTools Source | API Cost | Key Properties |
|---------|-------------------|----------|----------------|
| **Header** | `company.data` | ~300ms (1 call) | name, tickers, industry, sic |
| **Key Metrics** | `company.get_facts()` | 1-10s (cached) | revenue, net_income, assets |
| **Financials** | `facts.income_statement()` | In-memory | Multi-period statements |
| **Events** | `get_filings(form="8-K")` | Included | parsed_items for event codes |
| **Insider Activity** | `get_filings(form="4")` | Per-filing | Form4 transactions |

## Basic Usage

```python
from edgar import Company

# Create company (no API call yet)
company = Company("AAPL")

# Get basic info (triggers 1 API call, ~300ms)
print(company.name)           # "Apple Inc."
print(company.tickers)        # ["AAPL"]
print(company.industry)       # "Technology"
print(company.sic)            # 3571

# Get financial facts (1 API call, cached)
facts = company.get_facts()
print(facts.get_revenue())         # Latest revenue
print(facts.get_net_income())      # Latest net income
print(facts.shares_outstanding)    # Share count
print(facts.public_float)          # Public float

# Get financial statements
income = facts.income_statement(periods=4, annual=True)
balance = facts.balance_sheet(periods=4, annual=True)
cash = facts.cash_flow_statement(periods=4, annual=True)
```

## Parallel Loading Pattern

Load company data and facts concurrently for faster page rendering:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from edgar import Company

def load_company_page(ticker: str) -> dict:
    company = Company(ticker)
    results = {}

    def load_basic():
        return {
            "name": company.name,
            "ticker": company.tickers[0] if company.tickers else None,
            "industry": company.industry,
            "cik": company.cik,
        }

    def load_facts():
        facts = company.get_facts()
        return {
            "revenue": facts.get_revenue(),
            "net_income": facts.get_net_income(),
            "total_assets": facts.get_total_assets(),
        }

    def load_filings():
        filings = company.get_filings(form="8-K", trigger_full_load=False)
        return [{"form": f.form, "date": f.filing_date} for f in filings[:10]]

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(load_basic): "basic",
            executor.submit(load_facts): "facts",
            executor.submit(load_filings): "filings",
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    return results
```

## Extracting 8-K Events

8-K filings contain current events with item codes indicating the type:

```python
company = Company("AAPL")
eight_ks = company.get_filings(form="8-K")

for filing in eight_ks[:5]:
    # Get item codes (e.g., "2.02,9.01")
    items = filing.parsed_items  # More accurate than filing.items
    print(f"{filing.filing_date}: Items {items}")
```

### Material 8-K Item Codes

| Item | Description | Importance |
|------|-------------|------------|
| **1.01** | Material Agreement | High |
| **2.01** | Acquisition/Disposition | High |
| **2.02** | Results of Operations | High (Earnings) |
| **4.02** | Non-Reliance on Financials | Critical |
| **5.01** | Change in Control | High |
| **5.02** | Director/Officer Change | High |
| 5.07 | Shareholder Vote Results | Normal |
| 7.01 | Regulation FD Disclosure | Normal |
| 8.01 | Other Events | Normal |
| 9.01 | Financial Statements | Normal |

## Insider Activity from Form 4

```python
company = Company("AAPL")
form4s = company.get_filings(form="4")

for filing in form4s[:5]:
    form4 = filing.obj()  # Parse as Form4 object

    # Access insider info
    print(f"Insider: {form4.insider_name}")
    print(f"Position: {form4.position}")

    # Check for sales
    if form4.common_stock_sales is not None:
        for _, sale in form4.common_stock_sales.iterrows():
            print(f"  Sale: {sale['Shares']} shares @ ${sale['Price']}")

    # Check for purchases
    if form4.common_stock_purchases is not None:
        for _, purchase in form4.common_stock_purchases.iterrows():
            print(f"  Buy: {purchase['Shares']} shares @ ${purchase['Price']}")
```

## Performance Tips

### 1. Use `trigger_full_load=False`

```python
# Fast: Only loads recent filings (~100)
filings = company.get_filings(form="10-K", trigger_full_load=False)

# Slow: Loads ALL historical filings (multiple API calls)
filings = company.get_filings(year=2010)  # Triggers full load
```

### 2. EntityFacts is Cached (LRU 32)

```python
# First call: 1-10 seconds (API call)
facts = company.get_facts()

# Subsequent calls: <5ms (from cache)
facts = company.get_facts()  # Cached!
```

### 3. Use EntityFacts for Multi-Period Data

```python
# Efficient: Single API call for all periods
income = company.income_statement(periods=5)

# Inefficient: Parses XBRL for each filing
for filing in filings[:5]:
    xbrl = filing.xbrl()  # Slow per-filing
```

### 4. Avoid Parsing Unless Needed

```python
# Fast: Use filing metadata
for f in filings[:10]:
    print(f.form, f.filing_date, f.accession_no)

# Slow: Parse each filing
for f in filings[:10]:
    obj = f.obj()  # Downloads and parses
```

## Reference Implementation

A complete reference implementation is available at:

```
docs/examples/company_page/
├── __init__.py        # Package exports
├── models.py          # Dataclass DTOs (CompanyOverview, FilingItem, etc.)
├── formatters.py      # Currency, date, percentage formatters
├── company_page.py    # Main CompanyPage class
└── example_usage.py   # Runnable demonstration
```

### Quick Start

```python
from docs.examples.company_page import CompanyPage

page = CompanyPage("AAPL")

# Template-ready data
print(page.overview.name)
print(page.financial_summary.revenue.display_value)

# Get all data as dict for templates
data = page.to_dict()
```

### Key Classes

| Class | Purpose |
|-------|---------|
| `CompanyPage` | Main entry point, wraps Company |
| `CompanyOverview` | Header data (name, ticker, industry) |
| `FinancialSummary` | Key metrics with formatting |
| `FilingItem` | Single filing for lists |
| `ActivityItem` | Timeline event (filing, trade) |

## Caching Recommendations

| Data Type | Suggested TTL | Notes |
|-----------|---------------|-------|
| Company basics | 24 hours | Rarely changes |
| Financial facts | 1 hour | Updates with filings |
| Recent filings | 15 minutes | New filings throughout day |
| Parsed reports | 24 hours | Filing content immutable |

## Common Patterns

### Company Header Section

```python
company = Company("AAPL")
header = {
    "name": company.name,
    "ticker": company.tickers[0] if company.tickers else None,
    "cik": company.cik,
    "industry": company.industry,
    "fiscal_year_end": company.fiscal_year_end,
    "exchanges": company.get_exchanges(),
}
```

### Financial Dashboard

```python
facts = company.get_facts()
metrics = {
    "revenue": facts.get_revenue(),
    "net_income": facts.get_net_income(),
    "total_assets": facts.get_total_assets(),
    "equity": facts.get_shareholders_equity(),
    "shares": facts.shares_outstanding,
    "public_float": facts.public_float,
}
```

### Recent Activity Timeline

```python
from datetime import date, timedelta

cutoff = date.today() - timedelta(days=90)
filings = company.get_filings(trigger_full_load=False)

activities = []
for f in filings:
    if f.filing_date < cutoff:
        break
    activities.append({
        "type": f.form,
        "date": f.filing_date,
        "url": f.url,
    })
```

## Filing Form Reference

| Form | Object Class | Key Data |
|------|-------------|----------|
| 10-K | `TenK` | financials, income_statement, balance_sheet |
| 10-Q | `TenQ` | financials, period_of_report |
| 8-K | `EightK` | items, parsed_items |
| Form 4 | `Form4` | common_stock_sales, common_stock_purchases |
| 13F-HR | `ThirteenF` | infotable (portfolio holdings) |
| SC 13D | None | HTML parsing required |
| SC 13G | None | HTML parsing required |

## See Also

- [Company Facts Guide](company-facts.md) - Deep dive into EntityFacts
- [Track Form 4 Guide](track-form4.md) - Insider trading analysis
- [Working with Filings](working-with-filing.md) - Filing object reference
