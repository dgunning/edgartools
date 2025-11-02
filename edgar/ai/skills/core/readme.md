# SEC Filing Analysis Skills

EdgarTools skills package for AI agents analyzing SEC filings and financial statements.

## Overview

This package provides AI-friendly documentation and helper functions for working with SEC EDGAR filings using EdgarTools.

**What's Included**:
- **skill.md** - Progressive disclosure documentation following Anthropic Skills format
- **Helper functions** - Convenience wrappers for common analysis patterns
- **Object reference** - Token estimates and output format documentation
- **Workflows** - End-to-end analysis examples

## Documentation Structure

This skill provides **multi-tier documentation** optimized for AI agents:

### Tier 0: Quick Start (30 seconds)
**Fast routing based on task type** - Get to the right pattern immediately:
- **quickstart-by-task.md** - Decision tree routing by task type (counting, discovery, analysis, etc.)
- **form-types-reference.md** - Complete SEC form catalog with natural language mapping (311 forms)

**Use when**:
- You need to find the right approach quickly
- You don't know the SEC form code
- You want to route by task type (counting vs analysis)

**Time savings**: 60% faster than browsing all documentation

### Tier 1: Skill Documentation (Getting Started)
Tutorial-level documentation for learning patterns and workflows:
- **skill.md** - Main tutorial with progressive disclosure (Quick Start → Core → Advanced)
- **workflows.md** - End-to-end analysis examples showing complete workflows
- **objects.md** - Core EdgarTools objects (Company, Filing, XBRL, Statement) with token estimates
- **data-objects.md** - Form-specific data objects (TenK, Form4, FormD, ThirteenF, etc.)

**Use when**: Learning EdgarTools patterns, understanding workflows, working with specific form types, estimating token usage

### Tier 2: API Reference (Detailed Usage)
Comprehensive method-level documentation from EdgarTools centralized docs:
- **api-reference/Company.md** - Complete Company class reference (~1,070 lines)
- **api-reference/EntityFiling.md** - Complete Filing class reference (~557 lines)
- **api-reference/EntityFilings.md** - Complete Filings collection reference (~671 lines)
- **api-reference/XBRL.md** - Complete XBRL class reference (~587 lines)
- **api-reference/Statement.md** - Complete Statement class reference (~567 lines)

**Use when**: Looking up specific methods, parameters, return types, or advanced features

### Recommended Navigation Flow

**For Quick Queries** (< 2 minutes):
1. Check **quickstart-by-task.md** for task routing
2. Look up form code in **form-types-reference.md** if needed
3. Execute the pattern

**For Learning** (5-10 minutes):
1. Start with **skill.md** to learn the basic patterns
2. Check **data-objects.md** if working with specific form types (Form 4, Form D, 13F, etc.)
3. Reference **workflows.md** for complete examples
4. Consult **api-reference/** for detailed method signatures
5. Use **objects.md** for token optimization

**Example - "How many crowdfunding filings in past week?"**:
1. quickstart-by-task.md → Section 1: Counting & Existence
2. form-types-reference.md → "crowdfunding" → Form C
3. skill.md → Find relative date filtering example
4. Execute in < 90 seconds ✓

## Compatibility

**Designed for Anthropic Claude Desktop Skills compatibility**:
- ✅ YAML frontmatter with `name` and `description` fields
- ✅ Progressive disclosure structure (Quick Start → Core → Advanced)
- ✅ Natural language question mapping
- ✅ Claude Desktop can load this skill (installation/integration deferred to future work)

**Note**: While this package is designed to be compatible with Claude Desktop Skills, the actual integration and installation process is not covered in this initial release. The focus is on creating AI-friendly documentation that follows the Anthropic Skills format specification.

## Usage

### As Python Package

Import and use helper functions directly:

```python
from edgar.ai.helpers import get_revenue_trend

# Get revenue trend for 3 fiscal years
income = get_revenue_trend("AAPL", periods=3)
print(income)
```

All helper functions:
```python
from edgar.ai.helpers import (
    get_filings_by_period,
    get_today_filings,
    get_revenue_trend,
    get_filing_statement,
    compare_companies_revenue,
)

# Get filings for a specific period
filings = get_filings_by_period(2023, 1, form="10-K")

# Get today's filings
current = get_today_filings()

# Get revenue trend
income = get_revenue_trend("AAPL", periods=3)

# Get specific statement from filing
income = get_filing_statement("AAPL", 2023, "10-K", "income")

# Compare multiple companies
results = compare_companies_revenue(["AAPL", "MSFT"], periods=3)
```

### For AI Agents

The Skills documentation can be consumed directly by AI agents:

- **skill.md** provides comprehensive API documentation with examples
- **objects.md** documents object representations with token size estimates
- **workflows.md** provides end-to-end analysis patterns
- Natural language questions are mapped to code patterns

AI agents can reference these files to:
- Understand EdgarTools API capabilities
- Estimate token usage for operations
- Find code patterns for common tasks
- Handle errors gracefully

## Files in This Skill

| File | Purpose | Token Estimate |
|------|---------|----------------|
| **quickstart-by-task.md** | Fast task routing (< 30 sec) | ~5,000 |
| **form-types-reference.md** | SEC form catalog with 311 forms | ~7,000 |
| **skill.md** | Main skill documentation with API examples | ~10,000 |
| **workflows.md** | End-to-end analysis workflows | ~4,000 |
| **objects.md** | Core EdgarTools objects (Company, Filing, XBRL) | ~3,000 |
| **data-objects.md** | Form-specific data objects (TenK, Form4, etc.) | ~4,000 |
| **helpers.py** | Convenience functions for common patterns | N/A (code) |
| **README.md** | This file - package overview | ~1,200 |

**New in this version:**
- **data-objects.md** - Complete guide to form-specific data objects (16 types documented)
- **quickstart-by-task.md** - Decision tree for finding the right approach by task type
- **form-types-reference.md** - Comprehensive form catalog with natural language mappings
- **Enhanced skill.md** - Added examples for crowdfunding, relative dates, post-retrieval filtering

## Helper Functions Reference

### get_filings_by_period(year, quarter, form=None, filing_date=None)

Get published filings for a specific quarter.

```python
filings = get_filings_by_period(2023, 1, form="10-K")
```

### get_today_filings()

Get current filings from the last ~24 hours.

```python
current = get_today_filings()
```

### get_revenue_trend(ticker, periods=3, quarterly=False)

Get income statement for trend analysis.

```python
# Annual data (default)
income = get_revenue_trend("AAPL", periods=3)

# Quarterly data
quarterly = get_revenue_trend("AAPL", periods=4, quarterly=True)
```

### get_filing_statement(ticker, year, form, statement_type)

Get specific financial statement from a filing.

```python
income = get_filing_statement("AAPL", 2023, "10-K", "income")
balance = get_filing_statement("AAPL", 2023, "10-K", "balance")
cash_flow = get_filing_statement("AAPL", 2023, "10-K", "cash_flow")
```

### compare_companies_revenue(tickers, periods=3)

Compare revenue across multiple companies.

```python
results = compare_companies_revenue(["AAPL", "MSFT", "GOOGL"], periods=3)
print(results["AAPL"])
print(results["MSFT"])
```

## Requirements

EdgarTools is required and should be installed automatically:

```bash
pip install edgartools
```

The Skills package is included with EdgarTools at `edgar/ai/`.

## API Patterns

The Skills documentation covers three main approaches for getting filings:

1. **Published Filings** - Discovery & bulk analysis (quarterly SEC indexes)
   - Use when: Screening, pattern discovery, don't know specific companies
   - Example: `get_filings(2023, 1, form="10-K")`

2. **Current Filings** - Real-time monitoring (RSS feed, last 24h)
   - Use when: Monitoring recent activity, tracking latest submissions
   - Example: `get_current_filings()`

3. **Company Filings** - Known entity analysis (specific companies)
   - Use when: You know the company ticker or name
   - Example: `Company("AAPL").get_filings(form="10-K")`

For financial statements:

1. **Entity Facts API** - Multi-period comparison (fastest, most token-efficient)
   - Example: `company.income_statement(periods=3)`

2. **Filing XBRL** - Single period details (most comprehensive)
   - Example: `filing.xbrl().statements.income_statement()`

## Rate Limiting

EdgarTools respects SEC rate limits (10 requests/second):
- Automatic rate limiting built-in
- Request caching reduces redundant API calls
- Large batch operations may take time due to rate limits

**Best Practice**: For batch processing, use Entity Facts API when possible (single API call per company vs. multiple filing requests).

## Token Efficiency Tips

1. **Use `.head()` to limit collection output**:
   ```python
   filings.head(5)  # Only show 5 filings
   ```

2. **Prefer MultiPeriodStatement for multi-period data**:
   ```python
   # Efficient: ~500 tokens
   income = company.income_statement(periods=3)

   # Less efficient: ~3,750 tokens
   # (3 separate filings × ~1,250 tokens each)
   ```

3. **Filter before displaying**:
   ```python
   filings = get_filings(2023, 1, form="10-K")
   tech = filings.filter(ticker=["AAPL", "MSFT", "GOOGL"])  # Smaller result
   print(tech)
   ```

4. **Use specific statements vs full XBRL**:
   ```python
   # Efficient: ~1,250 tokens
   income = xbrl.statements.income_statement()

   # Less efficient: ~2,500 tokens
   print(xbrl)  # Full XBRL object
   ```

See [objects.md](objects.md) for detailed token estimates by object type.

## Learn More

- **EdgarTools Documentation**: https://github.com/dgunning/edgartools
- **SEC EDGAR System**: https://www.sec.gov/edgar
- **XBRL Primer**: Understanding financial statement structure
- **SEC API Documentation**: https://www.sec.gov/edgar/sec-api-documentation

## Development

This Skills package is part of the EdgarTools project and follows its development practices.

### Running Tests

Tests for the Skills system:

```bash
pytest tests/test_skills.py -v
```

### Contributing

Follow EdgarTools contribution guidelines. See the main project README for details.

## Support

For issues, questions, or feature requests:
- Open an issue at https://github.com/dgunning/edgartools/issues
- Check existing documentation in skill.md and workflows.md
- Review object reference in objects.md for token optimization

---

**Version**: Part of EdgarTools v4.22.0+
**Status**: Active development
**License**: Same as EdgarTools (MIT)
