# Fund Entity API Migration Guide

## Introduction

We're excited to introduce a significant improvement to the funds API in edgartools. This guide explains the changes and provides migration steps for users of the library.

## Overview of Changes

The funds module has been enhanced with a more intuitive API that better reflects the hierarchical nature of investment funds:

1. **Renamed Entities**
   - `Fund` → `FundCompany` (clearer naming for the top-level entity)
   - `FundSeries` and `FundClass` remain unchanged

2. **New Smart Factory Function**
   - `find_fund(identifier)` returns the appropriate entity type based on the identifier:
     - `FundClass` for ticker symbols and class IDs
     - `FundSeries` for series IDs
     - `FundCompany` for CIKs

3. **Specialized Getter Functions**
   - `get_fund_company(cik)` - Get a fund company by CIK
   - `get_fund_series(series_id)` - Get a fund series by ID
   - `get_fund_class(class_id_or_ticker)` - Get a fund class by ID or ticker
   - `get_series_by_name(company_cik, name)` - Find a series by name within a company
   - `get_class_by_ticker(ticker)` - Get a class by ticker (convenience method)

4. **Enhanced Navigation**
   - `fund_class.series` - Navigate from class to parent series
   - `fund_class.company` - Navigate from class to parent company
   - `fund_series.company` - Navigate from series to parent company

5. **Backward Compatibility**
   - The old `Fund` class and `get_fund()` function remain available
   - New entities have alias properties for backward compatibility

## Migration Guide

### Before

```python
from edgar.funds import get_fund, Fund

# Get a fund class by ticker
fund_class = get_fund("VFINX")
print(fund_class.name)

# Get the fund company
fund_company = fund_class.fund
print(fund_company.cik)

# Get all series for the fund
all_series = fund_company.get_series()
for series in all_series:
    print(series.name)

# This would return a Fund (company) even though it's a series ID
fund = get_fund("S000005029")
```

### After

```python
from edgar.funds import find_fund, get_fund_company, get_fund_series, get_fund_class

# Get a fund class by ticker (returns FundClass)
fund_class = find_fund("VFINX")
print(fund_class.name)

# Get the fund company
fund_company = fund_class.company  # or fund_class.fund_company
print(fund_company.cik)

# Get the parent series
series = fund_class.series
print(series.name)

# Get all series for the fund company
all_series = fund_company.get_series()
for series in all_series:
    print(series.name)

# This now correctly returns a FundSeries
series = find_fund("S000005029")
```

## Using Specialized Getters

The new specialized getter functions provide a more explicit way to get specific entity types:

```python
# Get a fund company by CIK
company = get_fund_company("0000102909")  # Vanguard

# Get a fund series by series ID
series = get_fund_series("S000584")  # Vanguard 500 Index Fund

# Get a fund class by class ID
class_obj = get_fund_class("C000065928")  # Vanguard 500 Index Fund Admiral Shares

# Get a fund class by ticker
class_obj = get_fund_class("VFINX")  # Vanguard 500 Index Fund Investor Shares
# or using the convenience function
class_obj = get_class_by_ticker("VFINX")

# Find a series by name within a company
series = get_series_by_name(102909, "500 Index Fund")
```

## Backward Compatibility

For existing code, the old API continues to work:

```python
# Old API (still available)
from edgar.funds import get_fund, Fund

# This still works as before
fund_class = get_fund("VFINX")
fund_company = Fund("0000102909")

# These attributes are maintained for compatibility
fund_class.fund  # Same as fund_class.company
fund_series.fund  # Same as fund_series.company
```

## Key Benefits

1. **More Intuitive Type Resolution**
   - `find_fund("S000xxx")` now returns a `FundSeries` (not a `Fund` as before)
   - `find_fund("C000xxx")` returns a `FundClass`
   - `find_fund("0000xxx")` returns a `FundCompany`

2. **Clearer Entity Naming**
   - `FundCompany` better describes its role as the legal entity

3. **Better Navigation**
   - Improved navigation between related entities
   - Explicit properties for moving up the hierarchy

4. **Specialized Getters for Explicit Entity Access**
   - When you know exactly what type you want, use the specialized getters

## Full Example

```python
from edgar.funds import find_fund, get_fund_company
from rich import print

# Start with a ticker symbol
vfiax = find_fund("VFIAX")  # Returns a FundClass
print(f"Fund Class: {vfiax.name} ({vfiax.ticker})")

# Navigate to the parent series
series = vfiax.series  # Returns a FundSeries
print(f"Series: {series.name}")

# Get all classes in this series
classes = series.get_classes()
print(f"Classes in this series: {len(classes)}")
for cls in classes:
    print(f"- {cls.name} ({cls.ticker or 'No ticker'})")

# Navigate to the parent company
company = vfiax.company  # Returns a FundCompany
print(f"Fund Company: {company.data.name}")

# See all series offered by this company
all_series = company.get_series()
print(f"Total series offered: {len(all_series)}")
```

## Conclusion

The new fund entity API provides a more intuitive and predictable way to work with fund entities while maintaining backward compatibility. We encourage migrating to the new API for clearer code and better alignment with the domain model.

For any questions or issues with the migration, please file an issue on GitHub.