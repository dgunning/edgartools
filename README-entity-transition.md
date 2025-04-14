# Entity Module Transition Guide

## Overview

The EdgarTools library is transitioning from using the `edgar.entities` module to a new package structure `edgar.entity`. This change brings several improvements:

1. **Clearer class hierarchy**: The new structure uses proper class inheritance with a base `SecFiler` class.
2. **Specialized classes**: Each entity type (Company, Fund) inherits from the base `Entity` class.
3. **Better organization**: Code is now organized into submodules by functionality.
4. **Improved type hints**: All classes and functions have proper type annotations.

## Timeline

- **Current version**: Both `edgar.entities` and `edgar.entity` are available, but `edgar.entities` is deprecated.
- **Future versions**: `edgar.entities` will be removed in a future version.

## Migration Steps

### Step 1: Update imports

Replace all imports from `edgar.entities` with imports from `edgar.entity`:

```python
# Old
from edgar.entities import (
    Company, 
    CompanyData, 
    find_company
)

# New
from edgar.entity import (
    Company, 
    CompanyData, 
    find_company
)
```

### Step 2: Update code that relies on implementation details

If your code relies on implementation details of the old module, you may need to update it. The core API is mostly unchanged, but some internal details have changed.

### Key differences

- `EntityFacts` is now the primary class (renamed from `CompanyFacts`)
- `EntityFilings` is now the primary class (renamed from `CompanyFilings`)
- `EntityFiling` is now the primary class (renamed from `CompanyFiling`)

These classes are still available with their old names for backward compatibility, but we recommend using the new names in new code.

## Examples

### Basic usage

```python
# Old
from edgar.entities import Company, find_company

# New
from edgar.entity import Company, find_company

# Usage is the same
company = Company("AAPL")
search_results = find_company("Apple")
```

### Using the new class hierarchy

```python
from edgar.entity import SecFiler, Entity, Company, Fund

# Create entities using factory functions
entity = Entity("0000320193")  # Apple via CIK
company = Company("AAPL")      # Apple via ticker
fund = Fund("C123456")         # Fund via identifier

# Check type relationships
isinstance(company, Entity)    # True
isinstance(company, SecFiler)  # True
isinstance(fund, SecFiler)     # True
```

## Full List of Imported Classes and Functions

```python
from edgar.entity import (
    # Core classes
    SecFiler,
    Entity,
    Company,
    Fund,
    FundClass,
    
    # Data classes
    EntityData,
    CompanyData,
    Address,
    
    # Filing classes
    EntityFiling,
    EntityFilings,
    EntityFacts,
    
    # Fact classes
    Fact,
    Concept,
    CompanyConcept,
    
    # Factory functions
    get_entity,
    get_company,
    get_fund,
    public_companies,
    
    # Search functions
    find_company,
    CompanySearchResults,
    CompanySearchIndex,
    
    # Ticker functions
    get_icon_from_ticker,
    get_company_tickers,
    get_ticker_to_cik_lookup,
    get_cik_lookup_data,
    find_cik,
    find_ticker,
    
    # Submission functions
    get_entity_submissions,
    download_entity_submissions_from_sec,
    
    # Fact functions
    get_company_facts,
    get_concept,
    
    # Exceptions
    NoCompanyFactsFound,
    
    # Backwards compatibility
    CompanyFiling,
    CompanyFilings,
    CompanyFacts
)
```

## Need Help?

If you have any questions about migrating to the new API, please open an issue on the GitHub repository.
EOL < /dev/null