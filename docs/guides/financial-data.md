# Financial Data

**Get financial statements from SEC filings in Python**

## Quick Start

Three lines to Apple's income statement:

```python
from edgar import Company

company = Company("AAPL")
financials = company.get_financials()
income_statement = financials.income_statement()
```

![AAPL Income Statement](../images/aapl-income-xbrl.webp)

That's it. You now have Apple's full income statement from their latest 10-K filing.

---

## Get Specific Values

Need just one number? Use the convenience methods:

```python
financials = company.get_financials()

revenue = financials.get_revenue()
net_income = financials.get_net_income()
total_assets = financials.get_total_assets()
```

| Method | Returns |
|--------|---------|
| `get_revenue()` | Total revenue / net sales |
| `get_net_income()` | Net income |
| `get_total_assets()` | Total assets |
| `get_total_liabilities()` | Total liabilities |
| `get_stockholders_equity()` | Stockholders' equity |
| `get_operating_cash_flow()` | Operating cash flow |
| `get_free_cash_flow()` | Free cash flow |
| `get_capital_expenditures()` | Capital expenditures |
| `get_current_assets()` | Current assets |
| `get_current_liabilities()` | Current liabilities |

All methods accept `period_offset` to access prior periods (0=current, 1=previous).

---

## Available Statements

```python
financials = company.get_financials()

income = financials.income_statement()
balance = financials.balance_sheet()
cashflow = financials.cashflow_statement()
equity = financials.statement_of_equity()
comprehensive = financials.comprehensive_income()
```

| Statement | Method |
|-----------|--------|
| Income Statement | `income_statement()` |
| Balance Sheet | `balance_sheet()` |
| Cash Flow Statement | `cashflow_statement()` |
| Statement of Equity | `statement_of_equity()` |
| Comprehensive Income | `comprehensive_income()` |

---

## Export to DataFrame

Every statement converts to a pandas DataFrame:

```python
income = financials.income_statement()

# Convert to DataFrame
df = income.to_dataframe()

# Export to CSV
df.to_csv("apple_income_statement.csv")

# Export to Excel
df.to_excel("apple_income_statement.xlsx")
```

The DataFrame preserves the statement structure with labeled rows and period columns.

---

## Quarterly Financials

Use `get_quarterly_financials()` for 10-Q data:

```python
quarterly = company.get_quarterly_financials()
income = quarterly.income_statement()
```

![AAPL Quarterly Income Statement](../images/aapl-income-quarterly-xbrl.webp)

| Need | Method |
|------|--------|
| Annual (10-K) | `company.get_financials()` |
| Quarterly (10-Q) | `company.get_quarterly_financials()` |

---

## Compare Multiple Periods

To analyze trends across multiple filings, use `XBRLS`:

```python
from edgar.xbrl import XBRLS

# Get last 3 annual filings
filings = company.get_filings(form="10-K").head(3)

# Stitch them together
xbrls = XBRLS.from_filings(filings)

# Get income statement across all periods
income = xbrls.statements.income_statement()
```

This aligns the periods and concepts across filings for easy comparison.

**Learn more:** [Multi-Period Analysis Guide](../xbrl/guides/multi-period-analysis.md)

---

## Cross-Company Comparison

The same API works for any public company:

```python
for ticker in ["AAPL", "MSFT", "GOOGL"]:
    company = Company(ticker)
    financials = company.get_financials()
    if financials:
        revenue = financials.get_revenue()
        print(f"{ticker}: ${revenue:,.0f}")
```

EdgarTools standardizes ~2,000 company-specific XBRL tags to 95 standard concepts, making cross-company analysis straightforward.

---

## Going Deeper: Filing-Level Access

The methods above use the latest filing automatically. When you need a specific filing—like last year's 10-K or a particular quarter—access the XBRL directly:

```python
# Get a specific filing
filing = company.get_filings(form="10-K", amendments=False).latest()

# Parse XBRL
xbrl = filing.xbrl()

# Get statements
income = xbrl.statements.income_statement()
balance = xbrl.statements.balance_sheet()
```

This gives you full control over which filing you're analyzing.

### Why skip amendments?

Use `amendments=False` when fetching filings. Amended filings (10-K/A) sometimes contain only the corrected sections, not complete financial statements.

---

## Advanced Topics

### Working with Dimensions

Companies report breakdowns by segment, product, or geography:

```python
income = financials.income_statement()

# Default: totals only
df = income.to_dataframe()

# Include dimensional breakdowns
df_full = income.to_dataframe(include_dimensions=True)
```

Common dimensions:
- `ProductOrServiceAxis` – Revenue by product vs service
- `StatementBusinessSegmentsAxis` – Business unit breakdown
- `StatementGeographicalAxis` – Geographic regions

**Learn more:** [Dimension Handling Guide](../xbrl/concepts/dimension-handling.md)

### Raw Facts Query

Query individual XBRL facts for research or custom calculations:

```python
xbrl = filing.xbrl()

# Find all revenue facts
revenue_facts = xbrl.facts.query()\
    .by_concept("Revenue")\
    .to_dataframe()

# Search by label
rd_facts = xbrl.facts.query()\
    .by_label("Research", exact=False)\
    .to_dataframe()
```

**Learn more:** [XBRL Querying Guide](../xbrl-querying.md)

---

## Troubleshooting

### "No financial data found"

Some companies (especially newer or smaller ones) may not have XBRL data:

```python
filing = company.get_filings(form="10-K").latest()
if filing.xbrl():
    print("XBRL available")
else:
    print("No XBRL - try filing.text() for raw content")
```

### "Statement is empty"

Try including dimensional data:

```python
df = income.to_dataframe(include_dimensions=True)
```

### "Numbers don't match the SEC website"

Check that you're looking at the right period:

```python
xbrl = filing.xbrl()
print(xbrl.reporting_periods)
```

---

## API Quick Reference

### Company-Level (Easiest)

| Method | Description |
|--------|-------------|
| `company.get_financials()` | Latest annual financials (10-K) |
| `company.get_quarterly_financials()` | Latest quarterly financials (10-Q) |

### Financials Object

| Method | Description |
|--------|-------------|
| `financials.income_statement()` | Income statement |
| `financials.balance_sheet()` | Balance sheet |
| `financials.cashflow_statement()` | Cash flow statement |
| `financials.get_revenue()` | Revenue value |
| `financials.get_net_income()` | Net income value |
| `financials.get_total_assets()` | Total assets value |
| `financials.get_financial_metrics()` | Dict of all key metrics |

### Statement Object

| Method | Description |
|--------|-------------|
| `statement.to_dataframe()` | Convert to pandas DataFrame |
| `statement.to_dataframe(include_dimensions=True)` | Include dimensional breakdowns |

### Filing-Level (More Control)

| Method | Description |
|--------|-------------|
| `filing.xbrl()` | Parse XBRL from filing |
| `xbrl.statements.income_statement()` | Get income statement |
| `xbrl.facts.query()` | Query individual facts |

### Multi-Period Analysis

| Method | Description |
|--------|-------------|
| `XBRLS.from_filings(filings)` | Stitch multiple filings together |
| `xbrls.statements.income_statement()` | Aligned multi-period statement |

---

## Next Steps

- **[Multi-Period Analysis](../xbrl/guides/multi-period-analysis.md)** – Build custom time series
- **[Standardization](../xbrl/concepts/standardization.md)** – How cross-company comparison works
- **[XBRL Documentation](../xbrl/index.md)** – Complete XBRL reference
