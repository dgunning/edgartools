# Fund Entity API

The Fund Entity API provides a comprehensive suite of tools for working with investment fund data from the SEC. It implements a domain model that reflects the hierarchical structure of investment funds:

- **Fund Company** → **Fund Series** → **Share Classes**

## Core Classes

```python
from edgar.funds import FundCompany, FundSeries, FundClass, find_fund

# Core classes for the fund hierarchy
company = FundCompany("0000102909")  # Vanguard (top-level entity)
series = FundSeries("S000584", "500 Index Fund", company)  # A specific fund product/strategy
fund_class = FundClass("C000065928", company, name="Admiral Shares", ticker="VFIAX")  # A specific share class
```

## Smart Factory Function

```python
from edgar.funds import find_fund

# Returns a FundClass for ticker symbols and class IDs
fund_class = find_fund("VFIAX")  # By ticker
fund_class = find_fund("C000065928")  # By class ID

# Returns a FundSeries for series IDs
fund_series = find_fund("S000584")

# Returns a FundCompany for CIKs
fund_company = find_fund("0000102909")
```

## Specialized Getter Functions

```python
from edgar.funds import get_fund_company, get_fund_series, get_fund_class, get_class_by_ticker, get_series_by_name

# Get entities directly by their identifiers
company = get_fund_company("0000102909")  # By CIK
series = get_fund_series("S000584")  # By series ID
fund_class = get_fund_class("C000065928")  # By class ID
fund_class = get_class_by_ticker("VFIAX")  # By ticker

# Find a series by name within a company
series = get_series_by_name(102909, "500 Index Fund")
```

## Navigation Between Entities

```python
# Start with a fund class
fund_class = find_fund("VFIAX")

# Navigate to parent series
series = fund_class.series
print(f"Parent series: {series.name}")

# Navigate to fund company
company = fund_class.company  # or fund_class.fund_company for backward compatibility
print(f"Fund company: {company.data.name}")

# Get all series offered by the company
all_series = company.get_series()

# Get all classes in a series
series_classes = series.get_classes()
```


## Relevant User Journeys
- Investment Fund Research Journey
- Fund Holdings Analysis Journey
