---
name: EdgarTools Object Reference
description: Reference guide for EdgarTools object representations - what AI agents can expect from each object type with token size estimates.
---

# EdgarTools Object Reference

## Overview

EdgarTools objects use `repr()` to display information in the terminal. All representations are plain text with Unicode box drawing characters - no ANSI escape codes, making them AI-friendly.

**Token Estimation**: All estimates use a 4 characters/token heuristic (conservative approximation).

**Documentation Tiers**:
1. **This Guide** - Quick reference with token estimates and output formats
2. **API Reference** - Detailed method documentation (see `api-reference/` directory)
   - [Company API](./api-reference/Company.md) - Complete Company class reference
   - [Filing API](./api-reference/EntityFiling.md) - Complete Filing reference
   - [Filings Collection API](./api-reference/EntityFilings.md) - Filings collection reference
   - [XBRL API](./api-reference/XBRL.md) - Complete XBRL class reference
   - [Statement API](./api-reference/Statement.md) - Complete Statement class reference

Use this guide to understand object structure and token costs, then reference the API docs for detailed method usage.

## AI-Optimized Access Methods

EdgarTools provides multiple ways to access information, each optimized for different use cases:

### 1. Quick Visual Overview (`repr()` / `print()`)

**Available on**: All objects

Every EdgarTools object has a rich terminal representation using Unicode box drawing:

```python
from edgar import Company

company = Company("AAPL")
print(company)  # Shows formatted company profile
```

**When to Use**: Quick overview, visual verification, understanding structure

### 2. AI-Optimized Text Format (`.text()`)

**Available on**: Company, XBRL only

**Important**: Not all objects have AI-optimized `.text()` methods. Only Company and XBRL provide this feature.

Objects with AI-optimized `.text()`:
- **Company**: Markdown-KV format (60.7% accuracy, 25% fewer tokens than JSON)
- **XBRL**: Markdown-KV format for metadata

Research basis: [Best Input Data Format for LLMs](https://improvingagents.com/blog/best-input-data-format-for-llms)

**Usage**:

```python
from edgar import Company

company = Company("AAPL")

# Get AI-optimized text (Markdown-KV format)
text = company.text(max_tokens=2000)
print(text)
# **Company:** Apple Inc.
# **CIK:** 0000320193
# **Ticker:** AAPL
# ...

# XBRL also has AI-optimized text
filing = company.get_filings(form="10-K")[0]
xbrl = filing.xbrl()
xbrl_text = xbrl.text(max_tokens=2000)
```

**Benefits**:
- **Token Efficient**: 25% fewer tokens than JSON for same information
- **Higher Accuracy**: 60.7% vs 54.7% (JSON) in research benchmarks
- **Token Control**: `max_tokens` parameter with automatic truncation
- **Format Optimized**: Markdown-KV for maximum LLM comprehension

**Special Note About Filing.text()**: Filing has a `.text()` method, but it returns the full filing document text (potentially 50K+ tokens), NOT AI-optimized metadata. For Filing metadata, use `repr()` or `.docs`.

### 3. Comprehensive Documentation (`.docs`)

**Available on**: All major objects (Company, Filing, EntityFiling, Filings, EntityFilings, XBRL, Statement)

All major EdgarTools objects provide a `.docs` property for comprehensive API documentation with semantic search:

```python
from edgar import Company

company = Company("AAPL")

# Access comprehensive documentation
company.docs  # Shows full API guide with Common Actions

# Search for specific topics
company.docs.search("get_filings")  # Find filing-related methods
company.docs.search("facts")        # Find facts-related sections
company.docs.search("ticker")       # Find ticker usage

# Same for other objects
filing = company.get_filings(form="10-K")[0]
filing.docs                         # Filing API guide
filing.docs.search("XBRL")         # How to get XBRL from filing

filings = company.get_filings()
filings.docs                       # EntityFilings API guide
filings.docs.search("filter")      # How to filter filings

xbrl = filing.xbrl()
xbrl.docs                          # XBRL API guide
xbrl.docs.search("statements")     # How to access statements
```

**Documentation Features**:
- **Common Actions**: Quick reference for most frequent operations
- **Searchable**: BM25 semantic search finds relevant sections
- **Comprehensive**: Complete API reference with examples
- **Contextual**: Shows methods, properties, workflows, and best practices

**When to Use .docs**:
- Discovering available methods and properties
- Finding usage examples for complex operations
- Learning API patterns and workflows
- Searching for specific functionality

**Documentation Features**:
- **Common Actions**: Quick reference for most frequent operations
- **Searchable**: BM25 semantic search finds relevant sections
- **Comprehensive**: Complete API reference with examples
- **Contextual**: Shows methods, properties, workflows, and best practices

**Token Estimates**:
- Full `.docs` display: 2,000-5,000 tokens (depending on class)
- Search results: 200-500 tokens per matching section
- Hint in `repr()`: Adds ~15 tokens to display

## Summary of Access Methods

**Recommended Pattern**: `repr()` + `.docs` + `.docs.search()`

This is the current recommended approach for API discovery and working with EdgarTools objects. The `.text()` method is only available on Company and XBRL for specialized AI data extraction.

| Method | Available On | Purpose | Token Range |
|--------|--------------|---------|-------------|
| `print(obj)` or `repr()` | All objects | Quick visual overview | 125-2,500 |
| `obj.docs` | All major objects | **Primary:** API discovery & learning | 2,000-5,000 |
| `obj.docs.search(query)` | All major objects | **Primary:** Find specific functionality | 200-500 |
| `obj.text(max_tokens)` | Company, XBRL only | **Specialized:** AI-optimized data extraction | 500-2,000 |

---

### ⚠️ IMPORTANT: Two Different Search Methods

Filing has **TWO search methods** with different purposes. Don't confuse them!

#### Content Search: `filing.search(query)` ⭐ Most Common Use Case

**Search the actual filing document text** (10-K content, proxy statements, 8-K reports, etc.)

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="DEF 14A")[0]  # Proxy statement

# Search for text IN the filing document
results = filing.search("executive compensation")
results = filing.search("risk factors")
results = filing.search("revenue recognition")

# Returns: List of DocSection objects with BM25 relevance scores
print(f"Found {len(results)} matches")
for match in results[:3]:  # Top 3 matches
    print(f"Score {match.score:.2f}: {str(match)[:100]}...")
```

**When to use**: Finding content, keywords, or topics within SEC filings

**Performance**: ~1-2 seconds per filing (BM25 index cached)

#### API Documentation Search: `filing.docs.search(query)` 📚 Developer Helper

**Search the Filing class API documentation** to discover methods and usage

```python
# Find how to use the Filing API
help_text = filing.docs.search("how to get XBRL")
help_text = filing.docs.search("convert to markdown")
help_text = filing.docs.search("list attachments")

# Returns: Documentation snippets about Filing methods
print(help_text)
```

**When to use**: Learning the API, discovering available methods

#### Quick Reference

| Search What? | Method | Example |
|--------------|--------|---------|
| Filing content (text inside 10-K, proxy, etc.) | `filing.search("keyword")` | `filing.search("risk factors")` |
| API documentation (how to use Filing class) | `filing.docs.search("how to")` | `filing.docs.search("get xbrl")` |

**Rule of thumb**:
- Looking for content **IN** the filing? → `filing.search()`
- Looking for how to **USE** the Filing API? → `filing.docs.search()`

---

## Company Object

**Typical Size**: ~3,000 characters
**Token Estimate**: ~750 tokens
**Format**: Unicode box drawing with information panels
**Has .docs**: ✅ Yes
**Has .text()**: ✅ Yes (AI-optimized Markdown-KV)

**Contains**:
- Entity name and identifiers (CIK, ticker, EIN)
- Exchange listings (NYSE, NASDAQ, OTC, etc.)
- Business address and mailing address
- Contact information (phone number, website if available)
- Former company names (if applicable)
- SIC code and industry description
- Docs hint in subtitle

**Example**:
```python
from edgar import Company

company = Company("AAPL")
print(company)  # Shows full company profile with box drawing

# Access documentation
company.docs  # Comprehensive API guide
company.docs.search("get_filings")  # Find filing methods

# Get AI-optimized text
company.text(max_tokens=1000)  # Markdown-KV format
```

**Sample Output Structure**:
```
╭──────────────────────────────────────────╮
│ Apple Inc.                               │
│ CIK: 0000320193                          │
│ Ticker: AAPL (NASDAQ)                    │
│ SIC: 3571 - Electronic Computers         │
├──────────────────────────────────────────┤
│ Business Address                         │
│ One Apple Park Way                       │
│ Cupertino, CA 95014                      │
│ Phone: 408-996-1010                      │
╰──────────────────────────────────────────╯
```

**When to Use**:
- Need complete company profile
- Verifying company identity
- Getting contact information

## Filing Object

**Typical Size**: ~500 characters
**Token Estimate**: ~125 tokens
**Format**: Unicode box drawing with key metadata
**Has .docs**: ✅ Yes
**Has .text()**: ⚠️ Yes, but returns filing document text (not AI metadata)

**Contains**:
- Form type (10-K, 10-Q, 8-K, S-1, etc.)
- Company name and CIK
- Accession number (unique filing identifier)
- Filing date and acceptance datetime
- Period of report (for periodic filings)
- Document count
- Docs hint in subtitle

**Example**:
```python
from edgar import Company

company = Company("AAPL")
filings = company.get_filings(form="10-K")
filing = filings[0]
print(filing)  # Shows filing metadata

# Access documentation
filing.docs  # Comprehensive Filing API guide
filing.docs.search("XBRL")  # How to get XBRL

# Note: filing.text() returns document content, not metadata
text = filing.text()  # Returns full filing document text
```

**Sample Output Structure**:
```
╭──────────────────────────────────────────╮
│ Form 10-K                                │
│ Apple Inc. (CIK: 0000320193)             │
│ Filed: 2023-11-03                        │
│ Period: 2023-09-30                       │
│ Accession: 0000320193-23-000106          │
│ Documents: 125                           │
╰──────────────────────────────────────────╯
```

**When to Use**:
- Identifying specific filing
- Getting filing metadata
- Verifying filing date/period

## Filings Collection

**Typical Size**: Varies by result count (default: first 3 shown)
**Token Estimate**: ~200-300 tokens for 3 filings
**Format**: Unicode table with columns
**Has .docs**: ✅ Yes (EntityFilings has .docs, base Filings has .docs)
**Has .text()**: ❌ No

**Contains**:
- Tabular view of multiple filings
- Company name, CIK, form type
- Filing date and period of report
- Pagination information
- Docs hint in subtitle (EntityFilings only)

**Example**:
```python
from edgar import Company

company = Company("AAPL")
filings = company.get_filings(form="10-K")  # Returns EntityFilings
print(filings.head(3))  # Shows first 3 filings in table format

# Access documentation
filings.docs  # Comprehensive EntityFilings API guide
filings.docs.search("filter")  # How to filter filings
filings.docs.search("latest")  # How to get latest filing
```

**Sample Output Structure**:
```
                         Filings
┏━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Form ┃ Company        ┃ CIK       ┃ Filed      ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ 10-K │ Apple Inc.     │ 0000320193│ 2023-11-03 │
│ 10-K │ Microsoft Corp │ 0000789019│ 2023-07-27 │
│ 10-K │ Google LLC     │ 0001652044│ 2023-02-02 │
└──────┴────────────────┴───────────┴────────────┘
Showing 3 of 1,245 filings
```

**When to Use**:
- Browsing multiple filings
- Comparing filing dates
- Identifying patterns across companies

**Tip**: Use `.head(n)` to limit output and reduce token usage.

## XBRL Object

**Typical Size (repr)**: ~3,000 characters (visual box drawing)
**Typical Size (.text())**: ~1,100 characters (AI-optimized)
**Token Estimate (repr)**: ~750 tokens
**Token Estimate (.text())**: ~275 tokens
**Format**: Markdown-KV (AI-optimized) via .text(), Unicode box drawing via repr()
**Has .docs**: ✅ Yes
**Has .text()**: ✅ Yes (AI-optimized Markdown-KV)

**Contains**:
- Entity information (name, ticker, CIK)
- Document metadata (type, fiscal year/period)
- Fact and context counts
- Available data coverage (annual/quarterly periods)
- Core financial statements availability
- Common usage patterns
- Docs hint

**Example**:
```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
xbrl = filing.xbrl()

# Visual display (Unicode box drawing)
print(xbrl)  # Shows comprehensive XBRL structure

# AI-optimized text (Markdown-KV format)
text = xbrl.text()  # Compact, token-efficient
print(text)

# Access documentation
xbrl.docs  # Comprehensive XBRL API guide
xbrl.docs.search("statements")  # How to access statements
xbrl.docs.search("facts")  # How to query facts
```

**Sample .text() Output (AI-Optimized)**:
```
**Entity:** Apple Inc. (AAPL)
**CIK:** 320193
**Form:** 10-K
**Fiscal Period:** Fiscal Year 2025 (ended 2025-09-27)
**Facts:** 1,131
**Contexts:** 182

**Available Data Coverage:**
  Annual: FY 2025, FY 2024, FY 2023
  Quarterly: June 29, 2025 to September 27, 2025, June 30, 2024 to September 28, 2024

**Available Statements:**
  Core: IncomeStatement, ComprehensiveIncome, BalanceSheet, StatementOfEquity, CashFlowStatement
  Other: 12 additional statements

**Common Actions:**
  # List all available statements
  xbrl.statements

  # View core financial statements
  stmt = xbrl.statements.income_statement()
  stmt = xbrl.statements.balance_sheet()
  stmt = xbrl.statements.cash_flow_statement()
  stmt = xbrl.statements.statement_of_equity()
  stmt = xbrl.statements.comprehensive_income()

  # Get current period only (returns XBRL with filtered context)
  current = xbrl.current_period
  stmt = current.income_statement()

  # Convert statement to DataFrame
  df = stmt.to_dataframe()

  # Query specific facts
  revenue = xbrl.facts.query().by_concept('Revenue').to_dataframe()

💡 Use xbrl.docs for comprehensive API guide
```

**When to Use**:
- Understanding XBRL filing structure
- Checking statement availability
- Getting fiscal period information
- AI analysis requiring XBRL metadata

**Token Efficiency**: The .text() method uses 66% fewer tokens than repr() while retaining all essential information including specific method names for AI agents.

## Statement Object

**Typical Size**: ~5,000 characters
**Token Estimate**: ~1,250 tokens
**Format**: ASCII table with financial data
**Has .docs**: ✅ Yes
**Has .text()**: ❌ No

**Contains**:
- Statement title and company name
- Period headers (dates)
- Line items with hierarchical structure
- Financial values properly formatted
- Units (USD, shares, etc.)

**Example**:
```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]
xbrl = filing.xbrl()
income = xbrl.statements.income_statement()
print(income)  # Shows income statement table

# Access documentation
income.docs  # Comprehensive Statement API guide
income.docs.search("dataframe")  # How to convert to DataFrame
income.docs.search("export")  # How to export data
```

**Sample Output Structure**:
```
Income Statement
Apple Inc.

                                    Sep 30, 2023
Revenue                             383,285,000,000
Cost of Revenue                     214,137,000,000
Gross Profit                        169,148,000,000
Operating Expenses                   51,345,000,000
Operating Income                    117,803,000,000
Net Income                           96,995,000,000
```

**When to Use**:
- Detailed financial analysis
- Getting specific line items
- Single period financial data

**Note**: For multi-period comparison, use `MultiPeriodStatement` instead (more token-efficient).

## MultiPeriodStatement Object

**Typical Size**: ~2,000 characters
**Token Estimate**: ~500 tokens
**Format**: Unicode table with multiple period columns

**Contains**:
- Company name
- Multi-period columns (typically 3-5 fiscal periods)
- Key financial metrics in rows
- Hierarchical line item structure
- Fiscal period labels

**Example**:
```python
from edgar import Company

company = Company("AAPL")
income = company.income_statement(periods=3)  # Last 3 fiscal years
print(income)  # Shows 3-period comparison
```

**Sample Output Structure**:
```
Income Statement (Annual)
Apple Inc.

                        FY 2023      FY 2022      FY 2021
Revenue                 383.3B       394.3B       365.8B
Cost of Revenue         214.1B       223.5B       212.3B
Gross Profit            169.1B       170.8B       153.5B
Operating Income        117.8B       119.4B       108.9B
Net Income               97.0B        99.8B        94.7B
```

**When to Use**:
- Trend analysis across multiple periods
- Year-over-year comparisons
- Most token-efficient format for multi-period data

**Advantage**: This is the most concise format for financial data - uses TSV-like structure internally for maximum token efficiency.

## Token Planning Guide

Understanding token usage helps you optimize API interactions.

### Three Ways to Get Information

EdgarTools provides three methods for accessing information, each optimized for different use cases:

| Method | Purpose | Token Usage | Available On |
|--------|---------|-------------|--------------|
| `print(obj)` or `repr()` | Quick visual overview | 125-2,500 | All objects |
| `obj.docs` | **Primary:** API discovery & learning | 2,000-5,000 | All major objects |
| `obj.docs.search()` | **Primary:** Find specific methods | 200-500 | All major objects |
| `obj.text()` | **Specialized:** AI data extraction | 25% less than JSON | Company, XBRL only |

**Recommended Pattern for API Discovery**:
1. **Start with `repr(object)`** - Quick visual overview
2. **Use `object.docs`** - Comprehensive API reference
3. **Use `object.docs.search("keyword")`** - Find specific functionality

**When to Use Each**:
- **`repr(obj)` or `print(obj)`**: Quick overview, see structure, visual verification
- **`obj.docs`**: **PRIMARY METHOD** - Learn API, discover methods, find workflow examples
- **`obj.docs.search()`**: **PRIMARY METHOD** - Search for specific functionality
- **`obj.text()`**: **SPECIALIZED** - Only for Company/XBRL when extracting data for AI analysis

### Token Estimates by Object and Method

| Object Type | repr() | .text() | .docs (full) | .docs (search) |
|-------------|--------|---------|--------------|----------------|
| Company | ~750 | ~75 | ~3,500 | ~300 |
| Filing | ~125 | N/A* | ~2,500 | ~250 |
| Filings (3 items) | ~300 | N/A | ~3,000 | ~250 |
| XBRL | ~750 | ~275 | ~4,000 | ~350 |
| Statement | ~1,250 | N/A | ~2,800 | ~300 |
| MultiPeriodStatement | ~500 | N/A | ~2,800 | ~300 |

*Filing has `.text()` but it returns full document text (potentially 50K+ tokens), not AI-optimized metadata.

**Note**: XBRL.text() was recently optimized to use Markdown-KV format with all essential method names (66% token reduction from previous ~810 tokens).

### Tips for Token Efficiency

1. **Use `.head()` on collections**:
   ```python
   filings.head(5)  # Limit to 5 instead of all results
   ```

2. **Prefer MultiPeriodStatement over multiple Statements**:
   ```python
   # Efficient - one object, ~500 tokens
   income = company.income_statement(periods=3)

   # Less efficient - three objects, ~3,750 tokens
   filing1 = company.get_filings(form="10-K")[0]
   filing2 = company.get_filings(form="10-K")[1]
   filing3 = company.get_filings(form="10-K")[2]
   ```

3. **Use specific statements instead of full XBRL**:
   ```python
   # Efficient - ~1,250 tokens
   income = xbrl.statements.income_statement()

   # Less efficient - ~2,500 tokens
   print(xbrl)  # Full XBRL object
   ```

4. **Filter before retrieving**:
   ```python
   # Get only what you need
   filings = get_filings(2023, 1, form="10-K", filing_date="2023-01-01:2023-01-31")
   ```

5. **Use date ranges to limit results**:
   ```python
   filings = company.get_filings(form="8-K", filing_date="2023-01-01:2023-03-31")
   ```

## Output Format Notes

All EdgarTools object representations:
- ✅ Are plain text (no ANSI escape codes)
- ✅ Use Unicode box drawing for visual structure (╭─╮│╰╯)
- ✅ Are AI-friendly (can be parsed programmatically)
- ✅ Are designed for terminal display but work well for AI consumption

For even more token-efficient formats optimized specifically for LLMs, some objects provide a `.text()` method that outputs in Markdown-KV or TSV format. See the main skill.md documentation for details.

## See Also

- [skill.md](skill.md) - Main API documentation and examples
- [workflows.md](workflows.md) - End-to-end analysis patterns
- [README.md](README.md) - Installation and usage guide
