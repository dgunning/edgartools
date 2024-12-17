# Company Financials

## Getting company financials

The easiest way to get company financials is to use the `Company.financials` property.

```python
from edgar import Company

company = Company("AAPL")
financials = company.financials
```

The `financials` property returns a `Financials` instance.
This instance has methods that return the balance sheet, income statement and cash flow statement.

```python
balance_sheet = financials.balance_sheet
income_statement = financials.income
cash_flow_statement = financials.cash_flow
```

### Financials for multiple years

The `MultiFinancials` class can be used to get financials for multiple years. To use it first you need to get the filings for the years you want.


```python
from edgar import MultiFinancials

filings = company.latest("10-K", 5)
financials = MultiFinancials(filings)
```

The `financials` property returns a `MultiFinancials` instance.
This instance has methods that return the balance sheet, income statement and cash flow statement.

```python
balance_sheet = financials.balance_sheet
income_statement = financials.income
cash_flow_statement = financials.cash_flow
```



