# EdgarTools Entity Package Migration Guide

## Overview

EdgarTools has introduced a new `edgar.entity` package that provides a cleaner, more intuitive API for working with SEC entities. This guide explains how to migrate from the old API to the new one.

## Key Benefits

The new entity package offers several advantages:

1. **Clearer class hierarchy**: A proper inheritance hierarchy with specialized classes for different entity types
2. **Improved type annotations**: Better IDE support and type checking
3. **More intuitive interfaces**: Specialized methods for each entity type
4. **Better documentation**: Clear docstrings and examples

## Migration Path

### Step 1: Update Imports

Change your imports from:

```python
from edgar.entities import Entity, Company, get_entity, get_company
```

To:

```python
from edgar.entity import Entity, Company, get_entity, get_company
```

### Step 2: Use Specialized Classes

Take advantage of the specialized classes for different entity types:

```python
# Before
company = get_entity("AAPL")
financials = company.latest("10-K").obj().financials

# After
company = Company("AAPL")
financials = company.get_financials()
```

### Step 3: Use Class-Specific Methods

The specialized classes provide convenient methods for common tasks:

```python
# Before
entity = get_entity("KINCX")
# Need to know how to get fund information...

# After
fund = get_fund("KINCX")
if isinstance(fund, FundClass):
    # It's a fund class
    print(f"Fund: {fund.fund.name}, Class: {fund.name}")
    portfolio = fund.fund.get_portfolio()
else:
    # It's a fund
    print(f"Fund: {fund.name}")
    portfolio = fund.get_portfolio()
```

## Backward Compatibility

For backward compatibility, the following elements are preserved:

1. Factory functions: `get_entity()`, `get_company()`, etc.
2. Method signatures: All existing methods maintain their signatures
3. Data access: `entity.data` still provides access to the underlying data

## Examples

### Working with Companies

```python
from edgar.entity import Company

# Create a company by ticker
apple = Company("AAPL")

# Get company information
print(f"Name: {apple.data.name}")
print(f"Industry: {apple.data.sic_description}")

# Get financial statements
financials = apple.get_financials()

# Get filings
tenks = apple.get_filings(form="10-K")
latest_10q = apple.get_filings(form="10-Q").latest()
```

### Working with Entities (Generic)

```python
from edgar.entity import Entity

# Create an entity by CIK
entity = Entity("0000320193")

# Get entity information
print(f"Name: {entity.data.name}")
print(f"Is company: {entity.data.is_company}")

# Get filings
filings = entity.get_filings(form="8-K", filing_date="2023-01-01:2023-12-31")
```

### Working with Funds

```python
from edgar.entity import get_fund

# Get a fund by ticker
fund = get_fund("KINCX")

# Check if it's a fund class
if hasattr(fund, 'fund'):
    # It's a fund class
    print(f"Fund: {fund.fund.name}, Class: {fund.name}")
    parent_fund = fund.fund
else:
    # It's a fund
    print(f"Fund: {fund.name}")
    parent_fund = fund

# Get fund classes
classes = parent_fund.get_classes()
```

## Timeline

The new `edgar.entity` package is available now, and the old `edgar.entities` module will be maintained for backward compatibility until the next major release.

We encourage users to migrate to the new package to take advantage of the improved API.