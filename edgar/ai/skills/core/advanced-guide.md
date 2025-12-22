# Advanced Guide

Advanced patterns, helper functions, error handling, and skill exportation for EdgarTools.

**For basic usage, see** [SKILL.md](SKILL.md).
**For complete examples, see** [common-questions.md](common-questions.md).

## Table of Contents

1. [Advanced Patterns](#advanced-patterns)
   - [Filtering and Pagination](#filtering-and-pagination)
   - [Multi-Company Analysis](#multi-company-analysis)
   - [Error Handling](#error-handling)
   - [Enterprise Configuration](#enterprise-configuration)
   - [Working with Filing Documents](#working-with-filing-documents)
2. [Helper Functions Reference](#helper-functions-reference)
3. [Exporting Skills](#exporting-skills)
   - [Export for Claude Desktop](#export-for-claude-desktop)
   - [Using in Claude Desktop](#using-in-claude-desktop)
   - [Creating External Skills](#creating-external-skills)
   - [Skill Discovery](#skill-discovery)

---

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

### Configuration

EdgarTools can be configured through environment variables for custom SEC mirrors and rate limiting.

**Note**: For deployment configurations (Docker, Kubernetes, etc.), see [Configuration Documentation](../../../../docs/configuration.md#enterprise-configuration).

#### Basic Configuration

Set configuration programmatically before importing edgar modules:

```python
import os

# Required: Set your identity
os.environ['EDGAR_IDENTITY'] = "Your Name your.email@example.com"

# Optional: Custom SEC mirror (enterprise use)
os.environ['EDGAR_BASE_URL'] = "https://sec-mirror.company.com"
os.environ['EDGAR_DATA_URL'] = "https://sec-data.company.com"

# Optional: Adjust rate limiting (default: 9 req/sec)
os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "25"

# Now import and use EdgarTools
from edgar import Company
company = Company("AAPL")
```

#### Available Configuration Options

Key environment variables:

- `EDGAR_IDENTITY` (required): User identification for SEC requests
- `EDGAR_BASE_URL`: SEC website base URL (default: https://www.sec.gov)
- `EDGAR_DATA_URL`: SEC data archives URL (default: https://data.sec.gov)
- `EDGAR_RATE_LIMIT_PER_SEC`: Requests per second (default: 9)
- `EDGAR_USE_LOCAL_DATA`: Enable local caching ("True"/"False")
- `EDGAR_ACCESS_MODE`: Request behavior ("NORMAL"/"CAUTION"/"CRAWL")

#### Programmatic Rate Limiting

Adjust rate limits after import:

```python
from edgar import httpclient

# Update rate limiter
httpclient.update_rate_limiter(requests_per_second=25)
```

**See also**: [Configuration Documentation](../../../../docs/configuration.md) for complete reference including Docker, Kubernetes, and deployment patterns.

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

---

## See Also

- [SKILL.md](SKILL.md) - Core concepts and API reference
- [common-questions.md](common-questions.md) - Complete examples with full code
- [workflows.md](workflows.md) - End-to-end analysis patterns
- [objects.md](objects.md) - Object representations and token estimates
- [Customizing XBRL Standardization](../../../../docs/advanced/customizing-standardization.md) - Advanced XBRL concept mapping and taxonomy customization
