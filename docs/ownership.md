# Ownership Documents

Ownership documents are SEC forms that contain information about ownership of securities.

### Ownership Forms

|  Form | Description                                                       | 
|------:|:------------------------------------------------------------------|
| **3** | Initial statement of beneficial ownership of securities           |
| **4** | Statement of changes of beneficial ownership of securities        | 
| **5** | Annual statement of changes in beneficial ownership of securities |

The module `edgar.ownership` module parses XML into an `OwnershipDocument` instance, 
containing data about transactions and holdings.

## Getting Ownership Documents


```python
from edgar import Company
from edgar.ownership import OwnershipDocument

# Get Snowflake
company = Company.for_ticker("SNOW")

# Get Form 4 filings for Snowflake
filings = company.get_filings(form="4")

# Get the first filing
filing = filings[0]

# Get the filing xml
xml = filing.xml()

# Now get the OwnershipDocument
ownership = OwnershipDocument.from_xml(xml)
```

## Derivative Table

This contains data on derivative holdings and transactions.
### Derivative Holdings
To access derivative transactions use `ownership.derivatives.holdings`

### Derivative Transactions
To access derivative transactions use `ownership.derivatives.transactions`

You can access individual transaction using the `[]` notation.
```python
ownership.derivatives.transactions[0]
```

![Derivative Transaction](https://raw.githubusercontent.com/dgunning/edgartools/main/derivative_transaction.png)

## Non Derivative Table
This contains data on non-derivative holdings and transactions.

### Non Derivative Holdings
To access derivative holdings use `ownership.non_derivatives.holdings`

You can access individual holdings using the `[]` notation.

```python
ownership.non_derivatives.holdings[0]
```

### Non Derivative Transactions
To access derivative transactions use `ownership.non_derivatives.transactions`

You can access individual transactions using the `[]` notation.

```python
ownership.non_derivatives.transactions[0]
```