# Business Overview Data Sources Guide

This guide documents all available data sources in EdgarTools for building a "Business Overview" section on a company page. Each source is documented with API access patterns, data fields, and recommendations.

## Quick Reference: Data Sources Summary

| Section | Primary Source | Load Time | Availability |
|---------|---------------|-----------|--------------|
| Company Header | `company.data` | ~300ms | 100% |
| Business Description | 10-K Item 1 | 1-2s | ~90% |
| Key Metrics | `company.get_facts()` | 1-10s | ~85% |
| Financial Statements | EntityFacts | 3-15s | ~85% |
| Recent Events | 8-K Filings | 200ms | 100% |
| Risk Factors | 10-K Item 1A | 1-2s | ~90% |

---

## 1. Company Core Data (`company.data`)

The foundation of any company page. Available for all SEC filers.

### Access Pattern
```python
from edgar import Company

company = Company("AAPL")
```

### Available Fields

| Field | Property | Example |
|-------|----------|---------|
| Company Name | `company.name` | "Apple Inc." |
| Ticker(s) | `company.tickers` | ["AAPL"] |
| CIK | `company.cik` | 320193 |
| Industry | `company.industry` | "Electronic Computers" |
| SIC Code | `company.sic` | "3571" |
| Exchange(s) | `company.get_exchanges()` | ["NASDAQ"] |
| Fiscal Year End | `company.fiscal_year_end` | "0928" (Sep 28) |
| State of Incorporation | `company.data.state_of_incorporation` | "CA" |
| Phone | `company.data.phone` | "408-996-1010" |
| Business Address | `company.business_address()` | Address object |
| Mailing Address | `company.mailing_address()` | Address object |
| Former Names | `company.data.former_names` | List of historical names |

### Code Example
```python
def get_company_header(ticker: str) -> dict:
    """Get company identification and contact data."""
    company = Company(ticker)

    return {
        "name": company.name,
        "ticker": company.tickers[0] if company.tickers else None,
        "cik": f"{company.cik:010d}",  # Zero-padded CIK
        "industry": company.industry,
        "sic_code": company.sic,
        "exchanges": company.get_exchanges(),
        "fiscal_year_end": company.fiscal_year_end,
        "state_incorporation": company.data.state_of_incorporation,
        "phone": company.data.phone,
    }
```

### Address Formatting
```python
# Business address object
addr = company.business_address()

# Individual components
street = addr.street1
city = addr.city
state = addr.state
zip_code = addr.zip_code

# Formatted string
formatted = str(addr)  # "1 Apple Park Way, Cupertino, CA 95014"
```

---

## 2. Key Financial Metrics (`company.get_facts()`)

High-level financial metrics extracted from XBRL filings via the SEC Company Facts API.

### Access Pattern
```python
facts = company.get_facts()
# or
facts = company.facts  # Property alias
```

### Available Metrics

| Metric | Method | Notes |
|--------|--------|-------|
| Revenue | `facts.get_revenue()` | Latest annual revenue |
| Net Income | `facts.get_net_income()` | Latest annual net income |
| Total Assets | `facts.get_total_assets()` | Balance sheet total |
| Shareholders' Equity | `facts.get_shareholders_equity()` | Book value |
| Cash & Equivalents | `facts.get_cash_and_equivalents()` | Liquid assets |
| Total Liabilities | `facts.get_liabilities()` | All liabilities |
| Shares Outstanding | `facts.shares_outstanding` | Current shares |
| Public Float | `facts.public_float` | Tradeable shares |

### Code Example
```python
def get_key_metrics(ticker: str) -> dict:
    """Get key financial metrics for display."""
    company = Company(ticker)
    facts = company.get_facts()

    if not facts:
        return None

    return {
        "revenue": facts.get_revenue(),
        "net_income": facts.get_net_income(),
        "total_assets": facts.get_total_assets(),
        "shareholders_equity": facts.get_shareholders_equity(),
        "shares_outstanding": facts.shares_outstanding,
    }
```

### Formatting Values
```python
def format_currency(value: float) -> str:
    """Format large currency values (e.g., $416.2B)."""
    if value is None:
        return "N/A"

    abs_value = abs(value)
    if abs_value >= 1e12:
        return f"${value/1e12:.1f}T"
    elif abs_value >= 1e9:
        return f"${value/1e9:.1f}B"
    elif abs_value >= 1e6:
        return f"${value/1e6:.1f}M"
    else:
        return f"${value:,.0f}"

# Usage
metrics = get_key_metrics("AAPL")
print(format_currency(metrics["revenue"]))  # "$416.2B"
```

### Limitations
- Not available for investment companies (mutual funds, ETFs)
- Some foreign filers may have incomplete data
- Fact availability varies by company size and filing history

---

## 3. Business Description (10-K Item 1)

The narrative business description from the company's annual report. This is the richest source of qualitative company information.

### Access Pattern
```python
tenk = company.latest_tenk

if tenk:
    business_text = tenk.business
    # or
    business_text = tenk['Item 1']
```

### Available 10-K Sections

| Item | Property | Content |
|------|----------|---------|
| Item 1 | `tenk.business` | Business operations, products, markets |
| Item 1A | `tenk.risk_factors` | Material risks and uncertainties |
| Item 1B | `tenk['Item 1B']` | Unresolved staff comments |
| Item 1C | `tenk['Item 1C']` | Cybersecurity governance |
| Item 2 | `tenk['Item 2']` | Properties |
| Item 3 | `tenk['Item 3']` | Legal proceedings |
| Item 7 | `tenk.management_discussion` | MD&A financial analysis |
| Item 7A | `tenk['Item 7A']` | Quantitative market risk |
| — | `tenk.auditor` | Auditor name, PCAOB ID, location, ICFR attestation |
| EX-21 | `tenk.subsidiaries` | List of subsidiaries with jurisdiction |

### Code Example
```python
def get_business_description(ticker: str) -> dict:
    """Extract business description from latest 10-K."""
    company = Company(ticker)
    tenk = company.latest_tenk

    if not tenk:
        return {
            "available": False,
            "fallback": f"This company operates in the {company.industry} industry."
        }

    business_text = tenk.business

    return {
        "available": True,
        "full_text": business_text,
        "summary": business_text[:1000] if business_text else None,
        "filing_date": tenk.filing_date,
        "fiscal_year": tenk.fiscal_year,
    }
```

### Text Processing Tips
```python
def extract_first_paragraph(text: str) -> str:
    """Extract the first substantial paragraph as a summary."""
    if not text:
        return None

    # Split by double newlines
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    # Find first paragraph with substantial content
    for p in paragraphs:
        if len(p) > 100:  # Skip short headers
            return p

    return paragraphs[0] if paragraphs else None


def get_business_summary(ticker: str) -> str:
    """Get a concise business summary."""
    company = Company(ticker)
    tenk = company.latest_tenk

    if tenk and tenk.business:
        return extract_first_paragraph(tenk.business)

    # Fallback to industry description
    return f"This company operates in the {company.industry} industry."
```

---

## 4. Multi-Period Financial Statements

Full financial statements across multiple periods for trend analysis.

### Access via EntityFacts
```python
facts = company.get_facts()

# Income Statement (4 annual periods)
income = facts.income_statement(periods=4, annual=True)

# Balance Sheet
balance = facts.balance_sheet(periods=4, annual=True)

# Cash Flow Statement
cash_flow = facts.cash_flow(periods=4, annual=True)

# Quarterly data
quarterly_income = facts.income_statement(periods=8, annual=False)
```

### Access via XBRL (Single Filing)
```python
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Statements from specific filing
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()
cash = xbrl.statements.cashflow_statement()
```

### Output Formats
```python
# Rich table display (for CLI/terminal)
print(income)  # Formatted table

# DataFrame (for further processing)
df = facts.income_statement(periods=4, as_dataframe=True)

# Concise format ($1.0B vs $1,000,000,000)
compact = facts.income_statement(concise_format=True)
```

### Code Example
```python
def get_financial_trends(ticker: str) -> dict:
    """Get multi-period financial data for trend charts."""
    company = Company(ticker)
    facts = company.get_facts()

    if not facts:
        return None

    # Get DataFrames for charting
    income_df = facts.income_statement(periods=4, as_dataframe=True)
    balance_df = facts.balance_sheet(periods=4, as_dataframe=True)

    return {
        "income_statement": income_df.to_dict() if income_df is not None else None,
        "balance_sheet": balance_df.to_dict() if balance_df is not None else None,
        "periods": list(income_df.columns) if income_df is not None else [],
    }
```

---

## 5. Recent Events (8-K Filings)

Material events and corporate announcements from 8-K filings.

### Access Pattern
```python
filings = company.get_filings(form="8-K")

for filing in filings[:10]:
    print(f"{filing.filing_date}: {filing.parsed_items}")
```

### Common 8-K Item Codes

| Item | Description |
|------|-------------|
| 1.01 | Entry into Material Agreement |
| 1.02 | Termination of Material Agreement |
| 2.01 | Acquisition/Disposition of Assets |
| 2.02 | Results of Operations (Earnings) |
| 2.03 | Creation of Obligation |
| 5.02 | Director/Officer Changes |
| 5.07 | Shareholder Vote |
| 7.01 | Regulation FD Disclosure |
| 8.01 | Other Events |

### Code Example
```python
from datetime import date, timedelta

def get_recent_events(ticker: str, days: int = 90) -> list:
    """Get recent material events from 8-K filings."""
    company = Company(ticker)
    cutoff = date.today() - timedelta(days=days)

    filings = company.get_filings(form="8-K")
    events = []

    for filing in filings:
        if filing.filing_date < cutoff:
            break

        events.append({
            "date": filing.filing_date.isoformat(),
            "items": filing.parsed_items,
            "description": describe_8k_items(filing.parsed_items),
            "url": filing.url,
        })

    return events


def describe_8k_items(items_str: str) -> str:
    """Convert item codes to human-readable description."""
    item_descriptions = {
        "1.01": "Material Agreement",
        "2.02": "Earnings Release",
        "5.02": "Officer/Director Change",
        "7.01": "Press Release",
        "8.01": "Other Event",
    }

    if not items_str:
        return "Corporate Update"

    items = [i.strip() for i in items_str.split(",")]
    descriptions = [item_descriptions.get(i, i) for i in items]
    return ", ".join(descriptions)
```

---

## 6. Risk Factors (10-K Item 1A)

Material risks and uncertainties facing the company.

### Access Pattern
```python
tenk = company.latest_tenk
risk_text = tenk.risk_factors
# or
risk_text = tenk['Item 1A']
```

### Code Example
```python
def get_risk_summary(ticker: str, max_risks: int = 5) -> list:
    """Extract top risk factors from 10-K."""
    company = Company(ticker)
    tenk = company.latest_tenk

    if not tenk or not tenk.risk_factors:
        return []

    text = tenk.risk_factors

    # Simple extraction: look for bold or capitalized headers
    # More sophisticated: use NLP to extract risk categories

    # For now, split by common risk section patterns
    risks = []
    lines = text.split('\n')

    for line in lines:
        # Look for risk headers (often bold or capitalized)
        if line.strip() and line.isupper() or line.strip().endswith(':'):
            risks.append(line.strip())
            if len(risks) >= max_risks:
                break

    return risks
```

---

## 7. Insider Activity (Form 4)

Officer and director stock transactions.

### Access Pattern
```python
form4_filings = company.get_filings(form="4")

for filing in form4_filings[:10]:
    form4 = filing.obj()
    print(f"{form4.insider_name}: {form4.position}")
```

### Code Example
```python
def get_insider_activity(ticker: str, limit: int = 10) -> list:
    """Get recent insider transactions."""
    company = Company(ticker)
    filings = company.get_filings(form="4")

    transactions = []
    for filing in filings[:limit]:
        try:
            form4 = filing.obj()

            # Get transaction summary
            purchases = form4.common_stock_purchases
            sales = form4.common_stock_sales

            transactions.append({
                "date": filing.filing_date.isoformat(),
                "insider": form4.insider_name,
                "position": form4.position,
                "has_purchases": len(purchases) > 0 if purchases is not None else False,
                "has_sales": len(sales) > 0 if sales is not None else False,
            })
        except Exception:
            continue

    return transactions
```

---

## 8. Institutional Holdings (13F)

Institutional investor holdings (for investment management companies).

### Access Pattern
```python
thirteenf_filings = company.get_filings(form="13F-HR")

for filing in thirteenf_filings[:5]:
    portfolio = filing.obj()
    holdings = portfolio.infotable  # DataFrame
```

---

## Complete Implementation Example

```python
from edgar import Company
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from typing import Optional


class CompanyOverview:
    """Complete company overview data for a SaaS page."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self._company = None
        self._facts = None
        self._tenk = None

    @property
    def company(self):
        if self._company is None:
            self._company = Company(self.ticker)
        return self._company

    @property
    def facts(self):
        if self._facts is None:
            self._facts = self.company.get_facts()
        return self._facts

    @property
    def tenk(self):
        if self._tenk is None:
            self._tenk = self.company.latest_tenk
        return self._tenk

    def get_header(self) -> dict:
        """Company identification data."""
        c = self.company
        return {
            "name": c.name,
            "ticker": c.tickers[0] if c.tickers else None,
            "cik": f"{c.cik:010d}",
            "industry": c.industry,
            "sic_code": c.sic,
            "exchanges": c.get_exchanges(),
        }

    def get_contact(self) -> dict:
        """Company contact information."""
        c = self.company
        addr = c.business_address()
        return {
            "phone": c.data.phone,
            "website": c.data.website,
            "investor_website": c.data.investor_website,
            "address": str(addr) if addr else None,
            "state_incorporation": c.data.state_of_incorporation,
        }

    def get_key_metrics(self) -> Optional[dict]:
        """Key financial metrics."""
        if not self.facts:
            return None

        return {
            "revenue": self._format_value(self.facts.get_revenue()),
            "net_income": self._format_value(self.facts.get_net_income()),
            "total_assets": self._format_value(self.facts.get_total_assets()),
            "shareholders_equity": self._format_value(self.facts.get_shareholders_equity()),
        }

    def get_business_summary(self) -> dict:
        """Business description from 10-K."""
        if self.tenk and self.tenk.business:
            text = self.tenk.business
            # Extract first substantial paragraph
            paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 100]
            summary = paragraphs[0] if paragraphs else text[:500]

            return {
                "available": True,
                "summary": summary,
                "full_text": text,
                "source": f"10-K filed {self.tenk.filing_date}",
            }

        # Fallback
        return {
            "available": False,
            "summary": f"This company operates in the {self.company.industry} industry.",
            "source": "SEC SIC classification",
        }

    def get_recent_events(self, days: int = 90) -> list:
        """Recent 8-K material events."""
        cutoff = date.today() - timedelta(days=days)
        filings = self.company.get_filings(form="8-K")

        events = []
        for filing in filings:
            if filing.filing_date < cutoff:
                break
            events.append({
                "date": filing.filing_date.isoformat(),
                "items": filing.parsed_items,
                "url": filing.url,
            })

        return events[:10]  # Limit to 10 most recent

    def get_all(self) -> dict:
        """Get all overview data in one call."""
        return {
            "header": self.get_header(),
            "contact": self.get_contact(),
            "metrics": self.get_key_metrics(),
            "business": self.get_business_summary(),
            "events": self.get_recent_events(),
        }

    @staticmethod
    def _format_value(value: float) -> Optional[str]:
        """Format large values as abbreviated strings."""
        if value is None:
            return None

        abs_val = abs(value)
        if abs_val >= 1e12:
            return f"${value/1e12:.1f}T"
        elif abs_val >= 1e9:
            return f"${value/1e9:.1f}B"
        elif abs_val >= 1e6:
            return f"${value/1e6:.1f}M"
        return f"${value:,.0f}"


# Usage
overview = CompanyOverview("AAPL")
data = overview.get_all()
print(data)
```

---

## Performance Optimization

### Parallel Loading
```python
from concurrent.futures import ThreadPoolExecutor

def load_overview_parallel(ticker: str) -> dict:
    """Load overview data with parallel fetching."""
    company = Company(ticker)

    def get_facts():
        return company.get_facts()

    def get_tenk():
        return company.latest_tenk

    def get_8ks():
        return list(company.get_filings(form="8-K")[:10])

    with ThreadPoolExecutor(max_workers=3) as executor:
        facts_future = executor.submit(get_facts)
        tenk_future = executor.submit(get_tenk)
        events_future = executor.submit(get_8ks)

        facts = facts_future.result()
        tenk = tenk_future.result()
        events = events_future.result()

    return {
        "header": {"name": company.name, "ticker": ticker},
        "facts": facts,
        "tenk": tenk,
        "events": events,
    }
```

### Caching Recommendations

| Data Type | Cache Duration | Reason |
|-----------|---------------|--------|
| Company basics | 24 hours | Rarely changes |
| Financial facts | 1 hour | Updates with filings |
| 10-K content | Forever | Immutable after filing |
| Recent filings | 15 minutes | New filings possible |

---

## Availability Notes

| Data Source | Availability | Notes |
|-------------|--------------|-------|
| Company core data | 100% | Available for all SEC filers |
| Key metrics | ~85% | Not for investment companies |
| 10-K sections | ~90% | Public operating companies only |
| 8-K events | 100% | All public companies file 8-Ks |
| Form 4 insider | ~70% | Only if insiders trade |
| 13F holdings | ~5% | Only investment managers |

---

## See Also

- `edgar/ai/skills/core/quickstart-by-task.md` - API quick reference
- `edgar/ai/skills/core/data-objects.md` - Data object documentation
- `docs/entity-facts-api-current-implementation.md` - EntityFacts details
