---
name: SEC Filing Analysis
description: Query and analyze SEC filings and financial statements using EdgarTools. Get company data, filings, XBRL financials, and perform multi-company analysis.
---

# SEC Filing Analysis

Analyze SEC filings and financial statements using EdgarTools - a Python library for accessing and analyzing SEC EDGAR data.

## Overview

This guide covers essential SEC filing analysis operations. For detailed object representations and token estimates, see [objects.md](./objects.md). For end-to-end analysis workflows, see [workflows.md](./workflows.md). For installation and setup, see [README.md](./README.md).

## Quick Start

Most common patterns for getting started quickly.

### Get a Company

```python
from edgar import Company

company = Company("AAPL")
print(company)  # Shows company profile
```

### Get Recent Filings

```python
from edgar import get_current_filings

filings = get_current_filings()  # Last ~24 hours
print(filings.head(5))  # Show first 5
```

### Get Financial Statements

```python
from edgar import Company

company = Company("AAPL")
income = company.income_statement(periods=3)  # 3 fiscal years
print(income)
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

## Common Questions

Natural language questions mapped to code patterns.

### "Show all S-1 filings from February 2023"

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

### "What's been filed today?"

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

### "Get Apple's revenue for last 3 fiscal years"

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

### "Tesla's quarterly net income trend (4 quarters)"

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

### "Full income statement from Apple's 2023 10-K"

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

### "Compare Apple and Microsoft revenue"

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

### "Get balance sheet from latest 10-Q"

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-Q")[0]  # Latest 10-Q
xbrl = filing.xbrl()
balance = xbrl.statements.balance_sheet()
print(balance)
```

### "Search for all 8-K filings with 'Item 5.02' (officer departures)"

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

### "Get all Form 4 insider transactions for AAPL"

```python
from edgar import Company

company = Company("AAPL")
form4_filings = company.get_filings(form="4")

print(f"Found {len(form4_filings)} Form 4 filings")
for filing in form4_filings[:5]:
    print(f"{filing.filing_date} - {filing.company}")
```

### "Find all tech companies that filed 10-K in January 2023"

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

## Advanced Patterns

Multi-step workflows and advanced use cases.

### Filtering and Pagination

```python
from edgar import get_filings

# Get large result set
filings = get_filings(2023, 1)

# Filter by multiple criteria
filtered = filings.filter(
    form=["10-K", "10-Q"],
    ticker=["AAPL", "MSFT", "GOOGL"]
)

# Pagination
print(filtered.head(10))  # First 10
print(filtered[10:20])  # Next 10

# Iterate
for filing in filtered[:5]:
    print(f"{filing.company} - {filing.form} - {filing.filing_date}")
```

### Multi-Company Analysis

```python
from edgar import Company

tickers = ["AAPL", "MSFT", "GOOGL", "META", "AMZN"]

# Collect revenue data
revenue_data = {}
for ticker in tickers:
    company = Company(ticker)
    income = company.income_statement(periods=3)
    revenue_data[ticker] = income

# Display comparisons
for ticker, statement in revenue_data.items():
    print(f"\n{ticker} Revenue:")
    print(statement)
```

### Error Handling

```python
from edgar import Company

try:
    company = Company("INVALID_TICKER")
    income = company.income_statement(periods=3)
except Exception as e:
    print(f"Error: {e}")
    # Handle error appropriately

# Check data availability
filings = get_filings(2023, 1, form="RARE-FORM")
if len(filings) == 0:
    print("No filings found matching criteria")
else:
    print(f"Found {len(filings)} filings")

# Verify XBRL availability
filing = company.get_filings(form="10-K")[0]
if hasattr(filing, 'xbrl') and filing.xbrl:
    xbrl = filing.xbrl()
    # Process XBRL
else:
    print("XBRL data not available")
```

### Working with Filing Documents

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Get parsed document
doc = filing.document()

# Access sections (for 10-K/10-Q)
if hasattr(doc, 'get_section'):
    item1 = doc.get_section("Item 1")  # Business description
    item1a = doc.get_section("Item 1A")  # Risk factors
    item7 = doc.get_section("Item 7")  # MD&A

# Get raw HTML
html = filing.html()
```

## Helper Functions Reference

Convenience functions available in `edgar.ai.helpers`:

```python
from edgar.ai.helpers import (
    get_filings_by_period,
    get_today_filings,
    get_revenue_trend,
    get_filing_statement,
    compare_companies_revenue,
)

# Get filings for a period
filings = get_filings_by_period(2023, 1, form="10-K")

# Get today's filings
current = get_today_filings()

# Get revenue trend (annual or quarterly)
income = get_revenue_trend("AAPL", periods=3)  # Annual
quarterly = get_revenue_trend("AAPL", periods=4, quarterly=True)

# Get specific statement from filing
income = get_filing_statement("AAPL", 2023, "10-K", "income")
balance = get_filing_statement("AAPL", 2023, "10-K", "balance")
cash_flow = get_filing_statement("AAPL", 2023, "10-K", "cash_flow")

# Compare multiple companies
results = compare_companies_revenue(["AAPL", "MSFT", "GOOGL"], periods=3)
```

## Exporting Skills

EdgarTools AI skills can be exported for use in Claude Desktop and other AI tools.

### Export for Claude Desktop

```python
from edgar.ai import sec_analysis_skill, export_skill

# Export skill to current directory
skill_dir = export_skill(sec_analysis_skill, format="claude-desktop")
print(f"Skill exported to: {skill_dir}")
# Output: Skill exported to: sec-filing-analysis

# Export with custom output directory
from pathlib import Path
output_path = export_skill(
    sec_analysis_skill,
    format="claude-desktop",
    output_dir=Path.home() / "claude-skills"
)

# Export as zip archive
zip_path = export_skill(
    sec_analysis_skill,
    format="claude-desktop",
    create_zip=True
)
print(f"Skill packaged: {zip_path}")
# Output: Skill packaged: sec-filing-analysis.zip
```

### Using in Claude Desktop

After exporting, add the skill to Claude Desktop:

1. Export the skill: `export_skill(sec_analysis_skill)`
2. Move the `sec-filing-analysis` directory to your Claude Desktop skills folder
3. Restart Claude Desktop
4. The skill will appear in your available skills

### Creating External Skills

External packages can extend EdgarTools with custom skills using the `BaseSkill` abstract class:

```python
from edgar.ai.skills.base import BaseSkill
from pathlib import Path
from typing import Dict, Callable

class CustomAnalysisSkill(BaseSkill):
    """Custom SEC analysis skill with specialized workflows."""

    @property
    def name(self) -> str:
        return "Custom SEC Analysis"

    @property
    def description(self) -> str:
        return "Specialized SEC filing analysis for XYZ use case"

    @property
    def content_dir(self) -> Path:
        return Path(__file__).parent / "content"

    def get_helpers(self) -> Dict[str, Callable]:
        """Return custom helper functions."""
        from mypackage import custom_helpers
        return {
            'analyze_filing_sentiment': custom_helpers.sentiment_analysis,
            'extract_risk_factors': custom_helpers.risk_extraction,
        }

# Register with EdgarTools
custom_skill = CustomAnalysisSkill()

# Export custom skill
from edgar.ai import export_skill
export_skill(custom_skill, format="claude-desktop")
```

### Skill Discovery

List all available skills (built-in + external):

```python
from edgar.ai import list_skills, get_skill

# List all skills
skills = list_skills()
for skill in skills:
    print(f"{skill.name}: {skill.description}")

# Get specific skill by name
sec_skill = get_skill("SEC Filing Analysis")
```

## See Also

- [Object Reference](objects.md) - Object representations and token size estimates
- [Workflows](workflows.md) - End-to-end analysis patterns
- [README](README.md) - Installation and troubleshooting

## Rate Limiting

EdgarTools automatically handles SEC rate limiting (10 requests/second):
- Built-in rate limiting
- Request caching to reduce API calls
- Large batch operations may take time due to rate limits
