# Form3 Class Documentation

## Overview

The `Form3` class represents SEC Form 3 - the Initial Statement of Beneficial Ownership. Form 3 filings are required within 10 days of becoming a corporate insider (officer, director, or 10%+ shareholder). Unlike Form 4, Form 3 reports current holdings rather than transactions.

**Key Features:**
- Parse and access initial ownership positions
- View both common stock and derivative holdings
- Track direct and indirect ownership
- Access computed summaries of total shares
- See derivative details (options, warrants, etc.)

## Quick Start

Get started with Form 3 in 3 lines:

```python
from edgar import Company

# Get a company's Form 3 filings
company = Company("AAPL")
filings = company.get_filings(form="3")
filing = filings[0]

# Parse into Form3 object
form3 = filing.obj()

# Access ownership information
print(f"Insider: {form3.insider_name}")
print(f"Position: {form3.position}")
print(f"Issuer: {form3.issuer.name}")

# Get ownership summary
summary = form3.get_ownership_summary()
print(f"Total Shares: {summary.total_shares:,}")
print(f"Has Derivatives: {summary.has_derivatives}")
```

## Form 3 vs Form 4

| Aspect | Form 3 | Form 4 |
|--------|--------|--------|
| Purpose | Initial ownership statement | Transaction report |
| Content | Current holdings | Changes in holdings |
| Timing | Within 10 days of becoming insider | Within 2 business days of transaction |
| Summary Class | InitialOwnershipSummary | TransactionSummary |
| Key Data | Holdings list | Transactions list |

## Common Actions

### Access Form 3 from Filing
```python
from edgar import Company

company = Company("MSFT")
filings = company.get_filings(form="3")
filing = filings[0]

# Parse into Form3 object
form3 = filing.obj()
```

### Access Issuer Information
```python
issuer = form3.issuer
print(issuer.name)     # Company name
print(issuer.ticker)   # Trading symbol
print(issuer.cik)      # CIK number
```

### Access Insider Information
```python
print(form3.insider_name)  # Insider's name
print(form3.position)      # Position(s)

# Get detailed owner info
for owner in form3.reporting_owners.owners:
    print(f"Name: {owner.name}")
    print(f"Is Director: {owner.relationship.is_director}")
    print(f"Is Officer: {owner.relationship.is_officer}")
    if owner.relationship.officer_title:
        print(f"Title: {owner.relationship.officer_title}")
```

### Access Holdings
```python
# Get all holdings as a list
holdings = form3.extract_form3_holdings()

for holding in holdings:
    print(f"Security: {holding.security_title}")
    print(f"Shares: {holding.shares}")
    print(f"Type: {holding.security_type}")
    print(f"Ownership: {holding.ownership_description}")
    print("---")
```

### Get Ownership Summary
```python
# Get InitialOwnershipSummary with computed properties
summary = form3.get_ownership_summary()

# Key metrics
print(f"Total Shares: {summary.total_shares:,}")
print(f"Has Derivatives: {summary.has_derivatives}")
print(f"Holdings Count: {len(summary.holdings)}")

# Check for empty holdings
if summary.no_securities:
    print("No securities beneficially owned")
```

### Convert to DataFrame
```python
# Get detailed holdings as DataFrame
df = form3.to_dataframe(detailed=True)

# Get summary as single row
df_summary = form3.to_dataframe(detailed=False)
```

## Properties and Attributes

### Core Information
```python
form3.form                     # Form type ("3")
form3.reporting_period         # Date of becoming insider
form3.insider_name             # Insider's name
form3.position                 # Insider's position(s)
form3.remarks                  # Any remarks
form3.no_securities            # True if no securities owned
```

### Holdings Tables
```python
form3.non_derivative_table     # NonDerivativeTable (common stock)
form3.derivative_table         # DerivativeTable (options, etc.)
```

### Other Attributes
```python
form3.issuer                   # Issuer object
form3.reporting_owners         # ReportingOwners object
form3.footnotes                # Footnotes object
form3.signatures               # OwnerSignatures object
```

## Working with InitialOwnershipSummary

When you call `form3.get_ownership_summary()`, you get an `InitialOwnershipSummary`:

```python
summary = form3.get_ownership_summary()

# Key properties
summary.total_shares           # Total non-derivative shares
summary.has_derivatives        # True if derivative holdings exist
summary.no_securities          # True if no securities owned
summary.holdings               # List[SecurityHolding]
```

### Accessing Holdings

```python
for holding in summary.holdings:
    print(f"Security: {holding.security_title}")
    print(f"Shares: {holding.shares}")
    print(f"Type: {holding.security_type}")
    print(f"Direct: {holding.direct_ownership}")

    if holding.is_derivative:
        print(f"  Underlying: {holding.underlying_security}")
        print(f"  Underlying Shares: {holding.underlying_shares}")
        print(f"  Exercise Price: {holding.exercise_price}")
        print(f"  Expiration: {holding.expiration_date}")
```

See [OwnershipSummary.md](OwnershipSummary.md) for complete documentation.

## SecurityHolding Properties

| Property | Type | Description |
|----------|------|-------------|
| `security_type` | str | "non-derivative" or "derivative" |
| `security_title` | str | Security name |
| `shares` | int | Number of shares |
| `direct_ownership` | bool | True if directly owned |
| `ownership_nature` | str | Nature of indirect ownership |
| `is_derivative` | bool | True if derivative security |
| `ownership_description` | str | "Direct" or "Indirect (reason)" |
| `underlying_security` | str | Underlying for derivatives |
| `underlying_shares` | int | Underlying shares for derivatives |
| `exercise_price` | Optional[float] | Exercise price for derivatives |
| `exercise_date` | str | Exercisable date |
| `expiration_date` | str | Expiration date |

## Finding Form 3 Filings

### By Company
```python
from edgar import Company

company = Company("TSLA")
filings = company.get_filings(form="3")

# Get recent filings
recent = filings.head(10)
```

### By Search
```python
from edgar import get_filings

# All Form 3 filings in a period
filings = get_filings(2024, 1, form="3")

# Filter by date
filings = get_filings(form="3", filing_date="2024-12-01:")
```

## Display and Output

### Rich Terminal Display
```python
# Display formatted output in terminal
print(form3)

# Shows:
# - Insider info and position
# - Common stock holdings table
# - Derivative securities table
```

### HTML Output
```python
# Get HTML representation
html = form3.to_html()

# In Jupyter, automatically renders
form3  # displays HTML
```

### DataFrame Export
```python
# All holdings with metadata
df = form3.to_dataframe(detailed=True, include_metadata=True)

# Summary row
df_summary = form3.to_dataframe(detailed=False)
```

## Best Practices

### Check for No Securities
```python
summary = form3.get_ownership_summary()

if summary.no_securities:
    print("Insider reports no beneficial ownership")
    return

# Process holdings...
```

### Handle Derivative Holdings
```python
summary = form3.get_ownership_summary()

# Separate by type
non_derivative = [h for h in summary.holdings if not h.is_derivative]
derivative = [h for h in summary.holdings if h.is_derivative]

print(f"Common stock positions: {len(non_derivative)}")
print(f"Derivative positions: {len(derivative)}")
```

### Calculate Total Exposure
```python
summary = form3.get_ownership_summary()

# Direct shares
direct_shares = summary.total_shares

# Add derivative underlying shares
derivative_exposure = sum(
    h.underlying_shares for h in summary.holdings
    if h.is_derivative
)

print(f"Direct shares: {direct_shares:,}")
print(f"Derivative exposure: {derivative_exposure:,}")
print(f"Total exposure: {direct_shares + derivative_exposure:,}")
```

## Common Use Cases

### Find New Board Members
```python
from edgar import get_filings

filings = get_filings(form="3", filing_date="2024-12-01:")

new_directors = []
for filing in filings:
    form3 = filing.obj()
    for owner in form3.reporting_owners.owners:
        if owner.relationship.is_director:
            summary = form3.get_ownership_summary()
            new_directors.append({
                'name': owner.name,
                'company': form3.issuer.name,
                'shares': summary.total_shares,
                'date': form3.reporting_period
            })

for d in new_directors[:10]:
    print(f"{d['name']} joined {d['company']} board")
    print(f"  Initial position: {d['shares']:,} shares")
```

### Track New 10% Owners
```python
from edgar import get_filings

filings = get_filings(form="3", filing_date="2024-12-01:")

for filing in filings:
    form3 = filing.obj()
    for owner in form3.reporting_owners.owners:
        if owner.relationship.is_ten_pct_owner:
            summary = form3.get_ownership_summary()
            print(f"New 10%+ owner: {owner.name}")
            print(f"  Company: {form3.issuer.name}")
            print(f"  Shares: {summary.total_shares:,}")
```

### Analyze Executive Stock Grants
```python
from edgar import Company

company = Company("AAPL")
filings = company.get_filings(form="3")

for filing in filings[:5]:
    form3 = filing.obj()
    summary = form3.get_ownership_summary()

    # Check for options/grants
    options = [h for h in summary.holdings if h.is_derivative]

    if options:
        print(f"{form3.insider_name} ({form3.position})")
        for opt in options:
            print(f"  {opt.security_title}: {opt.underlying_shares:,} shares")
            if opt.exercise_price:
                print(f"    Exercise: ${opt.exercise_price}")
```

## Troubleshooting

### no_securities is True

Insider has no beneficial ownership to report:
```python
summary = form3.get_ownership_summary()
if summary.no_securities:
    print("This is valid - insider owns no company securities")
```

### Holdings list is empty

May indicate no_securities or parsing issue:
```python
summary = form3.get_ownership_summary()

if not summary.holdings:
    if summary.no_securities:
        print("No securities - this is expected")
    else:
        # Check raw tables
        print("Non-derivative table:", form3.non_derivative_table)
        print("Derivative table:", form3.derivative_table)
```

### Missing exercise price

Some derivatives don't have fixed exercise prices:
```python
for holding in summary.holdings:
    if holding.is_derivative:
        if holding.exercise_price is not None:
            print(f"Exercise: ${holding.exercise_price}")
        else:
            print("Exercise price not fixed or N/A")
```

## Agent Implementation Guide

### Step 1: Get Form 3 Filings
```python
from edgar import Company

company = Company("TICKER_OR_CIK")
filings = company.get_filings(form="3")
```

### Step 2: Parse and Analyze
```python
for filing in filings:
    form3 = filing.obj()
    summary = form3.get_ownership_summary()

    # Check for holdings
    if summary.no_securities:
        continue

    # Analyze holdings
    print(f"Total shares: {summary.total_shares:,}")
```

### Step 3: Work with Holdings
```python
# Access individual holdings
for holding in summary.holdings:
    # Process each holding
    pass

# Or convert to DataFrame
df = form3.to_dataframe(detailed=True)
```

### Key Points for Agents

1. **Use get_ownership_summary()** - Returns InitialOwnershipSummary
2. **Check no_securities** - Some Form 3s report zero ownership
3. **Separate derivative/non-derivative** - Different data available
4. **total_shares** - Only counts non-derivative holdings
5. **to_dataframe()** - For pandas operations

## Related Classes

- **Form4** - Transaction report
- **Form5** - Annual statement
- **Ownership** - Base class for all ownership forms
- **InitialOwnershipSummary** - Summary for Form 3
- **SecurityHolding** - Individual holding details

## See Also

- [Form4.md](Form4.md) - Form 4 documentation
- [Form5.md](Form5.md) - Form 5 documentation
- [OwnershipSummary.md](OwnershipSummary.md) - Summary base class