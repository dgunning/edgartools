---
name: EdgarTools Object Reference
description: Reference guide for EdgarTools object representations - what AI agents can expect from each object type with token size estimates.
---

# EdgarTools Object Reference

## Overview

EdgarTools objects use `repr()` for terminal display. Plain text with Unicode box drawing - no ANSI codes, AI-friendly.

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

### 2. AI-Optimized Context Format (`.to_context()`)

**Available on**: Company, XBRL, Filing, Filings, EntityFilings, FormC, Offering

**Important**: Use `.to_context()` for AI-optimized metadata. The older `.text()` method is deprecated for Company and XBRL.

Objects with AI-optimized `.to_context()`:
- **Company**: Markdown-KV format (60.7% accuracy, 25% fewer tokens than JSON)
- **XBRL**: Markdown-KV format for metadata
- **Filing, Filings, EntityFilings**: Navigation hints and metadata
- **FormC**: Crowdfunding offering data with 3 detail levels (minimal, standard, full)
- **Offering**: Complete crowdfunding lifecycle context

Research basis: [Best Input Data Format for LLMs](https://improvingagents.com/blog/best-input-data-format-for-llms)

**Usage**:

```python
from edgar import Company

company = Company("AAPL")

# Get AI-optimized context (Markdown-KV format)
text = company.to_context(max_tokens=2000)
print(text)
# **Company:** Apple Inc.
# **CIK:** 0000320193
# **Ticker:** AAPL
# ...

# XBRL also has AI-optimized context
filing = company.get_filings(form="10-K")[0]
xbrl = filing.xbrl()
xbrl_text = xbrl.to_context(max_tokens=2000)
```

> **Note**: `Company.text()` and `XBRL.text()` are deprecated. Use `.to_context()` instead for consistent naming across all EdgarTools classes.

**Benefits**:
- **Token Efficient**: 25% fewer tokens than JSON for same information
- **Higher Accuracy**: 60.7% vs 54.7% (JSON) in research benchmarks
- **Token Control**: `max_tokens` parameter with automatic truncation
- **Format Optimized**: Markdown-KV for maximum LLM comprehension

**Special Note About Filing.text()**: Filing has a `.text()` method, but it returns the full filing document text (potentially 50K+ tokens), NOT AI-optimized metadata. For Filing metadata, use `repr()` or `.docs`.

### 3. Comprehensive Documentation (`.docs`)

**Available on**: All major objects (Company, Filing, EntityFiling, Filings, EntityFilings, XBRL, Statement, FormC)

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

**Documentation Features**: Common Actions (quick reference), Searchable (BM25 semantic search), Comprehensive (complete API with examples), Contextual (methods, properties, workflows, best practices)

**When to Use .docs**: Discovering available methods/properties, finding usage examples, learning API patterns, searching for specific functionality

**Token Estimates**:
- Full `.docs` display: 2,000-5,000 tokens (depending on class)
- Search results: 200-500 tokens per matching section
- Hint in `repr()`: Adds ~15 tokens to display

## Summary of Access Methods

**Recommended Pattern**: `repr()` + `.docs` + `.docs.search()`

This is the current recommended approach for API discovery and working with EdgarTools objects. The `.to_context()` method is available on many objects for AI-optimized data extraction.

| Method | Available On | Purpose | Token Range |
|--------|--------------|---------|-------------|
| `print(obj)` or `repr()` | All objects | Quick visual overview | 125-2,500 |
| `obj.docs` | All major objects | **Primary:** API discovery & learning | 2,000-5,000 |
| `obj.docs.search(query)` | All major objects | **Primary:** Find specific functionality | 200-500 |
| `obj.to_context(max_tokens)` | Company, XBRL, Filing, Filings, etc. | **Specialized:** AI-optimized data extraction | 200-2,000 |

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

### Quick Reference Table

| Attribute/Method | Type | Example | Notes |
|------------------|------|---------|-------|
| `.name` | str | "Apple Inc." | Company name |
| `.cik` | str | "0000320193" | Central Index Key |
| `.sic` | str | "3571" | Industry code (NOT `sic_code`) |
| `.sic_description` | str | "Electronic Computers" | Industry description |
| `.tickers` | list[str] | ["AAPL"] | All ticker symbols |
| `.ein` | str | "942404110" | Employer ID Number |
| `.category` | str | "Large accelerated filer" | Filer category |
| `.phone` | str | "4089961010" | Contact phone |
| `.get_filings()` | Filings | Collection | Returns filing collection |
| `.latest(n)` | Filing \| Filings | Single if n=1, collection otherwise | Latest filings |
| `.income_statement(periods)` | Statement | Multi-period statement | From Entity Facts API |
| `.balance_sheet(periods)` | Statement | Multi-period statement | From Entity Facts API |
| `.cash_flow_statement(periods)` | Statement | Multi-period statement | From Entity Facts API |
| `.to_context()` | str | AI-friendly summary | **Use this first!** Token-efficient |
| `.docs` | Documentation | API documentation | Search with `.docs.search()` |

**Important**: Use `.to_context()` for token-efficient output (~88 tokens vs ~750 for full repr).

**Typical Size**: ~3,000 characters
**Token Estimate**: ~750 tokens
**Format**: Unicode box drawing with information panels
**Has .docs**: ✅ Yes
**Has .to_context()**: ✅ Yes (AI-optimized Markdown-KV)

**Contains**: Entity name/identifiers (CIK, ticker, EIN), exchange listings (NYSE, NASDAQ, OTC), business/mailing address, contact info (phone, website if available), former names (if applicable), SIC code/industry description, docs hint

**Example**:
```python
from edgar import Company

company = Company("AAPL")
print(company)  # Shows full company profile with box drawing

# Access documentation
company.docs  # Comprehensive API guide
company.docs.search("get_filings")  # Find filing methods

# Get AI-optimized context
company.to_context(max_tokens=1000)  # Markdown-KV format
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

**When to Use**: Need complete company profile, verifying company identity, getting contact information

## Filing Object

**Typical Size**: ~500 characters
**Token Estimate**: ~125 tokens
**Format**: Unicode box drawing with key metadata
**Has .docs**: ✅ Yes
**Has .text()**: ⚠️ Yes, but returns filing document text (not AI metadata)

**Contains**: Form type (10-K, 10-Q, 8-K, S-1), company name/CIK, accession number (unique identifier), filing date/acceptance datetime, period of report (for periodic filings), document count, docs hint

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

**When to Use**: Identifying specific filing, getting filing metadata, verifying filing date/period

## Filings Collection

**Typical Size**: Varies by result count (default: first 3 shown)
**Token Estimate**: ~200-300 tokens for 3 filings
**Format**: Unicode table with columns
**Has .docs**: ✅ Yes (EntityFilings has .docs, base Filings has .docs)
**Has .text()**: ❌ No

**Contains**: Tabular view of multiple filings, company name/CIK/form type, filing date/period of report, pagination information, docs hint (EntityFilings only)

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

**When to Use**: Browsing multiple filings, comparing filing dates, identifying patterns across companies

**Tip**: Use `.head(n)` to limit output and reduce token usage.

## XBRL Object

**Typical Size (repr)**: ~3,000 characters (visual box drawing)
**Typical Size (.to_context())**: ~1,100 characters (AI-optimized)
**Token Estimate (repr)**: ~750 tokens
**Token Estimate (.to_context())**: ~275 tokens
**Format**: Markdown-KV (AI-optimized) via .to_context(), Unicode box drawing via repr()
**Has .docs**: ✅ Yes
**Has .to_context()**: ✅ Yes (AI-optimized Markdown-KV)

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

# AI-optimized context (Markdown-KV format)
text = xbrl.to_context()  # Compact, token-efficient
print(text)

# Access documentation
xbrl.docs  # Comprehensive XBRL API guide
xbrl.docs.search("statements")  # How to access statements
xbrl.docs.search("facts")  # How to query facts
```

**Sample .to_context() Output (AI-Optimized)**:
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

## FormC Object

**Typical Size (repr)**: ~2,500 characters
**Typical Size (.to_context())**:
  - Minimal: ~400 characters (~100 tokens)
  - Standard: ~1,200 characters (~300 tokens)
  - Full: ~2,800 characters (~700 tokens)
**Format**: Unicode box drawing via repr(), Markdown-KV via .to_context()
**Has .docs**: ✅ Yes
**Has .to_context()**: ✅ Yes (AI-optimized with 3 detail levels)

**Contains**:
- Form type (C, C/A, C-U, C-AR, C-TR)
- Issuer information (company name, CIK, legal status, jurisdiction)
- Offering information (target amount, maximum, deadline, security type, price)
- Funding portal details (name, CIK, file number)
- Financial disclosures (revenue, net income, assets, debt, employees)
- Campaign status (active, expired, terminated)
- Signature information

**Form C Variants**:
- **C** - Initial crowdfunding offering
- **C/A** - Amendment to offering
- **C-U** - Progress update (50% or 100% milestone)
- **C-AR** - Annual report
- **C-TR** - Termination report

**Example**:
```python
from edgar import Company

company = Company("1881570")  # ViiT Health
filings = company.get_filings(form="C")
filing = filings[0]
formc = filing.obj()

# Visual display (Unicode box drawing)
print(formc)  # Shows full offering with all sections

# AI-optimized context (Markdown-KV format)
context = formc.to_context()  # Standard detail (~300 tokens)
context = formc.to_context(detail='minimal')  # ~100 tokens
context = formc.to_context(detail='full')  # ~700 tokens

# Access documentation
formc.docs  # Comprehensive FormC API guide
formc.docs.search("offering")  # How to access offering data
formc.docs.search("lifecycle")  # Offering lifecycle workflow
```

**Sample .to_context(detail='standard') Output**:
```
FORM C - OFFERING (Filed: 2025-06-11)

ISSUER: ViiT Health Inc
  CIK: 1881570
  Legal: Delaware Corporation
  Website: https://www.viit.health

FUNDING PORTAL: Wefunder Portal LLC
  File Number: 007-00033

OFFERING:
  Security: Other (Membership Interests)
  Target: $50,000 | Maximum: $111,308
  Target is 45% of maximum
  Price: $1.00/unit | Units: 50,000
  Deadline: 2026-04-30
  Status: 293 days remaining

FINANCIALS (Current vs Prior Year):
  Revenue: $0 (pre-revenue)
  Net Income: -$346,594
  Assets: $25,065
  Total Debt: $1,688,898

CAMPAIGN STATUS: Active (Initial)

AVAILABLE ACTIONS:
  - Use .get_offering() for complete campaign lifecycle
  - Use .issuer for IssuerCompany information
  - Use .offering_information for offering terms
  - Use .annual_report_disclosure for financial data
```

**When to Use**:
- Analyzing crowdfunding offerings (Regulation CF)
- Screening offerings by size, status, or deadline
- Tracking offering lifecycle (initial → updates → annual reports → termination)
- Assessing company financial health from annual reports
- Finding offerings by funding portal

**Key Properties**:
```python
# Offering terms
formc.offering_information.target_amount
formc.offering_information.maximum_offering_amount
formc.offering_information.deadline_date
formc.offering_information.price_per_security
formc.offering_information.number_of_securities

# Financial data (if available)
formc.annual_report_disclosure.revenues
formc.annual_report_disclosure.net_income
formc.annual_report_disclosure.total_assets
formc.annual_report_disclosure.debt_to_asset_ratio
formc.annual_report_disclosure.revenue_growth_yoy

# Status
formc.campaign_status  # "Active (Initial)", "Progress Update", etc.
formc.days_to_deadline  # Days remaining until deadline
formc.is_expired  # True if past deadline

# Issuer and portal
formc.issuer_name
formc.issuer_cik
formc.portal_name
formc.portal_file_number

# Get complete offering lifecycle
offering = formc.get_offering()
print(offering.timeline())  # Show all related filings
```

**Detail Level Guide**:
- **minimal**: Essential offering info for quick screening (target, max, deadline, status)
- **standard** (default): Most important data including financials and portal info
- **full**: Everything including addresses, fees, jurisdictions, signatures

**Token Efficiency**: The .to_context() method provides 60-85% token reduction compared to repr() while retaining all actionable information.

## Token Planning Guide

Optimize API interactions with token planning.

### Three Ways to Get Information

EdgarTools provides three methods for accessing information, each optimized for different use cases:

| Method | Purpose | Token Usage | Available On |
|--------|---------|-------------|--------------|
| `print(obj)` or `repr()` | Quick visual overview | 125-2,500 | All objects |
| `obj.docs` | **Primary:** API discovery & learning | 2,000-5,000 | All major objects |
| `obj.docs.search()` | **Primary:** Find specific methods | 200-500 | All major objects |
| `obj.to_context()` | **Specialized:** AI-optimized extraction | 25% less than JSON | Company, XBRL, Filing, Filings, FormC |

**Recommended Pattern for API Discovery**:
1. **Start with `repr(object)`** - Quick visual overview
2. **Use `object.docs`** - Comprehensive API reference
3. **Use `object.docs.search("keyword")`** - Find specific functionality

**When to Use Each**: `repr(obj)` for quick overview/structure, `obj.docs` (PRIMARY) for API discovery/methods/workflows, `obj.docs.search()` (PRIMARY) for specific functionality, `obj.to_context()` (SPECIALIZED) for AI-optimized data extraction

### Token Estimates by Object and Method

| Object Type | repr() | .to_context() | .docs (full) | .docs (search) |
|-------------|--------|---------------|--------------|----------------|
| Company | ~750 | ~75 | ~3,500 | ~300 |
| Filing | ~125 | N/A | ~2,500 | ~250 |
| Filings (3 items) | ~300 | N/A | ~3,000 | ~250 |
| XBRL | ~750 | ~275 | ~4,000 | ~350 |
| Statement | ~1,250 | N/A | ~2,800 | ~300 |
| MultiPeriodStatement | ~500 | N/A | ~2,800 | ~300 |
| FormC | ~625 | ~100-700* | ~3,000 | ~300 |

*FormC .to_context() supports 3 detail levels: minimal (~100), standard (~300), full (~700)

**Note**: Filing has `.text()` but it returns full document text (potentially 50K+ tokens), not AI-optimized metadata.

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

All EdgarTools object representations: ✅ Plain text (no ANSI codes), ✅ Unicode box drawing (╭─╮│╰╯), ✅ AI-friendly (programmatically parsable), ✅ Designed for terminal but AI-compatible

For even more token-efficient formats optimized for LLMs, some objects provide `.to_context()` for AI-optimized Markdown-KV output. See the main skill.md documentation for details.

## See Also

- [skill.md](skill.md) - Main API documentation and examples
- [workflows.md](workflows.md) - End-to-end analysis patterns
- [README.md](README.md) - Installation and usage guide
