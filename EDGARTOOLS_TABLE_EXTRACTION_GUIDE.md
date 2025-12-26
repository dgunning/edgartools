# EdgarTools Table Extraction: Complete Guide

**Date:** 2025-12-24
**Purpose:** Document ALL table extraction capabilities in EdgarTools

---

## Executive Summary

**YES**, EdgarTools has **5 different ways** to extract tables:

1. **XBRL Financial Statements** (BalanceSheet, IncomeStatement, etc.) - BEST for financials
2. **Document.tables** (HTML table nodes) - For all HTML tables in filings
3. **llm_extraction.py** (Markdown extraction) - For Item-based extraction
4. **13F Holdings Tables** (Specialized) - For institutional holdings
5. **Ownership Forms** (Forms 3/4/5) - For insider transactions

Each approach serves different use cases.

---

## 1. XBRL Financial Statements ⭐ BEST FOR FINANCIALS

### Overview

The **primary and most reliable way** to extract financial tables from 10-K/10-Q filings.

### How It Works

XBRL (eXtensible Business Reporting Language) is the structured data format that companies submit alongside HTML filings. EdgarTools parses this XBRL data into clean, structured financial statements.

### Access Methods

#### Method 1: Via Filing.xbrl()

```python
from edgar import Company

# Get filing
company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Get XBRL object
xbrl = filing.xbrl()

# Get specific statements
balance_sheet = xbrl.balance_sheet
income_statement = xbrl.income_statement
cash_flow = xbrl.cash_flow_statement

# Display as table
print(balance_sheet)

# Convert to DataFrame
df = balance_sheet.to_dataframe()
```

#### Method 2: Via TenK/TenQ Shortcuts

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Get typed object
tenk = filing.obj()

# Direct access to statements
balance_sheet = tenk.balance_sheet
income_statement = tenk.income_statement
cash_flow = tenk.cash_flow_statement

# Display
print(income_statement)

# To DataFrame
df = income_statement.to_dataframe()
```

### Available Statements

```python
# Core financial statements
xbrl.balance_sheet              # Balance Sheet
xbrl.income_statement            # Income Statement
xbrl.cash_flow_statement         # Cash Flow Statement
xbrl.statement_of_equity         # Statement of Stockholders' Equity
xbrl.comprehensive_income        # Comprehensive Income

# Search for statements
statements = xbrl.statements     # All statements
statement = xbrl.find_statement("Revenue")  # Find by keyword

# Fund-specific (for mutual funds)
xbrl.fund_statements             # Fund-specific statements
```

### Features

✅ **Structured Data** - Clean pandas DataFrames
✅ **Multi-Period** - Automatic period alignment (2024, 2023, 2022)
✅ **Type-Safe** - Numeric values properly typed
✅ **Hierarchical** - Preserves account hierarchy (Assets → Current Assets → Cash)
✅ **Standardized** - Maps to standard concepts (Revenue, Net Income, etc.)
✅ **Footnote Links** - Preserves footnote references
✅ **No HTML Parsing** - Direct from XBRL data

### Example Output

```python
# Balance Sheet
balance_sheet = tenk.balance_sheet
print(balance_sheet)
```

Output:
```
                                             2024           2023           2022
Assets
  Current assets:
    Cash and cash equivalents           $29,943,000    $24,977,000    $23,646,000
    Marketable securities                31,590,000     31,590,000     24,658,000
    Accounts receivable, net             29,508,000     29,508,000     28,184,000
    Inventories                           6,511,000      6,331,000      4,946,000
    Vendor non-trade receivables         31,477,000     32,748,000     32,748,000
    Other current assets                 14,695,000     14,695,000     21,223,000
  Total current assets                  143,724,000    139,849,000    135,405,000
  ...
```

### DataFrame Export

```python
df = balance_sheet.to_dataframe()

# DataFrame structure:
# Index: Account names (hierarchical)
# Columns: Years (2024, 2023, 2022)
# Values: Numeric amounts

# Example operations
df.loc["Total assets"]                    # Get total assets row
df["2024"]                                # Get 2024 column
df.to_csv("balance_sheet.csv")            # Export to CSV
df.to_excel("balance_sheet.xlsx")         # Export to Excel
```

### Use Cases

- ✅ Extract financial ratios
- ✅ Time series analysis
- ✅ Financial modeling
- ✅ Comparative analysis across companies
- ✅ Automated reporting
- ✅ Machine learning on financial data

---

## 2. Document.tables (HTML Table Nodes)

### Overview

Extract ALL HTML tables from a filing, including:
- Financial statement tables (HTML versions)
- Footnote tables
- Schedule tables
- Other tabular data

### Access

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Get document
doc = filing.obj().document

# Get all tables
tables = doc.tables  # List of TableNode objects

print(f"Total tables: {len(tables)}")

# Iterate through tables
for i, table in enumerate(tables):
    print(f"\nTable {i+1}:")
    print(f"  Caption: {table.caption}")
    print(f"  Type: {table.table_type}")
    print(f"  Rows: {len(table.rows)}")
    print(f"  Headers: {len(table.headers)}")
```

### TableNode Properties

```python
table = tables[0]

# Metadata
table.caption        # Table caption/title
table.table_type     # TableType enum (FINANCIAL, NOTE, etc.)
table.headers        # List of header rows
table.rows           # List of data rows
table.footer         # Footer rows

# Check properties
table.has_row_headers   # Does first column have labels?
table.is_financial      # Is this a financial table?

# Export
df = table.to_dataframe()      # Pandas DataFrame
csv = table.to_csv()           # CSV string
dict_data = table.to_dict()    # Dictionary
```

### Example: Finding Tables

```python
# Get all financial tables
financial_tables = [t for t in doc.tables if t.table_type.name == "FINANCIAL"]

# Get tables with specific caption
revenue_tables = [t for t in doc.tables if "revenue" in (t.caption or "").lower()]

# Get tables from specific section
section = doc.sections.get_item("8")  # Item 8
section_tables = section.tables()      # Tables in this section
```

### Convert to DataFrame

```python
table = tables[0]
df = table.to_dataframe()

# Features:
# - Automatic colspan/rowspan handling
# - Multi-row header support (MultiIndex)
# - Numeric value parsing
# - Currency symbol handling
```

### Use Cases

- ✅ Extract footnote tables
- ✅ Get schedule tables (debt maturity, lease obligations)
- ✅ Extract supplementary data
- ✅ Get non-XBRL tables (older filings, exhibits)

### Limitations

⚠️ **Section Attribution Bug** - As discovered in PLTR test, tables may not correctly associate with sections
⚠️ **Basic Preprocessing** - No currency/percent cell merging like llm_extraction
⚠️ **No Deduplication** - May have duplicate tables

---

## 3. llm_extraction.py (Item-Based Markdown Extraction)

### Overview

Extract content (including tables) from specific Items in 10-K/10-Q/20-F/8-K filings as clean Markdown.

### Access

```python
from edgar import Company
from edgar.llm_extraction import extract_filing_sections

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Extract specific items
sections = extract_filing_sections(
    filing,
    item=["Item 1", "Item 7", "Item 8"]
)

for section in sections:
    print(f"\n{section.title}")
    print(f"Source: {section.source}")
    print(f"Length: {len(section.markdown):,} chars")

    # Save to file
    with open(f"{section.title}.md", "w") as f:
        f.write(section.markdown)
```

### Extract Tables as Markdown

```python
# Extract Item 8 (Financial Statements)
sections = extract_filing_sections(filing, item=["Item 8"])

markdown = sections[0].markdown

# Tables are in markdown format:
"""
#### Table: Consolidated Balance Sheets
| label | 2024 | 2023 |
| --- | --- | --- |
| Cash and cash equivalents | $29,943 | $24,977 |
| Total assets | $364,980 | $352,755 |
"""
```

### Features

✅ **Item-Based Extraction** - Extract by Item number
✅ **Markdown Output** - Clean, readable format
✅ **Currency Merging** - `$` symbols merged: `$29,943`
✅ **Table Deduplication** - Removes duplicate tables
✅ **Smart Headers** - Auto-detects headers from dates/patterns
✅ **Text + Tables** - Integrated content (not just tables)
✅ **Multiple Forms** - Works with 10-K, 10-Q, 20-F, 8-K, 6-K

### Table Extraction Features

```python
# Extract only statements (XBRL)
sections = extract_filing_sections(
    filing,
    statement=["BalanceSheet", "IncomeStatement"]
)

# Extract by category
sections = extract_filing_sections(
    filing,
    category="Statements"  # or "Notes", "Financial"
)

# Include notes
sections = extract_filing_sections(
    filing,
    item=["Item 8"],
    notes=True  # Include note sections
)
```

### Use Cases

- ✅ LLM/AI workflows (clean markdown)
- ✅ Document generation
- ✅ Content extraction for RAG systems
- ✅ Section-based analysis
- ✅ Export to documentation

### Limitations

⚠️ **Percent Merging Bug** - Spaces in percentages: `55.2 %` instead of `55.2%`
⚠️ **Markdown Only** - No DataFrame export
⚠️ **No Structured Data** - Tables are text, not typed data

---

## 4. 13F Holdings Tables (Institutional Holdings)

### Overview

Extract holdings tables from Form 13F (institutional investment managers).

### Access

```python
from edgar import Company

company = Company("BRK-A")  # Berkshire Hathaway
filings = company.get_filings(form="13F-HR")

filing = filings[0]
thirteenf = filing.obj()

# Get holdings table
holdings = thirteenf.holdings

# Display
print(holdings)

# To DataFrame
df = holdings.to_dataframe()
```

### Holdings Data

```python
df = holdings.to_dataframe()

# Columns:
# - Name of Issuer
# - Title of Class
# - CUSIP
# - Value (x$1000)
# - Shares/Principal Amount
# - Put/Call
# - Investment Discretion
# - Voting Authority
```

### Features

✅ **Specialized Parser** - Handles 13F XML format
✅ **Complete Holdings** - All positions
✅ **Structured Data** - Clean DataFrame
✅ **Sorted** - By value (largest holdings first)

### Use Cases

- ✅ Track institutional ownership
- ✅ Analyze hedge fund positions
- ✅ Portfolio analysis
- ✅ Ownership trends

---

## 5. Ownership Forms (Forms 3/4/5)

### Overview

Extract transaction tables from insider trading forms.

### Access

```python
from edgar import Company

company = Company("TSLA")
filings = company.get_filings(form="4")  # Form 4 - insider transactions

filing = filings[0]
form4 = filing.obj()

# Get transactions
transactions = form4.non_derivative_transactions
derivative_transactions = form4.derivative_transactions

# Get holdings
holdings = form4.non_derivative_holdings
```

### Transaction Data

```python
# Non-derivative transactions (common stock, etc.)
for txn in form4.non_derivative_transactions:
    print(f"Security: {txn.security_title}")
    print(f"Date: {txn.transaction_date}")
    print(f"Code: {txn.transaction_code}")  # P=Purchase, S=Sale
    print(f"Shares: {txn.transaction_shares}")
    print(f"Price: {txn.transaction_price_per_share}")
    print(f"Shares Owned: {txn.shares_owned_following_transaction}")
```

### Features

✅ **Structured Transactions** - All insider trades
✅ **Multiple Tables** - Derivative and non-derivative
✅ **Ownership Tracking** - Shares owned before/after
✅ **Type-Safe** - Typed transaction objects

### Use Cases

- ✅ Track insider buying/selling
- ✅ Ownership analysis
- ✅ Corporate governance research

---

## Comparison Matrix

| Method | Data Type | Output Format | Use Case | Complexity |
|--------|-----------|---------------|----------|------------|
| **XBRL Statements** | Financial data | DataFrame | Financial analysis | Easy ⭐ |
| **Document.tables** | All HTML tables | TableNode/DataFrame | General tables | Medium |
| **llm_extraction** | Item content | Markdown | LLM/AI workflows | Easy |
| **13F Holdings** | Institutional holdings | DataFrame | Portfolio tracking | Easy |
| **Ownership Forms** | Insider transactions | Structured objects | Insider tracking | Easy |

---

## Quick Reference

### Get Balance Sheet (Easiest)

```python
from edgar import Company

filing = Company("AAPL").get_filings(form="10-K")[0]
balance_sheet = filing.obj().balance_sheet
df = balance_sheet.to_dataframe()
```

### Get All Tables in Filing

```python
from edgar import Company

filing = Company("AAPL").get_filings(form="10-K")[0]
tables = filing.obj().document.tables

for table in tables:
    df = table.to_dataframe()
    print(f"{table.caption}: {df.shape}")
```

### Get Item 8 as Markdown

```python
from edgar import Company
from edgar.llm_extraction import extract_filing_sections

filing = Company("AAPL").get_filings(form="10-K")[0]
sections = extract_filing_sections(filing, item=["Item 8"])
markdown = sections[0].markdown
```

### Get 13F Holdings

```python
from edgar import Company

filing = Company("BRK-A").get_filings(form="13F-HR")[0]
holdings = filing.obj().holdings
df = holdings.to_dataframe()
```

---

## Recommendations by Use Case

### Financial Analysis & Modeling
**Use:** XBRL Statements (`filing.obj().balance_sheet`)
- Clean, structured data
- Multi-period alignment
- Type-safe numeric values
- Industry standard

### LLM/AI Workflows
**Use:** llm_extraction (`extract_filing_sections()`)
- Clean Markdown output
- Context-aware extraction
- Item-based chunking
- Ready for RAG systems

### General Table Extraction
**Use:** Document.tables (`filing.obj().document.tables`)
- Access all tables
- Footnotes and schedules
- Flexible filtering
- DataFrame export

### Institutional Holdings Tracking
**Use:** 13F parser (`filing.obj().holdings`)
- Specialized for 13F
- Complete holdings data
- Easy to analyze

### Insider Trading Monitoring
**Use:** Ownership Forms (`filing.obj().transactions`)
- Structured transaction data
- Real-time tracking
- Ownership changes

---

## Example: Extract All Financial Tables

```python
from edgar import Company

def extract_all_financial_tables(ticker: str, form: str = "10-K"):
    """Extract all financial tables from a filing"""

    company = Company(ticker)
    filing = company.get_filings(form=form)[0]

    results = {}

    # Method 1: XBRL Statements (BEST for financials)
    try:
        xbrl = filing.xbrl()
        results['balance_sheet'] = xbrl.balance_sheet.to_dataframe()
        results['income_statement'] = xbrl.income_statement.to_dataframe()
        results['cash_flow'] = xbrl.cash_flow_statement.to_dataframe()
    except Exception as e:
        print(f"XBRL extraction failed: {e}")

    # Method 2: HTML Tables (for supplementary data)
    doc = filing.obj().document
    financial_tables = [
        t for t in doc.tables
        if t.table_type.name == "FINANCIAL"
    ]

    for i, table in enumerate(financial_tables):
        results[f'html_table_{i}'] = table.to_dataframe()

    # Method 3: Markdown (for LLM processing)
    from edgar.llm_extraction import extract_filing_sections
    sections = extract_filing_sections(filing, item=["Item 8"])
    results['markdown'] = sections[0].markdown if sections else None

    return results

# Usage
tables = extract_all_financial_tables("AAPL")
print(f"Extracted {len(tables)} tables")
```

---

## Known Issues

### Document.tables Section Attribution Bug ❌
**Issue:** Tables not correctly associated with sections
**Impact:** `section.tables()` may return 0 tables even when tables exist
**Workaround:** Use `doc.tables` and filter manually

**Example:**
```python
# BROKEN - May return 0 tables
section = doc.sections.get_item("8")
tables = section.tables()  # Returns []

# WORKAROUND - Get all tables and filter
all_tables = doc.tables
# Filter by position or caption
item8_tables = [t for t in all_tables if "consolidated" in (t.caption or "").lower()]
```

### llm_extraction Percent Merging Bug ❌
**Issue:** Spaces before % symbols
**Impact:** `55.2 %` instead of `55.2%`
**Workaround:** Post-process markdown

```python
markdown = sections[0].markdown
# Fix percent spacing
markdown = markdown.replace(" %", "%")
```

---

## Best Practices

### 1. Prefer XBRL for Financial Statements

```python
# GOOD - Use XBRL
balance_sheet = filing.obj().balance_sheet
df = balance_sheet.to_dataframe()

# AVOID - Parsing HTML tables for financial statements
tables = filing.obj().document.tables
# ... complex filtering and parsing ...
```

### 2. Use llm_extraction for LLM Workflows

```python
# GOOD - Clean markdown for LLMs
from edgar.llm_extraction import extract_filing_sections
sections = extract_filing_sections(filing, item=["Item 7"])
context = sections[0].markdown

# AVOID - Extracting HTML for LLMs
html = filing.html()
# ... complex HTML parsing ...
```

### 3. Cache Results

```python
# Tables are expensive to parse - cache them
from functools import lru_cache

@lru_cache(maxsize=100)
def get_balance_sheet(ticker: str, filing_date: str):
    company = Company(ticker)
    filing = company.get_filings(form="10-K")[0]
    return filing.obj().balance_sheet.to_dataframe()
```

---

## Summary

**EdgarTools has excellent table extraction capabilities:**

1. ⭐ **XBRL Statements** - Best for financial data (Balance Sheet, Income Statement, etc.)
2. **Document.tables** - All HTML tables (with known bugs)
3. **llm_extraction** - Clean Markdown for Items (best for AI/LLM)
4. **13F Holdings** - Specialized for institutional portfolios
5. **Ownership Forms** - Insider transactions

**Choose based on your use case:**
- Financial analysis → XBRL Statements
- LLM/AI → llm_extraction
- General tables → Document.tables
- Holdings → 13F parser
- Insider trades → Ownership Forms

**All methods export to pandas DataFrame for further analysis.**
