# Ownership API

## Overview
The Ownership API provides access to insider transaction data reported in Forms 3, 4, and 5 filings with the SEC.

## Key Classes
- `Ownership` - Base class for Forms 3, 4, and 5 insider filings
- `Form3` - Initial beneficial ownership filings
- `Form4` - Changes in beneficial ownership filings
- `Form5` - Annual changes in beneficial ownership filings
- `SecurityHolding` - Represents a security holding in Form 3
- `TransactionActivity` - Represents a specific transaction activity in Forms 4 and 5

## Core Functionality
- Access insider ownership and transaction data
- View initial holdings and ownership changes
- Convert insider data to structured formats
- Generate ownership summaries

## Common Patterns

### Finding Ownership Filings
```python
# Get all recent insider filings
insider_filings = get_filings(form=["3", "4", "5"])

# Get insider filings for a specific company
company = Company("VRTX")
company_insider_filings = company.get_filings(form=[3, 4, 5])

# Get specifically Form 4 filings
form4_filings = company.get_filings(form=4)
```

### Converting Filings to Ownership Objects
```python
# Convert a filing to the appropriate Form object
filing = company_insider_filings[0]
ownership = filing.obj()  # Returns Form3, Form4, or Form5 depending on filing type

# Access basic information
owner_name = ownership.reporting_owner.name
owner_title = ownership.reporting_owner.title
filing_type = ownership.form_type  # "3", "4", or "5"
```

### Working with Form 3 (Initial Ownership)
```python
# Get Form 3 data
form3 = filing.obj()  # Assuming filing is a Form 3

# Get ownership summary
initial_ownership = form3.get_ownership_summary()

# Get details
total_shares = initial_ownership.total_shares
has_derivatives = initial_ownership.has_derivatives
has_no_securities = initial_ownership.no_securities

# Access individual holdings
for holding in initial_ownership.holdings:
    security_title = holding.security_title
    shares = holding.shares
    ownership_type = holding.ownership_description  # "Direct" or "Indirect"
    is_derivative = holding.is_derivative
```

### Working with Form 4 (Ownership Changes)
```python
# Get Form 4 data
form4 = filing.obj()  # Assuming filing is a Form 4

# Get transactions
for transaction in form4.transactions:
    security = transaction.security_title
    date = transaction.transaction_date
    code = transaction.transaction_code  # "P" for purchase, "S" for sale
    shares = transaction.shares
    price = transaction.price_per_share
    value = transaction.get_value()  # shares × price

# Get ownership summary
transaction_summary = form4.get_ownership_summary()
```

### Converting to DataFrame
```python
# Convert to DataFrame with all transaction details
df = form4.to_dataframe()

# Get summary view only
summary_df = form4.to_dataframe(detailed=False)

# Exclude filing metadata
clean_df = form4.to_dataframe(include_metadata=False)
```

### Aggregating Insider Activity
```python
# Aggregate all insider transactions for a company
all_transactions = []
for filing in company_insider_filings:
    ownership = filing.obj()
    if ownership and hasattr(ownership, 'transactions'):
        for transaction in ownership.transactions:
            all_transactions.append({
                "date": transaction.transaction_date,
                "insider": ownership.reporting_owner.name,
                "title": ownership.reporting_owner.title,
                "action": "Buy" if transaction.transaction_code == "P" else "Sell",
                "shares": transaction.shares,
                "price": transaction.price_per_share,
                "value": transaction.get_value()
            })

# Convert to DataFrame
import pandas as pd
transactions_df = pd.DataFrame(all_transactions)
```

## Transaction Codes
- "P": Purchase
- "S": Sale
- "A": Grant/award
- "D": Disposition to issuer
- "M": Exercise of derivative
- "C": Conversion
- "G": Gift

## Relevant User Journeys
- Insider Trading Analysis Journey
- Regulatory Filing Monitoring Journey