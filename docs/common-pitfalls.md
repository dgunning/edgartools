---
description: Common mistakes and gotchas when using EdgarTools. Avoid these pitfalls to save time and get correct results.
---

# Common Pitfalls

New to EdgarTools? This page covers the most frequent mistakes and how to avoid them.

---

## Which API Should I Use?

EdgarTools has three ways to get financial data. This causes the most confusion for new users.

| I want to... | Use this | Not this |
|---|---|---|
| Get revenue, net income, balance sheet | `company.get_financials()` | `company.get_facts()` or `filing.xbrl()` |
| Compare Apple vs Microsoft financials | `company.get_financials()` for each | Manual XBRL parsing |
| Get 5+ years of historical trends | `company.get_facts()` | Iterating over 5 filings |
| Get segment breakdowns or footnotes | `filing.xbrl()` | `get_financials()` (no segments) |

**Rule of thumb:** Start with `get_financials()`. It covers 95% of use cases. Only use `get_facts()` for 4+ years of history, and `filing.xbrl()` for segments/footnotes.

For a detailed comparison, see [Choosing the Right API](xbrl/getting-started/choosing-the-right-api.md).

---

## Financial Data

### Use `get_financials()`, not `filing.xbrl()`

```python
# WRONG: Too complex for simple financial data
filing = Company("AAPL").get_filings(form="10-K").latest()
xbrl = filing.xbrl()
statements = xbrl.statements
income = statements.income_statement()

# RIGHT: Direct and simple
financials = Company("AAPL").get_financials()
income = financials.income_statement()
```

### Use `get_financials()`, not `get_facts()` for standard data

```python
# WRONG: get_facts() is for historical trends, not everyday use
facts = company.get_facts()
income = facts.income_statement(periods=3, annual=True)

# RIGHT: get_financials() already includes 3 years
financials = company.get_financials()
income = financials.income_statement()        # Already 3 years
revenue = financials.get_revenue()             # Single current value
```

### Quick getters can return `None`

Always check before doing math:

```python
revenue = financials.get_revenue()
net_income = financials.get_net_income()

# WRONG: Will crash if either is None
margin = net_income / revenue

# RIGHT: Check first
if revenue and net_income:
    margin = net_income / revenue
```

### `period_offset=0` means current year, not prior year

```python
this_year  = financials.get_revenue()                   # period_offset=0 (default)
last_year  = financials.get_revenue(period_offset=1)    # 1 year ago
two_ago    = financials.get_revenue(period_offset=2)    # 2 years ago
```

### Financial values are in actual dollars

Values from `get_financials()` are in real dollars, not thousands or millions:

```python
revenue = financials.get_revenue()    # e.g. 391035000000
print(f"${revenue/1e9:.1f}B")         # "$391.0B"
```

### The cash flow method is `cashflow_statement()`

The canonical method name is `cashflow_statement()` (no underscore between "cash" and "flow"). The alias `cash_flow_statement()` also works. All three statements follow the same pattern:

```python
financials.income_statement()       # Income statement
financials.balance_sheet()          # Balance sheet
financials.cashflow_statement()     # Cash flow statement (cash_flow_statement() also works)
```

---

## Filings

### Always limit before iterating

```python
# WRONG: Loads ALL filings into memory
for filing in company.get_filings():
    process(filing)

# RIGHT: Limit first
for filing in company.get_filings(form="10-K").head(10):
    process(filing.obj())
```

### Use `.head(n)`, not `list(filings)[:n]`

```python
# WRONG: Converts ALL filings to a list first
recent = list(company.get_filings())[:5]

# RIGHT: Only fetches 5
recent = company.get_filings().head(5)
```

### Use `filing.obj()` for sections, not `filing.document()`

```python
# WRONG: Raw document text, no structure
doc = filing.document()
text = doc.text()

# RIGHT: Parsed data object with sections
tenk = filing.obj()
risk_factors = tenk['Item 1A']
business = tenk['Item 1']
```

---

## Insider Trading (Form 4)

### Use `get_ownership_summary()`, not raw DataFrames

```python
summary = form4.get_ownership_summary()
print(f"Activity: {summary.primary_activity}")   # "Purchase", "Sale", "Mixed"
print(f"Net shares: {summary.net_change:,}")      # positive=buy, negative=sell
print(f"Net value: ${summary.net_value:,.0f}")
```

### `get_ownership_summary()` returns ONE object, not a list

```python
# WRONG: Will crash — summary is not iterable
summary = form4.get_ownership_summary()
for item in summary:        # TypeError!
    print(item.insider_name)

# RIGHT: Access properties directly
summary = form4.get_ownership_summary()
summary.insider_name        # "Tim Cook"
summary.primary_activity    # "Sale"

# To process MULTIPLE filings, loop over filings:
for filing in company.get_filings(form="4").head(20):
    summary = filing.obj().get_ownership_summary()
    print(f"{summary.insider_name}: {summary.primary_activity}")
```

### Transaction codes have specific meanings

| Code | Meaning | Signal |
|------|---------|--------|
| P | Open market purchase | Strong buy signal |
| S | Open market sale | Sell signal |
| A | Grant/Award | Compensation, not a purchase |
| M | Option exercise | Converting options, not buying |
| F | Tax withholding | Shares sold to cover taxes |

The `primary_activity` property on `TransactionSummary` interprets these for you.

---

## Institutional Holdings (13F)

### Holdings value is in $1,000s, not dollars

```python
holdings = thirteenf.holdings

# WRONG: Off by 1000x
total = holdings['Value'].sum()

# RIGHT: Multiply by 1000
total = holdings['Value'].sum() * 1000
```

### Use CUSIP for reliable lookups, not ticker

```python
# Ticker may be missing for some securities
apple = holdings[holdings['Cusip'] == '037833100']    # Reliable
apple = holdings[holdings['Ticker'] == 'AAPL']         # May miss some
```

### Don't iterate all 13Fs to find holders of a stock

```python
# WRONG: Iterating 8,000+ filings to find "who holds Apple?"
for filing in get_filings(form="13F-HR"):
    holdings = filing.obj().holdings
    if 'AAPL' in holdings['Ticker'].values:
        print(filing.company)

# RIGHT: Filter by filer first
filing = get_filings(form="13F-HR").filter(company="BERKSHIRE")[0]
holdings = filing.obj().holdings
```

### 13F filings have a 45-day lag

Holdings are reported as of quarter-end, but filings aren't due for 45 days. Q3 (Sep 30) data may not appear until mid-November.

---

## 10-K / 10-Q / 8-K Reports

### Item keys differ between report types

```python
# 10-K / 10-Q: "Item 1", "Item 1A", "Item 7"
tenk['Item 1A']       # Risk Factors

# 8-K: "Item 1.01", "Item 5.02" (with dots)
eightk['Item 5.02']   # Personnel Changes
```

### Not all items exist in every filing

```python
risk_factors = tenk.risk_factors
if risk_factors:
    print(risk_factors.text[:1000])
else:
    print("No risk factors section in this filing")
```

---

## Exporting Data

### Export statements, not the financials object

```python
financials = company.get_financials()

# WRONG: financials object has no to_dataframe()
df = financials.to_dataframe()   # AttributeError

# RIGHT: call to_dataframe() on the individual statement
df = financials.income_statement().to_dataframe()
df = financials.balance_sheet().to_dataframe()
df = financials.cashflow_statement().to_dataframe()
```

### Export to CSV or Excel

```python
income = company.get_financials().income_statement()

# CSV
income.to_dataframe().to_csv("income.csv")

# Excel
income.to_dataframe().to_excel("income.xlsx")
```

### Export filings list (not financial data)

```python
# Export a list of filings to a DataFrame
filings = company.get_filings(form="10-K")
df = filings.to_pandas()   # One row per filing
df.to_csv("10k_filings.csv")
```

### Financial values are raw numbers (not formatted)

`get_revenue()` returns an integer like `391035000000`, not `"$391B"`. Format it yourself:

```python
revenue = financials.get_revenue()
print(f"${revenue / 1e9:.1f}B")   # "$391.0B"
```

---

## XBRL

### `filing.xbrl()` can return `None`

Not all filings have XBRL data. Always check:

```python
xbrl = filing.xbrl()
if xbrl:
    print(xbrl.entity_name)
else:
    print("No XBRL data in this filing")
```

### XBRL concept names vary by company

Different companies use different concept names for the same thing (e.g., "Revenues" vs "RevenueFromContractWithCustomerExcludingAssessedTax"). Use `get_financials()` instead, which normalizes these automatically.

```python
# Instead of guessing concept names:
revenue = company.get_financials().get_revenue()
```
