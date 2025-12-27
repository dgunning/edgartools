# Form5 Class Documentation

## Overview

The `Form5` class represents SEC Form 5 - the Annual Statement of Changes in Beneficial Ownership. Form 5 is used to report transactions that weren't required to be reported on Form 4, or transactions that should have been reported on Form 4 but were not. Form 5 is due within 45 days after the company's fiscal year end.

**Key Features:**
- Report transactions exempt from Form 4 filing
- Report previously unreported Form 4 transactions
- Track small acquisitions under $10,000
- Report gift transactions
- Annual summary of beneficial ownership changes

## Quick Start

Get started with Form 5 in 3 lines:

```python
from edgar import Company

# Get a company's Form 5 filings
company = Company("AAPL")
filings = company.get_filings(form="5")
filing = filings[0]

# Parse into Form5 object
form5 = filing.obj()

# Access transaction information
print(f"Insider: {form5.insider_name}")
print(f"Position: {form5.position}")

# Get transaction summary
summary = form5.get_ownership_summary()
print(f"Net Change: {summary.net_change:,} shares")
print(f"Activity: {summary.primary_activity}")
```

## Form 5 vs Form 4

| Aspect | Form 4 | Form 5 |
|--------|--------|--------|
| Timing | Within 2 business days | Within 45 days of fiscal year end |
| Purpose | Report most transactions | Report exempt/late transactions |
| Typical Transactions | Purchases, sales, exercises | Gifts, small acquisitions, late filings |
| Frequency | Per-transaction | Annual |

### Transactions Typically on Form 5

- Small acquisitions (under $10,000)
- Transactions exempt from Section 16(b) liability
- Gifts of securities
- Transactions that should have been on Form 4 but weren't
- Certain stock plan transactions

## Common Actions

### Access Form 5 from Filing
```python
from edgar import Company

company = Company("MSFT")
filings = company.get_filings(form="5")
filing = filings[0]

# Parse into Form5 object
form5 = filing.obj()
```

### Access Transaction Data
```python
# Form 5 uses the same interface as Form 4
summary = form5.get_ownership_summary()

# Key metrics
print(f"Net Change: {summary.net_change:,}")
print(f"Net Value: ${summary.net_value:,.2f}")
print(f"Activity: {summary.primary_activity}")

# Access individual transactions
for trans in summary.transactions:
    print(f"{trans.transaction_type}: {trans.shares_numeric:,} shares")
```

### Access Market Trades
```python
# Common stock purchases and sales
trades = form5.market_trades
if trades is not None and not trades.empty:
    print(trades)
```

### Convert to DataFrame
```python
# Get detailed transactions as DataFrame
df = form5.to_dataframe(detailed=True)

# Get summary as single row
df_summary = form5.to_dataframe(detailed=False)
```

## Properties and Attributes

### Core Information
```python
form5.form                     # Form type ("5")
form5.reporting_period         # Fiscal year end date
form5.insider_name             # Insider's name
form5.position                 # Insider's position(s)
form5.remarks                  # Any remarks
```

### Transaction Tables
```python
form5.non_derivative_table     # NonDerivativeTable (common stock)
form5.derivative_table         # DerivativeTable (options, etc.)
form5.market_trades            # DataFrame of P/S transactions
```

### Other Attributes
```python
form5.issuer                   # Issuer object
form5.reporting_owners         # ReportingOwners object
form5.footnotes                # Footnotes object
form5.signatures               # OwnerSignatures object
```

## Working with TransactionSummary

Form 5 uses the same `TransactionSummary` class as Form 4:

```python
summary = form5.get_ownership_summary()

# All the same properties as Form 4
summary.net_change             # Net shares change
summary.net_value              # Net dollar value
summary.primary_activity       # Activity classification
summary.transactions           # List of TransactionActivity
summary.remaining_shares       # Shares after transactions
```

See [TransactionSummary.md](TransactionSummary.md) for complete documentation.

## Finding Form 5 Filings

### By Company
```python
from edgar import Company

company = Company("TSLA")
filings = company.get_filings(form="5")
```

### By Search
```python
from edgar import get_filings

# All Form 5 filings in a period
filings = get_filings(2024, 1, form="5")

# Filter by date (Form 5 typically filed in Q1)
filings = get_filings(form="5", filing_date="2024-01-01:2024-03-15")
```

### Search All Ownership Forms
```python
# Get all ownership forms together
filings = company.get_filings(form=["3", "4", "5"])
```

## Display and Output

### Rich Terminal Display
```python
# Display formatted output in terminal
print(form5)
```

### HTML Output
```python
# Get HTML representation
html = form5.to_html()

# In Jupyter, automatically renders
form5  # displays HTML
```

### DataFrame Export
```python
# All transactions with metadata
df = form5.to_dataframe(detailed=True)

# Summary row
df_summary = form5.to_dataframe(detailed=False)
```

## Best Practices

### Check for Transactions
```python
summary = form5.get_ownership_summary()

if not summary.transactions:
    print("Form 5 filed with no transactions")
    # This can happen - insider may file "nothing to report"
```

### Identify Late Filings
```python
# Form 5 may include late Form 4 transactions
# Check the transaction dates vs filing date
for trans in summary.transactions:
    # Transaction codes like 'P', 'S' on Form 5 may indicate late filings
    if trans.code in ['P', 'S']:
        print(f"Possible late filing: {trans.display_name}")
```

### Compare with Form 4
```python
# Get both Form 4 and Form 5 for complete picture
company = Company("AAPL")

form4_filings = company.get_filings(form="4")
form5_filings = company.get_filings(form="5")

# Form 5 supplements Form 4 data
```

## Common Use Cases

### Find Gift Transactions
```python
from edgar import get_filings

# Form 5 often contains gift transactions
filings = get_filings(form="5", filing_date="2024-01-01:")

for filing in filings:
    form5 = filing.obj()
    summary = form5.get_ownership_summary()

    gifts = [t for t in summary.transactions if t.code == 'G']
    if gifts:
        print(f"{form5.insider_name} @ {form5.issuer.name}")
        for gift in gifts:
            print(f"  Gift: {gift.shares_numeric:,} shares")
```

### Identify Small Acquisitions
```python
# Small acquisitions often reported on Form 5
for filing in filings:
    form5 = filing.obj()
    summary = form5.get_ownership_summary()

    # Look for small-value transactions
    small_acq = [t for t in summary.transactions
                 if t.transaction_type == "purchase"
                 and (t.value_numeric or 0) < 10000]

    if small_acq:
        print(f"Small acquisitions by {form5.insider_name}")
```

### Year-End Ownership Analysis
```python
company = Company("AAPL")
form5_filings = company.get_filings(form="5")

# Analyze year-over-year changes
for filing in form5_filings:
    form5 = filing.obj()
    summary = form5.get_ownership_summary()

    print(f"Fiscal Year: {form5.reporting_period}")
    print(f"  Insider: {form5.insider_name}")
    print(f"  Net Change: {summary.net_change:,}")
    print(f"  Remaining: {summary.remaining_shares:,}")
```

## Troubleshooting

### No transactions found

Form 5 may be filed with no transactions to report:
```python
summary = form5.get_ownership_summary()
if not summary.transactions:
    # This is valid - filing confirms no reportable transactions
    print("No exempt transactions to report for fiscal year")
```

### Form 5 not filed

Not all insiders file Form 5:
```python
# Insider may check "no Form 5 required" on Form 4
# This indicates all transactions were already reported
```

### Missing price information

Form 5 transactions often lack prices (gifts, etc.):
```python
for trans in summary.transactions:
    if trans.price_numeric:
        print(f"Price: ${trans.price_numeric}")
    else:
        print(f"No price ({trans.code} transaction)")
```

## Agent Implementation Guide

### Step 1: Get Form 5 Filings
```python
from edgar import Company

company = Company("TICKER_OR_CIK")
filings = company.get_filings(form="5")
```

### Step 2: Parse and Analyze
```python
for filing in filings:
    form5 = filing.obj()
    summary = form5.get_ownership_summary()

    # Same analysis as Form 4
    print(f"Activity: {summary.primary_activity}")
```

### Step 3: Combine with Form 4
```python
# For complete ownership picture, combine Form 4 and Form 5
form4_filings = company.get_filings(form="4")
form5_filings = company.get_filings(form="5")

all_ownership = list(form4_filings) + list(form5_filings)
```

### Key Points for Agents

1. **Same interface as Form 4** - Uses TransactionSummary
2. **Annual filing** - Filed within 45 days of fiscal year end
3. **Exempt transactions** - Includes gifts, small acquisitions
4. **Late filings** - May include transactions that should have been on Form 4
5. **No transactions** - Some Form 5s report nothing

## Related Classes

- **Form3** - Initial beneficial ownership statement
- **Form4** - Transaction report (primary)
- **Ownership** - Base class for all ownership forms
- **TransactionSummary** - Transaction metrics
- **TransactionActivity** - Individual transaction details

## See Also

- [Form3.md](Form3.md) - Initial ownership documentation
- [Form4.md](Form4.md) - Form 4 documentation
- [TransactionSummary.md](TransactionSummary.md) - Transaction summary details
