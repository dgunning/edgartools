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

- get a form **3**, **4**, or **5** filing
- get the xml document
- call `OwnershipDocument.from_xml()`

```python
from edgar import CompanyData
from edgar.ownership import Ownership

# Get Snowflake
company = CompanyData.for_ticker("SNOW")

# Get Form 4 filings for Snowflake
filings = company.get_filings(form="4")

# Get the first filing
filing = filings[0]

# Get the filing xml
xml = filing.xml()

# Now get the OwnershipDocument
ownership = Ownership.from_xml(xml)
```

## Derivative Table

This contains data on derivative holdings and transactions. To access it call
`ownership_document.derivatives`.

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
This contains data on non-derivative holdings and transactions. To access it call
`ownership_document.non_
derivatives`.

### Non Derivative Holdings
To access derivative holdings use `ownership.non_derivatives.holdings`

You can access individual holdings using the `[]` notation.

```python
holding = ownership.non_derivatives.holdings[0]
holding
```
![Non Derivative Holding](https://raw.githubusercontent.com/dgunning/edgartools/main/non_derivative_holding.png)


### Non Derivative Transactions
To access derivative transactions use `ownership.non_derivatives.transactions`

You can access individual transactions using the `[]` notation.

```python
transaction = ownership.non_derivatives.transactions[0]
transaction
```