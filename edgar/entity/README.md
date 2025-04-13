# EdgarTools Entity Package

The `edgar.entity` package provides a clean, intuitive API for working with SEC entities like companies and funds.

## Key Features

- **Hierarchical Design**: Clear class structure that matches the domain model
- **Specialized Classes**: Classes tailored for specific entity types
- **Type Annotations**: Strong typing for better IDE support and validation
- **Factory Functions**: Convenient creation methods for common use cases

## Class Hierarchy

- `SecFiler` (abstract base class)
  - `Entity` (concrete class for any SEC filer)
    - `Company` (specialized for public companies)
    - `Fund` (specialized for investment funds)
      - `FundClass` (for specific fund share classes)

## Usage Examples

### Working with Companies

```python
from edgar.entity import Company

# Create a company by ticker
apple = Company("AAPL")

# Get basic information
print(f"Name: {apple.data.name}")
print(f"CIK: {apple.cik}")
print(f"Ticker: {apple.get_ticker()}")

# Get financial statements
financials = apple.get_financials()

# Get latest 10-K and 10-Q
latest_10k = apple.latest_tenk
latest_10q = apple.latest_tenq

# Get and filter filings
filings = apple.get_filings(form=["10-K", "10-Q"], filing_date="2020-01-01:")
for filing in filings:
    print(f"{filing.form} filed on {filing.filing_date}")
```

### Working with Generic Entities

```python
from edgar.entity import Entity

# Create an entity by CIK
entity = Entity("0000320193")

# Get entity type
if entity.data.is_company:
    print(f"{entity.data.name} is a company")
elif entity.data.is_individual:
    print(f"{entity.data.name} is an individual")

# Get the latest filings
latest = entity.get_filings().latest(5)
```

### Using Factory Functions

```python
from edgar.entity import get_entity, get_company, get_fund

# Get any entity (company, individual, fund, etc.)
entity = get_entity("0000320193")

# Get specifically a company
company = get_company("AAPL")

# Get a fund or fund class
fund_or_class = get_fund("KINCX")
```

## API Reference

See the full API documentation for details on classes, methods, and parameters.