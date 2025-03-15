# Edgartools


# Getting Started

Import the module and most useful functions with:
```python
from edgar import *
```

To make requests to the SEC, you need to set your identity with:
```python
set_identity("user@domain.com")
```

## Get a Company 

### Get a company by ticker symbol

```python
company = Company("AAPL")
```

### Get a company by CIK

```python
company = Company("0000320193")
# OR
company = Company(320193)
```

### Get company filings

To get all filings for a company:
```python
filings = company.get_filings()
```

### Get company filings by form type

To get all 10-K filings for a company:
```python
filings = company.get_filings(form="10-K")
```