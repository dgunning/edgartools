# Form4 Class Documentation

## Overview

The `Form4` class represents SEC Form 4 - the Statement of Changes in Beneficial Ownership. Form 4 filings are required when corporate insiders (officers, directors, and 10%+ shareholders) buy or sell company stock. These filings must be submitted within two business days of the transaction.

**Key Features:**
- Parse and access insider transaction details
- View purchase and sale transactions with prices and values
- Track option exercises, grants, and other equity changes
- Access derivative and non-derivative transaction tables
- Get computed summaries with net change and total value

## Quick Start

Get started with Form 4 in 3 lines:

```python
from edgar import Company

# Get a company's Form 4 filings
company = Company("AAPL")
filings = company.get_filings(form="4")
filing = filings[0]

# Parse into Form4 object
form4 = filing.obj()

# Access transaction information
print(f"Insider: {form4.insider_name}")
print(f"Position: {form4.position}")
print(f"Issuer: {form4.issuer.name} ({form4.issuer.ticker})")

# Get transaction summary
summary = form4.get_ownership_summary()
print(f"Net Change: {summary.net_change:,} shares")
print(f"Activity: {summary.primary_activity}")
```

## Common Actions

Quick reference for working with Form 4 filings:

### Access Form 4 from Filing
```python
from edgar import Company

company = Company("MSFT")
filings = company.get_filings(form="4")
filing = filings[0]

# Parse into Form4 object
form4 = filing.obj()
```

### Access Issuer Information
```python
# Company being traded
issuer = form4.issuer
print(issuer.name)     # Company name
print(issuer.ticker)   # Trading symbol
print(issuer.cik)      # CIK number
```

### Access Insider Information
```python
# Who made the transaction
print(form4.insider_name)  # Insider's name
print(form4.position)      # Position (Director, Officer, etc.)

# Get detailed owner info
for owner in form4.reporting_owners.owners:
    print(f"Name: {owner.name}")
    print(f"Is Director: {owner.relationship.is_director}")
    print(f"Is Officer: {owner.relationship.is_officer}")
    print(f"Is 10% Owner: {owner.relationship.is_ten_pct_owner}")
    if owner.relationship.officer_title:
        print(f"Title: {owner.relationship.officer_title}")
```

### Access Market Trades
```python
# Common stock purchases and sales
trades = form4.market_trades
if trades is not None and not trades.empty:
    print(trades)  # DataFrame with all market transactions

# Filter by transaction type
purchases = form4.common_stock_purchases
sales = form4.common_stock_sales
```

### Access Option Exercises
```python
# Get option exercise transactions
exercises = form4.option_exercises
if not exercises.empty:
    print(exercises)
```

### Get Transaction Summary
```python
# Get a TransactionSummary object with computed properties
summary = form4.get_ownership_summary()

# Key computed metrics
print(f"Net Change: {summary.net_change:,} shares")
print(f"Net Value: ${summary.net_value:,.2f}")
print(f"Primary Activity: {summary.primary_activity}")
print(f"Remaining Shares: {summary.remaining_shares:,}")

# Access individual transactions
for trans in summary.transactions:
    print(f"{trans.transaction_type}: {trans.shares:,} @ ${trans.price_per_share}")
```

### Convert to DataFrame
```python
# Get detailed transactions as DataFrame
df = form4.to_dataframe(detailed=True)
print(df)

# Get summary as single row
df_summary = form4.to_dataframe(detailed=False)
print(df_summary)
```

## Properties and Attributes

### Core Information
```python
form4.form                     # Form type ("4")
form4.reporting_period         # Date of the transaction
form4.insider_name             # Insider's name
form4.position                 # Insider's position(s)
form4.remarks                  # Any remarks or notes
```

### Issuer Details
```python
form4.issuer                   # Issuer object
form4.issuer.name              # Company name
form4.issuer.ticker            # Ticker symbol
form4.issuer.cik               # CIK number
```

### Transaction Tables
```python
form4.non_derivative_table     # NonDerivativeTable (common stock)
form4.derivative_table         # DerivativeTable (options, etc.)
form4.market_trades            # DataFrame of P/S transactions
form4.common_stock_purchases   # Purchase transactions only
form4.common_stock_sales       # Sale transactions only
form4.option_exercises         # Option exercise transactions
form4.derivative_trades        # Derivative transactions
```

### Other Attributes
```python
form4.reporting_owners         # ReportingOwners object
form4.footnotes                # Footnotes object
form4.signatures               # OwnerSignatures object
form4.no_securities            # True if no securities reported
```

## Working with TransactionSummary

When you call `form4.get_ownership_summary()`, you get a `TransactionSummary` object with computed properties:

```python
summary = form4.get_ownership_summary()

# Key properties
summary.net_change             # Total shares bought - sold
summary.net_value              # Total value bought - sold
summary.primary_activity       # "Purchase", "Sale", "Mixed", etc.
summary.transaction_types      # List of unique transaction types
summary.remaining_shares       # Shares owned after transactions

# Transaction checks
summary.has_derivatives        # True if derivative transactions exist
summary.has_only_derivatives   # True if only derivative transactions
summary.has_non_derivatives    # True if common stock transactions

# Access individual transactions
for trans in summary.transactions:
    print(f"Type: {trans.transaction_type}")
    print(f"Code: {trans.code}")
    print(f"Shares: {trans.shares_numeric}")
    print(f"Price: {trans.price_numeric}")
    print(f"Value: {trans.value_numeric}")
```

See [TransactionSummary.md](TransactionSummary.md) for complete documentation.

## Transaction Codes

Form 4 uses standard transaction codes:

| Code | Description |
|------|-------------|
| **P** | Open market or private purchase |
| **S** | Open market or private sale |
| **A** | Grant or award |
| **M** | Exercise of derivative (exempt) |
| **X** | Exercise of in/at-the-money derivative |
| **F** | Payment of exercise price or tax |
| **G** | Gift |
| **C** | Conversion of derivative |
| **D** | Disposition to the issuer |

## Finding Form 4 Filings

### By Company
```python
from edgar import Company

company = Company("TSLA")
filings = company.get_filings(form="4")

# Get recent filings
recent = filings.head(10)
```

### By Search
```python
from edgar import get_filings

# All Form 4 filings in a period
filings = get_filings(2024, 1, form="4")

# Filter by date
filings = get_filings(form="4", filing_date="2024-12-01:2024-12-15")
```

### By Specific Insider
```python
from edgar import Entity

# Search for insider by name
insider = Entity.search("Elon Musk")[0]
filings = insider.get_filings(form="4")
```

## Display and Output

### Rich Terminal Display
```python
# Display formatted output in terminal
print(form4)

# Shows insider info, transactions table, and summary
```

### HTML Output
```python
# Get HTML representation
html = form4.to_html()

# In Jupyter, automatically renders
form4  # displays HTML
```

### DataFrame Export
```python
# All transactions with metadata
df = form4.to_dataframe(detailed=True, include_metadata=True)

# Summary row
df_summary = form4.to_dataframe(detailed=False)

# Transactions only (no metadata columns)
df_trans = form4.to_dataframe(detailed=True, include_metadata=False)
```

## Best Practices

### Check Data Availability
```python
# Market trades may be empty
if form4.market_trades is not None and not form4.market_trades.empty:
    print(form4.market_trades)

# Option exercises may not exist
if not form4.option_exercises.empty:
    print(form4.option_exercises)
```

### Use Computed Properties
```python
summary = form4.get_ownership_summary()

# Good - uses computed metrics
net_change = summary.net_change
net_value = summary.net_value

# Less ideal - manual calculation
# purchases - sales from raw tables
```

### Handle Footnotes
```python
# Shares may include footnote references
for trans in summary.transactions:
    shares = trans.shares_numeric  # Handles footnotes
    if shares is not None:
        print(f"Shares: {shares:,}")
```

## Common Use Cases

### Track Large Insider Purchases
```python
from edgar import get_filings

filings = get_filings(form="4", filing_date="2024-12-01:")

for filing in filings:
    form4 = filing.obj()
    summary = form4.get_ownership_summary()

    # Filter for significant purchases
    if summary.net_change > 10000 and summary.net_value > 100000:
        print(f"{form4.insider_name} @ {form4.issuer.name}")
        print(f"  Bought: {summary.net_change:,} shares")
        print(f"  Value: ${summary.net_value:,.0f}")
```

### Analyze CEO Transactions
```python
company = Company("AAPL")
filings = company.get_filings(form="4")

for filing in filings:
    form4 = filing.obj()

    # Check if CEO
    for owner in form4.reporting_owners.owners:
        if owner.relationship.officer_title and "CEO" in owner.relationship.officer_title:
            summary = form4.get_ownership_summary()
            print(f"CEO {form4.insider_name}: {summary.primary_activity}")
            print(f"  Net Change: {summary.net_change:,}")
```

### Build Transaction Database
```python
import pandas as pd
from edgar import get_filings

filings = get_filings(form="4", filing_date="2024-12-01:")

all_transactions = []
for filing in filings:
    form4 = filing.obj()
    df = form4.to_dataframe(detailed=True)
    df['AccessionNumber'] = filing.accession_number
    all_transactions.append(df)

# Combine all transactions
transactions_db = pd.concat(all_transactions, ignore_index=True)
```

## Troubleshooting

### No market_trades found

Form 4 may only contain derivative transactions:
```python
if form4.market_trades is None or form4.market_trades.empty:
    # Check for derivative transactions
    if form4.derivative_table.has_transactions:
        print("Only derivative transactions in this filing")
```

### Missing price information

Some transactions don't have prices (grants, gifts):
```python
summary = form4.get_ownership_summary()
for trans in summary.transactions:
    if trans.price_numeric:
        print(f"Price: ${trans.price_numeric}")
    else:
        print(f"No price (transaction type: {trans.code})")
```

### Multiple reporting owners

Some filings have multiple insiders:
```python
if len(form4.reporting_owners.owners) > 1:
    print("Multiple reporting owners:")
    for owner in form4.reporting_owners.owners:
        print(f"  - {owner.name}")
```

## Agent Implementation Guide

If you're an AI agent implementing insider transaction analysis:

### Step 1: Get Form 4 Filings
```python
from edgar import Company

company = Company("TICKER_OR_CIK")
filings = company.get_filings(form="4")
```

### Step 2: Parse and Analyze
```python
for filing in filings:
    form4 = filing.obj()
    summary = form4.get_ownership_summary()

    # Use computed properties for analysis
    print(f"Activity: {summary.primary_activity}")
    print(f"Net Change: {summary.net_change}")
```

### Step 3: Convert for Further Processing
```python
# Get as DataFrame for analysis
df = form4.to_dataframe(detailed=True)

# Or get summary for quick screening
summary_df = form4.to_dataframe(detailed=False)
```

### Key Points for Agents

1. **Use get_ownership_summary()** - Returns TransactionSummary with computed metrics
2. **Check data availability** - Not all Form 4s have market trades
3. **Handle None values** - Prices and some fields may be None
4. **Use to_dataframe()** - For bulk analysis and pandas operations
5. **Different transaction types** - P/S are market trades, M/X are exercises, etc.

## Related Classes

- **Form3** - Initial beneficial ownership statement
- **Form5** - Annual statement of beneficial ownership
- **Ownership** - Base class for all ownership forms
- **TransactionSummary** - Computed transaction metrics
- **TransactionActivity** - Individual transaction details
- **Issuer** - Company information
- **ReportingOwners** - Insider information

## See Also

- [Form3.md](Form3.md) - Initial ownership documentation
- [Form5.md](Form5.md) - Annual statement documentation
- [TransactionSummary.md](TransactionSummary.md) - Transaction summary details
- [OwnershipSummary.md](OwnershipSummary.md) - Summary base class
