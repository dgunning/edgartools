# Data Objects

Data Objects in EdgarTools provide structured access to filing content in a format specific to each filing type. These specialized objects extract, organize, and expose the relevant data from SEC filings, making it much easier to work with different filing types programmatically.

## Overview

Data Objects represent parsed SEC filings with type-specific properties and methods. For example, a `TenK` object provides structured access to an annual report's business description, risk factors, and financial data, while a `ThirteenF` object organizes investment holdings into tabular data.

The following filing types are supported:

| Form                       | Data Object                  | Description                           |
|----------------------------|------------------------------|---------------------------------------|
| 10-K                       | `TenK`                       | Annual report                         |
| 10-Q                       | `TenQ`                       | Quarterly report                      |
| 8-K                        | `EightK`                     | Current report                        |
| MA-I                       | `MunicipalAdvisorForm`       | Municipal advisor initial filing      |
| Form 144                   | `Form144`                    | Notice of proposed sale of securities |
| C, C-U, C-AR, C-TR         | `FormC`                      | Form C Crowdfunding Offering          |
| D                          | `FormD`                      | Form D Offering                       |
| 3, 4, 5                    | `Ownership`                  | Ownership reports                     |
| 13F-HR                     | `ThirteenF`                  | 13F Holdings Report                   |
| NPORT-P                    | `FundReport`                 | Fund Report                           |
| EFFECT                     | `Effect`                     | Notice of Effectiveness               |
| Any filing with XBRL       | `FilingXbrl`                 | XBRL-enabled filing                   |

## Converting Filings to Data Objects

To get a Data Object from a `Filing`, use the `obj()` method:

```python
from edgar import get_filings, get_company

# Get a Form 4 filing
filings = get_filings(form="4")
filing = filings[0]
form4 = filing.obj()

# Get the most recent 10-K for Apple
apple = get_company("AAPL")
tenk = apple.get_filings(form="10-K").latest(1)[0].obj()
```

## Data Object Features

Each Data Object provides specialized methods and properties that match the filing type:

### For 10-K Annual Reports (`TenK`)

```python
tenk = filing.obj()

# Access sections by name
business_description = tenk.business
risk_factors = tenk.risk_factors
md_and_a = tenk.management_discussion

# Access financial statements
balance_sheet = tenk.balance_sheet
income_stmt = tenk.income_statement
cash_flow = tenk.cashflow_statement

# Convert to DataFrame
df = tenk.balance_sheet.to_dataframe()
```

### For 8-K Current Reports (`EightK`)

```python
eightk = filing.obj()

# Check for press releases
if eightk.has_press_release:
    press_releases = eightk.press_releases
    
# Get report date
report_date = eightk.date_of_report

# Access specific items
if "Item 2.01" in eightk:
    completion_info = eightk["Item 2.01"]
```

### For Form 4 Ownership Reports (`Form4`)

```python
form4 = filing.obj()

# Access transaction data
trades = form4.market_trades
shares = form4.shares_traded

# Get insider trading summary
trade_summary = form4.get_insider_market_trade_summary()
```

### For 13F Holdings Reports (`ThirteenF`)

```python
thirteen_f = filing.obj()

# Get holdings data
holdings = thirteen_f.infotable
total_value = thirteen_f.total_value
count = thirteen_f.total_holdings

# Convert to DataFrame
holdings_df = holdings.to_dataframe()
```

## Rich Display

Most Data Objects include rich display formatting for use in terminals or notebooks:

```python
# Display formatted information in a terminal or notebook
from rich import print
print(tenk)
print(form4)
```

## Implementation Details

Data Objects are implemented using a mix of regular classes, dataclasses, and Pydantic models, depending on the complexity of the filing type. They handle parsing of HTML, XML, and XBRL content automatically, providing a clean interface to work with filing data.