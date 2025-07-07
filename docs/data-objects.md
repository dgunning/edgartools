# Data Objects

Data Objects in EdgarTools provide structured access to filing content in a format specific to each filing type. These specialized objects extract, organize, and expose the relevant data from SEC filings, making it much easier to work with different filing types programmatically.

## Overview

Data Objects represent parsed SEC filings with type-specific properties and methods. They automatically handle the complex parsing of raw filing data (HTML, XML, XBRL) and present a clean, intuitive interface tailored to each filing type.

For example, a `TenK` object provides structured access to an annual report's business description, risk factors, and financial data, while a `ThirteenF` object organizes investment holdings into tabular data.

## Supported Filing Types

EdgarTools provides specialized Data Objects for the most common SEC filing types:

| Form                       | Data Object                  | Description                           | Key Features                                      |
|----------------------------|------------------------------|---------------------------------------|---------------------------------------------------|
| 10-K                       | `TenK`                       | Annual report                         | Section access, financial statements, XBRL data   |
| 10-Q                       | `TenQ`                       | Quarterly report                      | Section access, financial statements, XBRL data   |
| 8-K                        | `EightK`                     | Current report                        | Item access, press releases, event categorization |
| 3, 4, 5                    | `Ownership`                  | Ownership reports                     | Transaction details, insider information          |
| 13F-HR                     | `ThirteenF`                  | 13F Holdings Report                   | Portfolio holdings, securities information        |
| NPORT-P                    | `FundReport`                 | Fund Report                           | Fund portfolio data, investments                  |
| D                          | `FormD`                      | Form D Offering                       | Exempt offering details                           |
| C, C-U, C-AR, C-TR         | `FormC`                      | Form C Crowdfunding Offering          | Crowdfunding details, issuer information          |
| MA-I                       | `MunicipalAdvisorForm`       | Municipal advisor initial filing      | Municipal advisor information                     |
| Form 144                   | `Form144`                    | Notice of proposed sale of securities | Proposed sale details                             |
| EFFECT                     | `Effect`                     | Notice of Effectiveness               | Registration statement effectiveness              |
| Any filing with XBRL       | `FilingXbrl`                 | XBRL-enabled filing                   | Access to structured XBRL data                    |

## Converting Filings to Data Objects

To get a Data Object from a `Filing`, use the `obj()` method:

```python
from edgar import Company, get_filings

# Method 1: From a company object
apple = Company("AAPL")
filings = apple.get_filings(form="10-K")
latest_10k = filings.latest()
tenk = latest_10k.obj()

# Method 2: From filings search
form4_filings = get_filings(form="4", limit=10)
form4 = form4_filings[0].obj()

# Method 3: Direct from a filing accessor
filing = apple.get_latest_filing("10-K")
tenk = filing.obj()
```

## Working with Data Objects

### Company Reports (10-K, 10-Q)

```python
# Get a 10-K data object
tenk = filing.obj()

# Access document sections by name
business_description = tenk.business
risk_factors = tenk.risk_factors
md_and_a = tenk.management_discussion
legal_proceedings = tenk.legal_proceedings

# Access financial statements
balance_sheet = tenk.balance_sheet
income_stmt = tenk.income_statement
cash_flow = tenk.cashflow_statement

# Get specific financial values
revenue = income_stmt.get_value("Revenues")
net_income = income_stmt.get_value("NetIncomeLoss")
assets = balance_sheet.get_value("Assets")

# Convert to DataFrame for analysis
income_df = income_stmt.to_dataframe()
balance_df = balance_sheet.to_dataframe()

# Access raw text of a section
risk_text = tenk.get_section_text("Risk Factors")
```

### Current Reports (8-K)

```python
eightk = filing.obj()

# Get basic information
report_date = eightk.date_of_report
items_reported = eightk.items

# Check for specific events
has_acquisition = eightk.has_item("2.01")  # Acquisition/disposition
has_officer_change = eightk.has_item("5.02")  # Officer changes

# Access specific items by number
if "Item 2.01" in eightk:
    acquisition_info = eightk["Item 2.01"]
    
# Get press releases
if eightk.has_press_release:
    press_releases = eightk.press_releases
    for pr in press_releases:
        print(f"Title: {pr.title}")
        print(f"Content: {pr.content[:100]}...")
```

### Insider Trading (Forms 3, 4, 5)

```python
form4 = filing.obj()

# Get basic information
insider_name = form4.reporting_owner
company_name = form4.issuer
filing_date = form4.filing_date

# Access transaction data
for transaction in form4.transactions:
    print(f"Date: {transaction.transaction_date}")
    print(f"Type: {transaction.transaction_code}")  # P for purchase, S for sale
    print(f"Shares: {transaction.shares}")
    print(f"Price: ${transaction.price_per_share}")
    print(f"Value: ${transaction.value}")

# Get summary of market trades
buy_count, sell_count = form4.get_buy_sell_counts()
net_shares = form4.get_net_shares_traded()
```

### Investment Fund Holdings (13F)

```python
thirteen_f = filing.obj()

# Get fund information
fund_name = thirteen_f.manager_name
report_date = thirteen_f.report_date

# Get holdings summary
total_value = thirteen_f.total_value
holdings_count = thirteen_f.total_holdings

# Access all holdings
holdings = thirteen_f.infotable
for holding in holdings:
    print(f"Company: {holding.name}")
    print(f"Value: ${holding.value:,.2f}")
    print(f"Shares: {holding.shares:,}")
    print(f"Security Type: {holding.security_type}")

# Convert to DataFrame for analysis
holdings_df = holdings.to_dataframe()
top_holdings = holdings_df.sort_values('value', ascending=False).head(10)
```

## Rich Display

Most Data Objects include rich display formatting for use in terminals or notebooks:

```python
# Display formatted information in a terminal or notebook
print(tenk)  # Shows a summary of the 10-K filing
print(form4)  # Shows insider transaction details
print(thirteen_f)  # Shows fund holdings summary

# In Jupyter notebooks, objects render as HTML tables automatically
tenk.balance_sheet  # Displays as formatted table
thirteen_f.infotable  # Displays as holdings table
```

## Error Handling

Data Objects handle common parsing errors gracefully:

```python
try:
    data_obj = filing.obj()
except UnsupportedFilingTypeError:
    print("This filing type doesn't have a specialized data object")
except ParsingError as e:
    print(f"Error parsing filing: {e}")
    # Fall back to generic access
    text = filing.text
```

## Performance Considerations

- Data Objects parse filing content on-demand
- Large filings (like 10-Ks) may take a few seconds to parse
- Consider using local storage for batch processing


## Implementation Details

Data Objects are implemented using a mix of regular classes, dataclasses, and Pydantic models, depending on the complexity of the filing type. They handle parsing of HTML, XML, and XBRL content automatically, providing a clean interface to work with filing data.