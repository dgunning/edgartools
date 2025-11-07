# Common Questions & Examples

Natural language questions mapped to EdgarTools code patterns. These examples show complete solutions for common tasks.

**For quick task routing, see** [quickstart-by-task.md](quickstart-by-task.md).
**For core concepts, see** [SKILL.md](SKILL.md).

## Table of Contents

1. [Show all S-1 filings from February 2023](#show-all-s-1-filings-from-february-2023)
2. [What's been filed today?](#whats-been-filed-today)
3. [Get Apple's revenue for last 3 fiscal years](#get-apples-revenue-for-last-3-fiscal-years)
4. [Tesla's quarterly net income trend (4 quarters)](#teslas-quarterly-net-income-trend-4-quarters)
5. [Full income statement from Apple's 2023 10-K](#full-income-statement-from-apples-2023-10-k)
6. [Compare Apple and Microsoft revenue](#compare-apple-and-microsoft-revenue)
7. [Get balance sheet from latest 10-Q](#get-balance-sheet-from-latest-10-q)
8. [Search for all 8-K filings with 'Item 5.02'](#search-for-all-8-k-filings-with-item-502-officer-departures)
9. [Get all Form 4 insider transactions for AAPL](#get-all-form-4-insider-transactions-for-aapl)
10. [Find all tech companies that filed 10-K in January 2023](#find-all-tech-companies-that-filed-10-k-in-january-2023)
11. [How many crowdfunding filings in the past week?](#how-many-crowdfunding-filings-were-released-in-the-past-week)
12. [When to use .filter() vs Python filtering](#when-to-use-filter-vs-python-filtering)
13. [Don't know the form type? Look it up!](#dont-know-the-form-type-look-it-up)

---

## "Show all S-1 filings from February 2023"

```python
from edgar import get_filings

filings = get_filings(
    2023, 1,  # Q1 2023
    form="S-1",
    filing_date="2023-02-01:2023-02-28"
)
print(f"Found {len(filings)} S-1 filings")
print(filings.head(5))
```

**Using helper function**:
```python
from edgar.ai.helpers import get_filings_by_period

filings = get_filings_by_period(2023, 1, form="S-1", filing_date="2023-02-01:2023-02-28")
```

## "What's been filed today?"

```python
from edgar import get_current_filings

current = get_current_filings()
print(f"{len(current)} filings in last 24 hours")
print(current.head(10))
```

**Using helper function**:
```python
from edgar.ai.helpers import get_today_filings

filings = get_today_filings()
```

## "Get Apple's revenue for last 3 fiscal years"

```python
from edgar import Company

company = Company("AAPL")
income = company.income_statement(periods=3)
print(income)  # Shows 3-year revenue trend
```

**Using helper function**:
```python
from edgar.ai.helpers import get_revenue_trend

income = get_revenue_trend("AAPL", periods=3)
```

## "Tesla's quarterly net income trend (4 quarters)"

```python
from edgar import Company

company = Company("TSLA")
income = company.income_statement(periods=4, annual=False)
print(income)
```

**Using helper function**:
```python
from edgar.ai.helpers import get_revenue_trend

income = get_revenue_trend("TSLA", periods=4, quarterly=True)
```

## "Full income statement from Apple's 2023 10-K"

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(year=2023, form="10-K")[0]
xbrl = filing.xbrl()
income = xbrl.statements.income_statement()
print(income)
```

**Using helper function**:
```python
from edgar.ai.helpers import get_filing_statement

income = get_filing_statement("AAPL", 2023, "10-K", "income")
```

## "Compare Apple and Microsoft revenue"

```python
from edgar import Company

aapl = Company("AAPL")
msft = Company("MSFT")

aapl_income = aapl.income_statement(periods=3)
msft_income = msft.income_statement(periods=3)

print("Apple Revenue Trend:")
print(aapl_income)
print("\nMicrosoft Revenue Trend:")
print(msft_income)
```

**Using helper function**:
```python
from edgar.ai.helpers import compare_companies_revenue

results = compare_companies_revenue(["AAPL", "MSFT"], periods=3)
print("Apple:")
print(results["AAPL"])
print("\nMicrosoft:")
print(results["MSFT"])
```

## "Get balance sheet from latest 10-Q"

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-Q")[0]  # Latest 10-Q
xbrl = filing.xbrl()
balance = xbrl.statements.balance_sheet()
print(balance)
```

## "Search for all 8-K filings with 'Item 5.02' (officer departures)"

```python
from edgar import Company

company = Company("AAPL")
eightk_filings = company.get_filings(form="8-K")

# Examine individual filings
for filing in eightk_filings[:5]:
    print(f"{filing.filing_date}: {filing.form}")
    # Access filing document for text search
    doc = filing.document()
```

## "Get all Form 4 insider transactions for AAPL"

```python
from edgar import Company

company = Company("AAPL")
form4_filings = company.get_filings(form="4")

print(f"Found {len(form4_filings)} Form 4 filings")
for filing in form4_filings[:5]:
    print(f"{filing.filing_date} - {filing.company}")
```

## "Find all tech companies that filed 10-K in January 2023"

```python
from edgar import get_filings

filings = get_filings(
    2023, 1,
    form="10-K",
    filing_date="2023-01-01:2023-01-31"
)

# Filter for tech companies (example tickers)
tech_tickers = ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA"]
tech_filings = filings.filter(ticker=tech_tickers)

print(f"Found {len(tech_filings)} tech 10-K filings in January 2023")
print(tech_filings)
```

## "How many crowdfunding filings were released in the past week?"

**Form Type**: Form C (Regulation Crowdfunding)

```python
from edgar import get_filings
from datetime import datetime, timedelta

# Calculate date range for past week
end_date = datetime.now().date()
start_date = end_date - timedelta(days=7)

print(f"Searching for crowdfunding filings from {start_date} to {end_date}")

# Get Form C filings and filter by date using .filter() method
# (More efficient than Python list comprehension)
filings = get_filings(form="C")
recent_filings = filings.filter(filing_date=f"{start_date}:")

# Count
count = len(recent_filings)
print(f"Found {count} crowdfunding filings in the past week")

# Show sample
if recent_filings:
    print("\nSample filings:")
    print(recent_filings.head(5))
```

**Why this approach?**
- Form C = Crowdfunding offerings (see [form-types-reference.md](form-types-reference.md))
- Can't use `get_today_filings()` (only ~24h)
- Use `.filter(filing_date="start:")` for open-ended date range (more efficient than Python loops)
- Works even when date range spans quarters

**Alternative (if you know the quarter)**:
```python
# If past week is entirely within Q4 2024, filter in one call
filings = get_filings(
    2024, 4,
    form="C",
    filing_date=f"{start_date}:"  # Open-ended range
)
count = len(filings)
```

## "When to use .filter() vs Python filtering"

**IMPORTANT**: Always prefer `.filter()` method over Python list comprehensions when possible!

### ✅ Use `.filter()` method (EFFICIENT)

The `.filter()` method is optimized and should be your first choice:

```python
from edgar import get_filings

filings = get_filings(2024, 1, form="10-K")

# Date filtering - use .filter()!
recent = filings.filter(filing_date="2024-02-01:")

# Ticker filtering - use .filter()!
apple = filings.filter(ticker="AAPL")

# Multiple tickers - use .filter()!
tech = filings.filter(ticker=["AAPL", "MSFT", "GOOGL"])

# Exchange filtering - use .filter()!
nasdaq = filings.filter(exchange="NASDAQ")

# CIK filtering - use .filter()!
by_cik = filings.filter(cik="0000320193")

# Combine multiple filters
filtered = filings.filter(
    ticker=["AAPL", "MSFT"],
    filing_date="2024-01-15:",
    amendments=False
)
```

**Available `.filter()` parameters:**
- `form`: Form type(s)
- `filing_date` / `date`: Date range
- `ticker`: Ticker symbol(s)
- `cik`: CIK number(s)
- `exchange`: Exchange name(s)
- `accession_number`: Accession number(s)
- `amendments`: Include/exclude amendments

See [filtering-filings.md](../../guides/filtering-filings.md) for complete reference.

### ⚠️ Use Python filtering ONLY when necessary (INEFFICIENT)

Only use Python list comprehensions when `.filter()` doesn't support your criteria:

```python
from edgar import get_filings

filings = get_filings(2024, 1, form="10-K")

# Complex string matching (not supported by .filter())
tech_companies = [
    f for f in filings
    if "tech" in f.company.lower() or "software" in f.company.lower()
]

# Custom business logic (not supported by .filter())
short_names = [
    f for f in filings
    if len(f.company) < 30 and f.ticker  # Has ticker and short name
]

# Complex date logic (not supported by .filter())
weekdays_only = [
    f for f in filings
    if f.filing_date.weekday() < 5  # Monday-Friday only
]
```

**Use Python filtering for**:
- Company name pattern matching
- Complex multi-field logic
- Custom calculations
- Conditions not supported by `.filter()`

**Pattern**: `[f for f in filings if <condition>]`

## "Don't know the form type? Look it up!"

**Problem**: You need to map natural language to form codes

**Solution**: Use the form types reference or `describe_form()`

```python
from edgar.reference import describe_form

# Look up form descriptions
print(describe_form("C"))        # Form C: Offering statement
print(describe_form("10-K"))     # Form 10-K: Annual report for public companies
print(describe_form("S-1"))      # Form S-1: Securities registration
print(describe_form("4"))        # Form 4: Statement of changes in beneficial ownership
```

**Complete reference**: See [form-types-reference.md](form-types-reference.md)

**Common mappings**:
- "crowdfunding" → **Form C**
- "IPO" → **S-1** (or F-1 for foreign)
- "insider trading" → **Form 4**
- "proxy statement" → **DEF 14A**
- "institutional holdings" → **13F-HR**
- "private placement" → **Form D**

---

## See Also

- [SKILL.md](SKILL.md) - Core concepts and API reference
- [quickstart-by-task.md](quickstart-by-task.md) - Quick task routing
- [workflows.md](workflows.md) - End-to-end analysis examples
- [form-types-reference.md](form-types-reference.md) - Complete form type catalog
