# TransactionSummary Class Documentation

## Overview

The `TransactionSummary` dataclass provides a rich, computed summary of transactions from Form 4 and Form 5 filings. It extends `OwnershipSummary` with transaction-specific analytics including net share changes, total values, and activity classification.

**Key Features:**
- Computed `net_change` and `net_value` properties
- Automatic `primary_activity` classification
- DataFrame export with detailed or summary modes
- Rich terminal display with formatted tables
- Access to individual `TransactionActivity` objects

## Quick Start

Get a TransactionSummary from any Form 4 or Form 5:

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="4")[0]
form4 = filing.obj()

# Get the transaction summary
summary = form4.get_ownership_summary()

# Access computed properties
print(f"Net Change: {summary.net_change:,} shares")
print(f"Net Value: ${summary.net_value:,.2f}")
print(f"Activity: {summary.primary_activity}")
```

## Computed Properties

TransactionSummary provides several computed properties for quick analysis:

### net_change
Calculates total shares purchased minus shares sold:

```python
summary = form4.get_ownership_summary()
change = summary.net_change  # int

if change > 0:
    print(f"Net acquisition of {change:,} shares")
elif change < 0:
    print(f"Net disposition of {abs(change):,} shares")
else:
    print("No net change in position")
```

### net_value
Calculates total purchase value minus sale value:

```python
value = summary.net_value  # float

if value > 0:
    print(f"Net investment: ${value:,.2f}")
elif value < 0:
    print(f"Net proceeds: ${abs(value):,.2f}")
```

### primary_activity
Classifies the overall transaction activity:

```python
activity = summary.primary_activity  # str

# Possible values:
# - "Purchase" - Only purchases
# - "Sale" - Only sales
# - "Mixed Transactions" - Both purchases and sales
# - "Tax Withholding" - Tax-related dispositions
# - "Grant/Award" - Stock grants or awards
# - "Option Exercise" - Option exercises
# - "Conversion" - Security conversions
# - "DERIVATIVE ACQUISITION" - Derivative-only purchases
# - "DERIVATIVE DISPOSITION" - Derivative-only sales
# - "DERIVATIVE TRANSACTIONS" - Mixed derivative activity
# - "No Transactions" - No transactions found
```

### transaction_types
Get unique transaction types in the filing:

```python
types = summary.transaction_types  # List[str]

# Example output: ['purchase', 'sale', 'exercise']
for t in types:
    print(f"Contains {t} transactions")
```

### Transaction Checks

```python
# Check transaction composition
summary.has_derivatives        # True if any derivative transactions
summary.has_only_derivatives   # True if ONLY derivative transactions
summary.has_non_derivatives    # True if common stock transactions
```

## DataFrame Export

TransactionSummary provides flexible DataFrame export:

### Detailed Mode (default)
One row per transaction with all details:

```python
df = summary.to_dataframe(detailed=True)

# Columns include:
# - Transaction Type, Code, Description
# - Shares, Price, Value
# - Date, Form, Issuer, Ticker, Insider, Position
# - Remaining Shares
```

### Summary Mode
Single row with aggregated metrics:

```python
df = summary.to_dataframe(detailed=False)
# Or use the alias:
df = summary.to_summary_dataframe()

# Columns include:
# - Date, Form, Issuer, Ticker, Insider, Position
# - Transaction Count, Net Change, Net Value
# - Remaining Shares, Primary Activity
# - Per-type counts and values (Purchase Count, Sale Shares, etc.)
```

### Control Metadata Columns

```python
# Include filing metadata (issuer, insider, etc.)
df = summary.to_dataframe(include_metadata=True)

# Exclude metadata for cleaner transaction data
df = summary.to_dataframe(include_metadata=False)
```

## Accessing Individual Transactions

Each transaction is a `TransactionActivity` object:

```python
for trans in summary.transactions:
    print(f"Type: {trans.transaction_type}")
    print(f"Code: {trans.code} ({trans.code_description})")
    print(f"Shares: {trans.shares_numeric:,}")
    print(f"Price: ${trans.price_numeric:.2f}")
    print(f"Value: ${trans.value_numeric:,.2f}")
    print(f"Display: {trans.display_name}")
    print("---")
```

### TransactionActivity Properties

| Property | Type | Description |
|----------|------|-------------|
| `transaction_type` | str | "purchase", "sale", "exercise", etc. |
| `code` | str | SEC transaction code (P, S, M, etc.) |
| `shares` | Any | Raw shares value |
| `shares_numeric` | Optional[float] | Numeric shares (handles footnotes) |
| `value` | Any | Raw transaction value |
| `value_numeric` | Optional[float] | Numeric value |
| `price_per_share` | Any | Raw price |
| `price_numeric` | Optional[float] | Numeric price |
| `security_type` | str | "non-derivative" or "derivative" |
| `security_title` | str | Security name |
| `code_description` | str | Human-readable code description |
| `display_name` | str | Formatted display name |
| `is_derivative` | bool | True if derivative transaction |
| `style` | str | Rich text style for display |

## Rich Terminal Display

TransactionSummary renders beautifully in the terminal:

```python
# Print the summary
print(summary)

# Or use rich directly
from rich import print as rprint
rprint(summary)
```

The display includes:
- Header with insider info, position, company, date
- Transaction tables (non-derivative and derivative)
- Summary totals for purchases and sales
- Color-coded transaction types

## Properties Reference

### Inherited from OwnershipSummary

| Property | Type | Description |
|----------|------|-------------|
| `reporting_date` | str/date | Date of report |
| `issuer_name` | str | Company name |
| `issuer_ticker` | str | Ticker symbol |
| `insider_name` | str | Reporting insider |
| `position` | str | Insider's position |
| `form_type` | str | "4" or "5" |
| `remarks` | str | Filing remarks |
| `issuer` | str | Formatted issuer (computed) |

### TransactionSummary-Specific

| Property | Type | Description |
|----------|------|-------------|
| `transactions` | List[TransactionActivity] | All transactions |
| `remaining_shares` | Optional[int] | Shares after transactions |
| `has_derivative_transactions` | bool | Has derivative transactions |
| `transaction_types` | List[str] | Unique transaction types |
| `has_only_derivatives` | bool | Only derivative transactions |
| `has_non_derivatives` | bool | Has common stock transactions |
| `net_change` | int | Net shares change |
| `net_value` | float | Net dollar value |
| `primary_activity` | str | Activity classification |

## Common Use Cases

### Screen for Significant Purchases

```python
from edgar import get_filings

filings = get_filings(form="4", filing_date="2024-12-01:")

significant = []
for filing in filings:
    form4 = filing.obj()
    summary = form4.get_ownership_summary()

    if summary.net_change > 10000 and summary.net_value > 100000:
        significant.append({
            'insider': summary.insider_name,
            'company': summary.issuer,
            'shares': summary.net_change,
            'value': summary.net_value
        })

# Sort by value
significant.sort(key=lambda x: x['value'], reverse=True)
```

### Analyze Transaction Patterns

```python
from collections import Counter

company = Company("TSLA")
filings = company.get_filings(form="4")

activity_counts = Counter()
for filing in filings:
    summary = filing.obj().get_ownership_summary()
    activity_counts[summary.primary_activity] += 1

print("Transaction patterns:")
for activity, count in activity_counts.most_common():
    print(f"  {activity}: {count}")
```

### Calculate Average Price

```python
summary = form4.get_ownership_summary()

# Get average purchase price
purchases = [t for t in summary.transactions
             if t.transaction_type == "purchase" and t.price_numeric]

if purchases:
    total_value = sum(t.value_numeric or 0 for t in purchases)
    total_shares = sum(t.shares_numeric or 0 for t in purchases)
    avg_price = total_value / total_shares if total_shares else 0
    print(f"Average purchase price: ${avg_price:.2f}")
```

### Aggregate Multiple Filings

```python
import pandas as pd

company = Company("AAPL")
filings = company.get_filings(form="4").head(20)

all_dfs = []
for filing in filings:
    summary = filing.obj().get_ownership_summary()
    df = summary.to_dataframe(detailed=True)
    df['filing_date'] = filing.filing_date
    all_dfs.append(df)

combined = pd.concat(all_dfs, ignore_index=True)

# Analyze by insider
by_insider = combined.groupby('Insider').agg({
    'Shares': 'sum',
    'Value': 'sum'
})
```

## Best Practices

### Handle Empty Transactions

```python
summary = form4.get_ownership_summary()

if not summary.transactions:
    print("No transactions in this filing")
else:
    print(f"{len(summary.transactions)} transactions found")
```

### Use Numeric Properties

```python
# Good - handles footnotes and None values
for trans in summary.transactions:
    shares = trans.shares_numeric or 0
    price = trans.price_numeric or 0

# Less ideal - may fail on footnotes
# shares = int(trans.shares)  # Could fail
```

### Check Transaction Types Before Calculations

```python
# Only calculate net_value if there are market transactions
if summary.has_non_derivatives:
    print(f"Net value: ${summary.net_value:,.2f}")
else:
    print("No common stock transactions (derivatives only)")
```

## Troubleshooting

### net_change is 0 but transactions exist

The filing may only contain non-P/S transactions:
```python
# Check what transaction types exist
print(summary.transaction_types)
# e.g., ['exercise', 'tax'] - no purchases or sales
```

### net_value is 0

Some transactions don't have prices:
```python
# Check for transactions with prices
for trans in summary.transactions:
    if trans.price_numeric is None:
        print(f"{trans.code}: No price (likely grant, exercise, etc.)")
```

### remaining_shares is None

Not all filings report remaining shares:
```python
if summary.remaining_shares is not None:
    print(f"Remaining: {summary.remaining_shares:,}")
else:
    print("Remaining shares not reported")
```

## Agent Implementation Guide

### Step 1: Get Summary from Form 4/5
```python
form4 = filing.obj()
summary = form4.get_ownership_summary()
```

### Step 2: Use Computed Properties for Quick Analysis
```python
# Quick screening
if summary.primary_activity == "Purchase" and summary.net_value > 50000:
    # Flag as significant purchase
    pass
```

### Step 3: Use DataFrame for Detailed Analysis
```python
# For pandas operations
df = summary.to_dataframe(detailed=True)
```

### Key Points for Agents

1. **net_change** - Net shares (positive = buy, negative = sell)
2. **net_value** - Net dollar amount
3. **primary_activity** - Quick activity classification
4. **transactions** - Access individual transactions when needed
5. **to_dataframe()** - For bulk processing and pandas operations

## Related Classes

- **OwnershipSummary** - Base summary class
- **InitialOwnershipSummary** - Summary for Form 3
- **TransactionActivity** - Individual transaction details
- **Form4** - Form 4 ownership document
- **Form5** - Form 5 ownership document

## See Also

- [Form4.md](Form4.md) - Form 4 documentation
- [Form5.md](Form5.md) - Form 5 documentation
- [OwnershipSummary.md](OwnershipSummary.md) - Base summary class