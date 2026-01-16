# Financial Data

**Get financial statements from SEC filings in Python**

EdgarTools provides multiple ways to access financial data, from simple one-liners to advanced XBRL queries. Start with the simplest approach and go deeper when you need more control.

---

## Quick Start: Get Financial Statements

The fastest way to get financial data - no XBRL knowledge required:

```python
from edgar import Company

company = Company("AAPL")

# Get income statement (multiple periods, automatic)
income = company.income_statement()
print(income)

# Get balance sheet and cash flow
balance = company.balance_sheet()
cash_flow = company.cash_flow_statement()
```

**Output:**
```
                                           2024         2023         2022
Revenue                            391,035,000  383,285,000  394,328,000
Cost of Revenue                    210,352,000  214,137,000  223,546,000
Gross Profit                       180,683,000  169,148,000  170,782,000
Operating Expenses                  26,752,000   25,370,000   25,094,000
Operating Income                   153,931,000  143,778,000  145,688,000
...
```

This uses the **Company Facts API** - pre-aggregated data from the SEC that's fast and easy to use.

---

## Choose Your Approach

| Approach | Best For | Complexity |
|----------|----------|------------|
| **[Company API](#company-api)** | Quick analysis, trends, beginners | Simple |
| **[Filing XBRL](#filing-xbrl)** | Specific periods, full statement structure | Moderate |
| **[Multi-Period XBRL](#multi-period-analysis)** | Custom period comparison, stitching | Advanced |
| **[Raw Facts Query](#raw-facts-query)** | Custom metrics, research, data mining | Advanced |

---

## Company API

**Use when:** You want financial trends without worrying about specific filings.

```python
from edgar import Company

company = Company("MSFT")

# Annual data (default: 4 periods)
income = company.income_statement(periods=5, annual=True)

# Quarterly data
quarterly = company.income_statement(periods=8, annual=False)

# All three statements
balance = company.balance_sheet(periods=4)
cash_flow = company.cash_flow_statement(periods=4)
```

**Pros:**
- Single API call for multiple periods
- Automatic period alignment
- Standardized labels across companies

**Cons:**
- Limited to standard line items
- No dimensional breakdowns (segments, products)
- Less control over exact periods

**Learn more:** [Company Facts Guide](company-facts.md)

---

## Filing XBRL

**Use when:** You need data from a specific filing, or want the full statement structure.

```python
from edgar import Company

company = Company("NVDA")
filing = company.get_filings(form="10-K").latest()

# Parse XBRL from the filing
xbrl = filing.xbrl()

# Get statements with full structure
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()
cash_flow = xbrl.statements.cash_flow_statement()

# Convert to DataFrame for analysis
df = income.to_dataframe()
```

**Pros:**
- Full statement hierarchy (subtotals, sections)
- Access to dimensional data (segments, products, geography)
- Exact periods from the filing

**Cons:**
- One filing at a time
- Must handle period selection yourself

**Learn more:** [Extract Financial Statements](extract-statements.md)

---

## Multi-Period Analysis

**Use when:** You need to compare specific filings or build custom time series.

```python
from edgar import Company
from edgar.xbrl import XBRLS

company = Company("TSLA")

# Get multiple 10-K filings
filings = company.get_filings(form="10-K").head(3)

# Create stitched XBRL view
xbrls = XBRLS.from_filings(filings)

# Get stitched income statement across all filings
income = xbrls.statements.income_statement()
print(income)  # Shows all periods aligned
```

**Pros:**
- Custom filing selection
- Aligned periods across filings
- Full XBRL features (dimensions, facts)

**Cons:**
- More setup required
- Must understand period alignment

**Learn more:** [Multi-Period Analysis Guide](../xbrl/guides/multi-period-analysis.md)

---

## Raw Facts Query

**Use when:** You need specific metrics, custom calculations, or research data.

```python
from edgar import Company

company = Company("GOOGL")
filing = company.get_filings(form="10-K").latest()
xbrl = filing.xbrl()

# Query specific facts
revenue_facts = xbrl.facts.query()\
    .by_concept("Revenue")\
    .by_period_type("duration")\
    .to_dataframe()

# Get all facts for a period
q4_facts = xbrl.facts.query()\
    .by_fiscal_period("Q4")\
    .by_fiscal_year(2024)\
    .to_dataframe()

# Search by label
rd_facts = xbrl.facts.query()\
    .by_label("Research", exact=False)\
    .to_dataframe()
```

**Pros:**
- Access any XBRL fact
- Custom filtering and aggregation
- Research-grade data access

**Cons:**
- Requires XBRL knowledge
- More code to write

**Learn more:** [XBRL Querying Guide](../xbrl-querying.md)

---

## Working with Dimensions

Many companies report financial data with dimensional breakdowns (by product, segment, geography).

```python
# Default: simplified view (totals only)
income = xbrl.statements.income_statement()
df = income.to_dataframe()  # ~20 rows

# Full view: includes dimensional breakdowns
df_full = income.to_dataframe(include_dimensions=True)  # ~50+ rows
```

**Common dimensions:**
- `ProductOrServiceAxis` - Revenue/costs by product vs service
- `StatementBusinessSegmentsAxis` - Business unit breakdown
- `StatementGeographicalAxis` - Geographic regions

**Learn more:** [Dimension Handling Guide](../xbrl/concepts/dimension-handling.md)

---

## Cross-Company Comparison

EdgarTools standardizes financial concepts across companies, making comparison easier:

```python
from edgar import Company

# Same API works for any company
companies = ["AAPL", "MSFT", "GOOGL"]

for ticker in companies:
    company = Company(ticker)
    income = company.income_statement(periods=1)
    print(f"{ticker}: {income}")
```

The standardization maps ~2,000 company-specific XBRL tags to 95 standard concepts.

**Learn more:** [Standardization Concepts](../xbrl/concepts/standardization.md)

---

## Common Tasks

### Get Revenue Trend

```python
company = Company("AMZN")
income = company.income_statement(periods=5)
# Revenue row shows 5-year trend
```

### Compare Two Companies

```python
aapl = Company("AAPL").income_statement(periods=3)
msft = Company("MSFT").income_statement(periods=3)
```

### Get Quarterly vs Annual

```python
company = Company("META")
annual = company.income_statement(periods=3, annual=True)
quarterly = company.income_statement(periods=8, annual=False)
```

### Export to DataFrame

```python
income = company.income_statement()
df = income.to_dataframe()
df.to_csv("income_statement.csv")
```

---

## Troubleshooting

### "No financial data found"

Some companies (especially newer or smaller ones) may not have XBRL data:
```python
# Check if XBRL is available
filing = company.get_filings(form="10-K").latest()
if filing.xbrl():
    print("XBRL available")
else:
    print("No XBRL - try filing.text() for raw content")
```

### "Statement is empty or missing rows"

Try including dimensional data:
```python
df = income.to_dataframe(include_dimensions=True)
```

### "Numbers don't match SEC filing"

Check if you're looking at the right period:
```python
# See all available periods
print(xbrl.reporting_periods)
```

---

## Next Steps

- **[Extract Financial Statements](extract-statements.md)** - Detailed guide for statement extraction
- **[Company Facts API](company-facts.md)** - Deep dive into the Company API
- **[XBRL Documentation Hub](../xbrl/index.md)** - Complete XBRL reference
- **[Choosing the Right API](../xbrl/getting-started/choosing-the-right-api.md)** - Decision guide

---

## API Quick Reference

| Method | Returns | Use Case |
|--------|---------|----------|
| `company.income_statement()` | Multi-period income | Quick trends |
| `company.balance_sheet()` | Multi-period balance | Quick trends |
| `company.cash_flow_statement()` | Multi-period cash flow | Quick trends |
| `filing.xbrl()` | XBRL object | Full filing data |
| `xbrl.statements.income_statement()` | Statement object | Structured statement |
| `xbrl.facts.query()` | FactQuery builder | Custom queries |
| `XBRLS.from_filings()` | Stitched XBRL | Multi-filing analysis |
