---
description: Parse SEC 8-K current reports and extract earnings data with Python. Access corporate events, press releases, and financial statements using edgartools.
---

# 8-K Current Reports: Parse SEC Corporate Events and Earnings with Python

Companies file 8-K current reports within four business days of material events -- acquisitions, executive changes, earnings releases, bankruptcy. EdgarTools parses these filings into structured Python objects so you can access the event items, press releases, and financial tables.

```python
from edgar import *

filing = get_filings(form="8-K").latest()
eight_k = filing.obj()
eight_k
```

![8-K current report parsed with Python edgartools](images/eightk.webp)

Three lines to get a parsed 8-K with company info, filing date, items disclosed, and exhibits.

---

## Read Item Content

Every 8-K discloses one or more numbered items (1.01 through 9.01). The `items` property lists what was disclosed:

```python
eight_k.items  # ['Item 2.02', 'Item 9.01']
```

Access the text of any item by number:

```python
# Works with or without "Item" prefix
content = eight_k['2.02']
content = eight_k['Item 2.02']

print(content)
```

Common items:

| Item | What it reports |
|------|----------------|
| **1.01** | Material agreements |
| **2.02** | Earnings and financial condition |
| **5.02** | Director or officer changes |
| **8.01** | Other events |
| **9.01** | Financial statements and exhibits |

The complete mapping is in `eight_k.structure`.

---

## Access Press Releases

Most 8-Ks attach press releases as EX-99 exhibits:

```python
if eight_k.has_press_release:
    releases = eight_k.press_releases
    pr = releases[0]

    # Get content in different formats
    pr.text()         # Plain text
    pr.html()         # HTML
    pr.to_markdown()  # Markdown
    pr.open()         # Open in browser
```

Press releases are indexed by position. `press_releases[0]` is the first release, `press_releases[1]` is the second.

---

## Extract Earnings Data from 8-K Filings

When an 8-K includes Item 2.02 (earnings) with an EX-99.1 press release, EdgarTools parses the financial tables automatically:

```python
# Check if earnings data is available
if eight_k.has_earnings:
    earnings = eight_k.earnings  # EarningsRelease object

    # Get specific statements
    income = eight_k.income_statement       # FinancialTable or None
    balance = eight_k.balance_sheet         # FinancialTable or None
    cash_flow = eight_k.cash_flow_statement # FinancialTable or None

    # Safe access - always returns a DataFrame
    df = eight_k.get_income_statement()
    df = eight_k.get_balance_sheet()
    df = eight_k.get_cash_flow_statement()
```

The `EarningsRelease` object provides additional tables:

```python
earnings.financial_tables   # All parsed financial tables
earnings.segment_data       # Segment breakdown (if present)
earnings.eps_reconciliation # GAAP to Non-GAAP EPS reconciliation
earnings.guidance           # Forward guidance table
earnings.detected_scale     # Scale factor (thousands, millions, etc.)
```

Each `FinancialTable` has:

```python
table = eight_k.income_statement

table.dataframe         # Parsed data as DataFrame
table.scaled_dataframe  # Values multiplied by detected scale
table.scale             # Scale enum (UNITS, THOUSANDS, MILLIONS, BILLIONS)
table.title             # Table title if detected
table.statement_type    # StatementType enum
table.to_html()         # HTML export for web apps
table.to_json()         # JSON export for APIs
```

Example workflow:

```python
from edgar import Company

aapl = Company("AAPL")
filing = aapl.get_filings(form="8-K").latest()
eight_k = filing.obj()

if eight_k.has_earnings:
    # Get income statement with scale applied
    income = eight_k.income_statement
    df = income.scaled_dataframe

    # Access specific metrics
    revenue = df.loc['Net revenue']
    print(f"Scale: {income.scale.name}")  # "MILLIONS"
    print(f"Revenue: ${revenue.iloc[0]:,.0f}")
```

---

## Access Financial Statements

Some 8-Ks include XBRL-tagged financial statements (less common than EX-99 tables):

```python
# Check if XBRL financials are available
if eight_k.financials:
    statements = eight_k.financials.get_statement()
    print(statements)
```

This uses the same XBRL parsing as 10-K/10-Q filings. For earnings announcements, the EX-99 table parsing (previous section) is more common and reliable.

---

## Work with Exhibits

All 8-K attachments (press releases, financial statements, material agreements):

```python
exhibits = filing.exhibits

for ex in exhibits:
    print(f"{ex.document_type}: {ex.description}")

# Access specific exhibit
ex_99 = exhibits[0]
content = ex_99.download()
```

Exhibits are indexed by position. The `document_type` shows what kind of exhibit it is (EX-99.1, EX-10.1, etc.).

---

## Common Analysis Patterns

### Find all earnings releases in a quarter

```python
from edgar import get_filings

filings = get_filings(
    form="8-K",
    date="2024-01-01:2024-03-31"
)

for filing in filings[:20]:
    eight_k = filing.obj()
    if eight_k.has_earnings:
        print(f"{filing.company}: {filing.filing_date}")
```

### Extract all financial tables

```python
if eight_k.has_earnings:
    for table in eight_k.earnings.financial_tables:
        print(f"{table.statement_type.value}: {table.dataframe.shape}")
```

### Check for specific events

```python
# Director changes
if 'Item 5.02' in eight_k.items:
    print(eight_k['5.02'])

# Material agreements
if 'Item 1.01' in eight_k.items:
    print(eight_k['1.01'])
```

---

## Metadata Quick Reference

| Property | Returns | Example |
|----------|---------|---------|
| `company` | Company name | `"Apple Inc."` |
| `form` | Form type | `"8-K"` |
| `filing_date` | Date filed with SEC | `"2024-02-01"` |
| `period_of_report` | Report date | `"2024-01-31"` |
| `date_of_report` | Formatted report date | `"January 31, 2024"` |
| `items` | List of disclosed items | `['Item 2.02', 'Item 9.01']` |
| `has_press_release` | Has EX-99 press release? | `True` |
| `has_earnings` | Has parseable earnings data? | `True` |

---

## Methods Quick Reference

| Call | Returns | What it does |
|------|---------|--------------|
| `eight_k['2.02']` | `str` | Get item content by number |
| `eight_k.press_releases` | `PressReleases` | Collection of press release exhibits |
| `eight_k.earnings` | `EarningsRelease` | Parsed earnings tables from EX-99.1 |
| `eight_k.income_statement` | `FinancialTable` | Income statement or None |
| `eight_k.balance_sheet` | `FinancialTable` | Balance sheet or None |
| `eight_k.cash_flow_statement` | `FinancialTable` | Cash flow statement or None |
| `eight_k.get_income_statement()` | `DataFrame` | Income statement (empty DataFrame if missing) |
| `eight_k.get_balance_sheet()` | `DataFrame` | Balance sheet (empty DataFrame if missing) |
| `eight_k.get_cash_flow_statement()` | `DataFrame` | Cash flow (empty DataFrame if missing) |

---

## Things to Know

**Item detection is multi-tier.** EdgarTools uses document parser first (95% accuracy), falls back to text extraction for legacy SGML filings (1999-2001).

**Earnings parsing requires EX-99.1.** The `has_earnings` property returns True only if Item 2.02 is present AND an EX-99.1 exhibit contains parseable tables. Some earnings 8-Ks only have narrative text.

**Scale matters.** Financial tables include scale detection (thousands, millions, billions). Use `scaled_dataframe` to get values with scale applied, or check `table.scale` to apply manually.

**Not all 8-Ks have XBRL.** 8-K filings typically contain only DEI (Document and Entity Information) XBRL metadata. Actual financial data is in HTML tables within EX-99 exhibits.

**Press releases use pattern matching.** EdgarTools looks for EX-99, EX-99.1, EX-99.01 exhibits or exhibits with "RELEASE" in the description. Some companies use non-standard exhibit numbering.

---

## Related

- [Working with Filings](guides/working-with-filing.md) -- general filing access patterns
- [10-K Annual Reports](tenk-filings.md) -- annual report parsing
- [10-Q Quarterly Reports](tenq-filings.md) -- quarterly report parsing
