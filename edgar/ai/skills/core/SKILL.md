---
name: EdgarTools
description: Query and analyze SEC filings and financial statements using EdgarTools. Get company data, filings, XBRL financials, and perform multi-company analysis.
---

# EdgarTools

Analyze SEC filings and financial statements using EdgarTools - a Python library for accessing and analyzing SEC EDGAR data.

## Overview

This guide covers essential SEC filing analysis operations. For detailed object representations and token estimates, see [objects.md](./objects.md). For end-to-end analysis workflows, see [workflows.md](./workflows.md). For installation and setup, see [README.md](./README.md).

## Prerequisites & Setup

**REQUIRED:** Before using EdgarTools, you must set your identity (SEC requirement):

```python
from edgar import set_identity
set_identity("Your Name your@email.com")
```

This identifies your application to the SEC. **Without this, all API calls will fail** with `"User-Agent identity is not set"` error.

## ⚡ Token-Efficient API Usage

**ALWAYS use `.to_context()` first** to get concise summaries with available actions. This is 5-10x more token-efficient than printing full objects.

### Company.to_context()

```python
from edgar import Company

company = Company("AAPL")
print(company.to_context())  # ~88 tokens vs 200+ for full object
```

**Output:**
```
**Company:** Apple Inc.
**CIK:** 0000320193
**Ticker:** AAPL
**Exchange:** Nasdaq
**Industry:** Electronic Computers (SIC 3571)
**Fiscal Year End:** Sep 30
```

### Filings.to_context()

```python
filings = company.get_filings(form="10-K")
print(filings.to_context())  # ~95 tokens vs 500-1000 for rich table
```

Shows summary + **AVAILABLE ACTIONS** (what methods to call next).

### Filing.to_context()

```python
filing = filings.latest()
print(filing.to_context())  # ~109 tokens, includes available methods
```

### XBRL.to_context()

```python
xbrl = filing.xbrl()
print(xbrl.to_context())  # ~275 tokens vs 2,500+ for full statements
```

**Token Comparison:**

| Object | Full Output | to_context() | Savings |
|--------|-------------|--------------|---------|
| Company | ~200 tokens | ~88 tokens | 56% |
| Filings | ~500-1000 | ~95 tokens | 80-90% |
| XBRL | ~2,500 tokens | ~275 tokens | 89% |

**Pattern:** Always use `to_context()` first → See what's available → Access specific data as needed.

## Quick Start

Most common patterns for getting started quickly. **Use `.to_context()` for token-efficient exploration.**

### Get a Company

```python
from edgar import set_identity, Company

set_identity("Your Name your@email.com")  # Required first!

company = Company("AAPL")
print(company.to_context())  # Concise profile (~88 tokens)
# OR for full details:
# print(company)  # Full object (~200 tokens)
```

### Get Recent Filings

```python
from edgar import get_current_filings

filings = get_current_filings()  # Last ~24 hours
print(filings.to_context())  # Summary + available actions (~95 tokens)
# OR to see first 5 in table:
# print(filings.head(5))  # Rich table (~500-1000 tokens)
```

### Get Financial Statements

```python
from edgar import Company

company = Company("AAPL")
income = company.income_statement(periods=3)  # 3 fiscal years
print(income)  # Full statement
```

## Core API Reference

Complete reference for main API functions and approaches.

### Getting Filings (3 Approaches)

Choose the approach based on your use case:

#### 1. Published Filings - Discovery & Bulk Analysis

**When to use**: Cross-company screening, pattern discovery, historical research, don't know which specific companies.

**Data source**: SEC quarterly indexes (updated nightly)

```python
from edgar import get_filings

# Get all filings for a quarter
filings = get_filings(2023, 1)  # Q1 2023

# Filter by form type
filings = get_filings(2023, 1, form="10-K")

# Filter by date range
filings = get_filings(2023, 1, filing_date="2023-02-01:2023-02-15")

# Further filter results
filtered = filings.filter(ticker="AAPL")
tech_filings = filings.filter(ticker=["AAPL", "MSFT", "GOOGL"])
```

#### 2. Current Filings - Real-time Monitoring

**When to use**: Monitoring recent filing activity, tracking latest submissions

**Data source**: SEC RSS feed (last ~24 hours)

```python
from edgar import get_current_filings

# Get all recent filings
current = get_current_filings()

# Filter by form type
reports = current.filter(form=["10-K", "10-Q"])

# Filter by specific companies
tech_current = current.filter(ticker=["AAPL", "MSFT"])
```

#### 3. Company Filings - Known Entity Analysis

**When to use**: You know the specific company ticker or name

**Data source**: SEC company submissions endpoint

```python
from edgar import Company

company = Company("AAPL")

# Get all filings
all_filings = company.get_filings()

# Filter by form type
annual_reports = company.get_filings(form="10-K")

# Filter by year
filings_2023 = company.get_filings(year=2023)

# Combine filters
q1_2023_10q = company.get_filings(year=2023, form="10-Q")
```

### Getting Financials (2 Approaches)

#### 1. Entity Facts API - Multi-Period Comparison

**When to use**: Comparing multiple periods, trend analysis (fastest approach)

**Data source**: SEC Company Facts API

**Advantages**:
- Very fast (single API call)
- Pre-aggregated data
- Multi-period comparison built-in

```python
from edgar import Company

company = Company("AAPL")

# Annual data (fiscal years)
income = company.income_statement(periods=3)  # Last 3 fiscal years
balance = company.balance_sheet(periods=3)
cash_flow = company.cash_flow_statement(periods=3)

# Quarterly data
quarterly_income = company.income_statement(periods=4, annual=False)  # Last 4 quarters
```

#### 2. Filing XBRL - Single Period Detail

**When to use**: Need specific filing details, want complete line items, analyzing single period

**Data source**: XBRL files attached to specific filings

**Advantages**:
- Most comprehensive detail
- All line items available
- Exact as-filed data

```python
from edgar import Company

company = Company("AAPL")

# Get specific filing
filing = company.get_filings(form="10-K")[0]  # Latest 10-K

# Parse XBRL
xbrl = filing.xbrl()

# Get statements
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()
cash_flow = xbrl.statements.cash_flow_statement()

# Access metadata
print(f"Entity: {xbrl.entity_name}")
print(f"Fiscal Year: {xbrl.fiscal_year}")
print(f"Period: {xbrl.fiscal_period}")
```

### Searching Filing Content

**⚠️ IMPORTANT**: Filing has TWO different search methods. Use the right one!

#### Content Search: `filing.search(query)` ⭐ Find Text in Filings

**Search the actual filing document** - find keywords, topics, or sections within SEC filings.

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="DEF 14A")[0]  # Proxy statement

# Search for content IN the filing
results = filing.search("executive compensation")

# Process results
print(f"Found {len(results)} matches")
for match in results[:5]:  # Top 5 matches
    print(f"Relevance score: {match.score:.2f}")
    print(f"Excerpt: {str(match)[:200]}...")
    print()
```

**Features**:
- BM25 relevance ranking (best matches first)
- Searches parsed HTML sections
- Returns `DocSection` objects with scores
- Index cached for performance (~1-2 seconds per filing)

**Use cases**:
- Find mentions of specific topics ("revenue recognition", "risk factors")
- Locate sections in large filings
- Screen filings for relevant content
- Extract context around keywords

**Example: Find proxy statements mentioning compensation changes**

```python
from edgar import get_filings
from datetime import datetime, timedelta

# Get recent proxy statements
start_date = datetime.now() - timedelta(days=30)
filings = get_filings(form="DEF 14A")
recent = filings.filter(filing_date=f"{start_date.strftime('%Y-%m-%d')}:")

# Search each filing
companies_with_matches = []
for filing in recent:
    matches = filing.search("executive compensation changes")

    if matches and len(matches) > 0:
        companies_with_matches.append({
            'company': filing.company,
            'date': filing.filing_date,
            'matches': len(matches),
            'top_score': matches[0].score,
            'excerpt': str(matches[0])[:200]
        })

print(f"Found {len(companies_with_matches)} companies")
```

#### API Documentation Search: `filing.docs.search(query)` 📚 Find Methods

**Search the Filing API documentation** - discover how to use the Filing class.

```python
# Find how to use Filing API
help_text = filing.docs.search("how to get XBRL")
print(help_text)  # Shows documentation about filing.xbrl() method

help_text = filing.docs.search("convert to markdown")
print(help_text)  # Shows documentation about filing.markdown() method
```

**Use cases**:
- Learning the Filing API
- Discovering available methods
- Finding parameter details

#### Quick Reference

| What are you searching? | Method | Returns |
|-------------------------|--------|---------|
| Text **in** the filing (content) | `filing.search("keyword")` | List of DocSection matches with scores |
| How to **use** Filing API (methods) | `filing.docs.search("how to")` | API documentation snippets |

**⚠️ Common Mistake**:
```python
# WRONG - Searches API docs, not filing content!
matches = filing.docs.search("executive compensation")  # ❌
# Returns empty - API docs don't mention "executive compensation"

# CORRECT - Searches the actual filing document
matches = filing.search("executive compensation")  # ✅
# Returns 50+ matches from proxy statement
```

## Quick Reference

For complete examples with full code, see **[common-questions.md](common-questions.md)**.

| Task | Primary Method | Example |
|------|----------------|---------|
| Show S-1 filings from date range | `get_filings(year, quarter, form="S-1", filing_date="...")` | [See example](common-questions.md#show-all-s-1-filings-from-february-2023) |
| Get today's filings | `get_current_filings()` | [See example](common-questions.md#whats-been-filed-today) |
| Get company revenue trend | `company.income_statement(periods=3)` | [See example](common-questions.md#get-apples-revenue-for-last-3-fiscal-years) |
| Get quarterly financials | `company.income_statement(periods=4, annual=False)` | [See example](common-questions.md#teslas-quarterly-net-income-trend-4-quarters) |
| Get statement from specific filing | `filing.xbrl().statements.income_statement()` | [See example](common-questions.md#full-income-statement-from-apples-2023-10-k) |
| Compare multiple companies | `compare_companies_revenue(["AAPL", "MSFT"])` | [See example](common-questions.md#compare-apple-and-microsoft-revenue) |
| Get latest quarterly balance sheet | `company.get_filings(form="10-Q")[0].xbrl()` | [See example](common-questions.md#get-balance-sheet-from-latest-10-q) |
| Get insider transactions (Form 4) | `company.get_filings(form="4")` | [See example](common-questions.md#get-all-form-4-insider-transactions-for-aapl) |
| Filter filings efficiently | `filings.filter(ticker="AAPL", filing_date="2024-01-01:")` | [See example](common-questions.md#when-to-use-filter-vs-python-filtering) |
| Look up form types | `describe_form("C")` or see form-types-reference.md | [See example](common-questions.md#dont-know-the-form-type-look-it-up) |

**Pattern**: For any question, check [common-questions.md](common-questions.md) for full working examples.

## Advanced Topics

For advanced patterns, helper functions, error handling, and skill exportation, see **[advanced-guide.md](advanced-guide.md)**.

**Includes:**
- Filtering and pagination
- Multi-company analysis
- Error handling patterns
- Working with filing documents
- Helper functions reference
- Exporting skills for Claude Desktop
- Creating custom external skills

## Troubleshooting

Common errors and solutions.

### "User-Agent identity is not set"

**Error:**
```
RuntimeError: User-Agent identity is not set. Please call set_identity() first.
```

**Cause:** Missing `set_identity()` call (SEC requirement)

**Solution:**
```python
from edgar import set_identity
set_identity("Your Name your@email.com")  # Must call before any API operations
```

### AttributeError on Company object

**Error:**
```
AttributeError: 'Company' object has no attribute 'sic_code'
```

**Cause:** Incorrect attribute name

**Solution:** Check the [API reference in objects.md](objects.md) for correct attribute names (e.g., use `company.sic` instead of `company.sic_code`)

### Using too many tokens?

**Problem:** Agent consuming excessive tokens for simple queries

**Cause:** Not using `.to_context()` method

**Solution:** Always call `.to_context()` before printing full objects:
```python
# Instead of:
print(company)  # 200+ tokens

# Use:
print(company.to_context())  # ~88 tokens
```

### Empty filings result

**Problem:** `get_filings()` returns empty list

**Possible causes:**
1. No filings match the criteria (try broader search)
2. Wrong quarter/year combination
3. Form type doesn't exist for that period

**Solution:**
```python
filings = get_filings(2024, 1, form="10-K")
if len(filings) == 0:
    print("No filings found - try different criteria")
    # Try broader search
    all_filings = get_filings(2024, 1)
    print(f"Found {len(all_filings)} total filings in 2024 Q1")
```

## See Also

- [Common Questions](common-questions.md) - Complete examples with full code for common tasks
- [Advanced Guide](advanced-guide.md) - Advanced patterns, helper functions, and skill exportation
- [Quick Start by Task](quickstart-by-task.md) - Fast task routing (< 30 seconds)
- [Object Reference](objects.md) - Object representations and token size estimates
- [Workflows](workflows.md) - End-to-end analysis patterns
- [Form Types Reference](form-types-reference.md) - Complete SEC form catalog (311 forms)
- [README](readme.md) - Installation and package overview

## Rate Limiting

EdgarTools automatically handles SEC rate limiting (10 requests/second):
- Built-in rate limiting
- Request caching to reduce API calls
- Large batch operations may take time due to rate limits
