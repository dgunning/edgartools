# OwnershipSummary Class Documentation

## Overview

`OwnershipSummary` is the base dataclass for ownership form summaries. It provides common fields and methods shared by its subclasses:

- **InitialOwnershipSummary** - For Form 3 (initial ownership)
- **TransactionSummary** - For Form 4/5 (transactions)

**Key Features:**
- Common metadata fields (issuer, insider, position, date)
- Base DataFrame export functionality
- Rich display interface
- Consistent API across ownership forms

## Class Hierarchy

```
OwnershipSummary (base)
    ├── InitialOwnershipSummary (Form 3)
    └── TransactionSummary (Form 4/5)
```

## Quick Start

Get the appropriate summary from any ownership form:

```python
from edgar import Company

company = Company("AAPL")

# Form 3 returns InitialOwnershipSummary
form3 = company.get_filings(form="3")[0].obj()
initial_summary = form3.get_ownership_summary()

# Form 4 returns TransactionSummary
form4 = company.get_filings(form="4")[0].obj()
transaction_summary = form4.get_ownership_summary()

# Both have common base properties
print(f"Issuer: {initial_summary.issuer}")
print(f"Issuer: {transaction_summary.issuer}")
```

## Base Properties

All summary classes share these properties:

| Property | Type | Description |
|----------|------|-------------|
| `reporting_date` | str/date | Date of report |
| `issuer_name` | str | Company name |
| `issuer_ticker` | str | Ticker symbol |
| `insider_name` | str | Reporting person's name |
| `position` | str | Insider's position(s) |
| `form_type` | str | "3", "4", or "5" |
| `remarks` | str | Filing remarks |
| `issuer` | str | Formatted as "Name (Ticker)" |

### The issuer Property

```python
# Computed property combining name and ticker
summary.issuer  # Returns "Apple Inc. (AAPL)"
```

## Base Methods

### to_dataframe()

The base implementation provides metadata columns:

```python
df = summary.to_dataframe(include_metadata=True)

# Returns DataFrame with columns:
# - Date
# - Form
# - Issuer
# - Ticker
# - Insider
# - Position
# - Remarks
```

Subclasses extend this with additional columns.

---

# InitialOwnershipSummary

Summary class for Form 3 (Initial Statement of Beneficial Ownership).

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `holdings` | List[SecurityHolding] | All holdings |
| `no_securities` | bool | True if no securities owned |
| `total_shares` | int | Total non-derivative shares |
| `has_derivatives` | bool | True if derivative holdings exist |

## Usage

```python
# Get from Form 3
form3 = filing.obj()
summary = form3.get_ownership_summary()

# Check for no securities
if summary.no_securities:
    print("Insider owns no securities")
else:
    print(f"Total shares: {summary.total_shares:,}")
```

## Accessing Holdings

```python
# Iterate over all holdings
for holding in summary.holdings:
    print(f"{holding.security_title}: {holding.shares}")

# Filter by type
stocks = [h for h in summary.holdings if not h.is_derivative]
derivatives = [h for h in summary.holdings if h.is_derivative]
```

## DataFrame Export

### Detailed Mode
Returns one row per holding:

```python
df = summary.to_dataframe(include_metadata=True)

# Columns:
# - Security Type, Security Title, Shares
# - Ownership Type, Ownership Nature
# - For derivatives: Underlying Security, Exercise Price, etc.
# - Plus metadata columns if include_metadata=True
```

### Summary Mode
Returns single row with aggregates:

```python
df = summary.to_summary_dataframe()

# Columns:
# - Date, Form, Issuer, Ticker, Insider, Position
# - Total Shares, Has Derivatives, Holdings count
# - Common Stock Holdings, Derivative Holdings counts
```

## SecurityHolding Details

Each holding in the list is a `SecurityHolding` dataclass:

```python
@dataclass
class SecurityHolding:
    security_type: str       # "non-derivative" or "derivative"
    security_title: str      # Security name
    shares: int              # Number of shares
    direct_ownership: bool   # True if directly owned
    ownership_nature: str    # Nature of indirect ownership
    underlying_security: str # For derivatives
    underlying_shares: int   # For derivatives
    exercise_price: Optional[float]
    exercise_date: str
    expiration_date: str
```

### SecurityHolding Properties

```python
holding.is_derivative        # True if derivative security
holding.ownership_description  # "Direct" or "Indirect (reason)"
```

## Rich Display

```python
# Terminal display
print(summary)

# Shows:
# - Header with insider info
# - Common Stock Holdings table
# - Derivative Securities table
# - Remarks if present
```

---

# TransactionSummary

Summary class for Form 4/5 (Changes in Beneficial Ownership).

See [TransactionSummary.md](TransactionSummary.md) for complete documentation.

## Quick Reference

```python
summary = form4.get_ownership_summary()

# Key properties
summary.net_change           # int - Net shares bought/sold
summary.net_value            # float - Net dollar value
summary.primary_activity     # str - "Purchase", "Sale", etc.
summary.transactions         # List[TransactionActivity]
summary.remaining_shares     # Optional[int]
summary.transaction_types    # List[str] - Unique types
```

---

# Common Patterns

## Type Checking

```python
from edgar.ownership import InitialOwnershipSummary, TransactionSummary

summary = form.get_ownership_summary()

if isinstance(summary, InitialOwnershipSummary):
    print(f"Form 3 with {len(summary.holdings)} holdings")
elif isinstance(summary, TransactionSummary):
    print(f"Form 4/5 with {len(summary.transactions)} transactions")
```

## Unified Processing

```python
def process_filing(filing):
    form = filing.obj()
    summary = form.get_ownership_summary()

    # Common fields work for all forms
    print(f"Insider: {summary.insider_name}")
    print(f"Company: {summary.issuer}")
    print(f"Form: {summary.form_type}")

    # Type-specific processing
    if isinstance(summary, InitialOwnershipSummary):
        print(f"Initial shares: {summary.total_shares:,}")
    else:
        print(f"Net change: {summary.net_change:,}")
```

## DataFrame Aggregation

```python
import pandas as pd

all_summaries = []
for filing in filings:
    form = filing.obj()
    summary = form.get_ownership_summary()

    if hasattr(summary, 'to_summary_dataframe'):
        df = summary.to_summary_dataframe()
    else:
        df = summary.to_dataframe(include_metadata=True)

    all_summaries.append(df)

combined = pd.concat(all_summaries, ignore_index=True)
```

## Best Practices

### Always Use get_ownership_summary()

```python
# Good - uses the summary interface
summary = form.get_ownership_summary()
shares = summary.total_shares if hasattr(summary, 'total_shares') else summary.net_change

# Less ideal - accessing raw tables
df = form.non_derivative_table.holdings.data
```

### Check for Empty/No Securities

```python
# Form 3
if summary.no_securities:
    return  # No holdings to process

# Form 4/5
if not summary.transactions:
    return  # No transactions to process
```

### Use Subclass-Specific Methods

```python
# For Form 3 - use summary_dataframe for aggregated view
if isinstance(summary, InitialOwnershipSummary):
    df = summary.to_summary_dataframe()

# For Form 4/5 - use detailed=False for aggregated view
if isinstance(summary, TransactionSummary):
    df = summary.to_dataframe(detailed=False)
```

## Agent Implementation Guide

### Step 1: Get Summary from Any Form

```python
form = filing.obj()  # Works for Form 3, 4, or 5
summary = form.get_ownership_summary()
```

### Step 2: Use Common Properties

```python
# These work for all summary types
print(f"Insider: {summary.insider_name}")
print(f"Issuer: {summary.issuer}")
print(f"Date: {summary.reporting_date}")
```

### Step 3: Handle Type-Specific Logic

```python
if summary.form_type == "3":
    # InitialOwnershipSummary
    print(f"Holdings: {len(summary.holdings)}")
else:
    # TransactionSummary (Form 4 or 5)
    print(f"Net Change: {summary.net_change}")
```

### Key Points for Agents

1. **get_ownership_summary()** - Returns the appropriate subclass
2. **Common properties** - issuer, insider_name, position work everywhere
3. **Type-specific properties** - Check form_type or use isinstance()
4. **to_dataframe()** - Available on all summary types
5. **Rich display** - print(summary) works everywhere

## Related Classes

- **Ownership** - Base class for ownership forms
- **Form3, Form4, Form5** - Specific form classes
- **TransactionActivity** - Individual transaction details
- **SecurityHolding** - Individual holding details

## See Also

- [Form3.md](Form3.md) - Form 3 documentation
- [Form4.md](Form4.md) - Form 4 documentation
- [Form5.md](Form5.md) - Form 5 documentation
- [TransactionSummary.md](TransactionSummary.md) - Transaction summary details
