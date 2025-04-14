# Fund Data Package

The `edgar.funds` package provides a comprehensive suite of tools for working with investment fund data from the SEC. It implements a domain model that reflects the hierarchical structure of investment funds:

- **Fund Company** → **Fund Series** → **Share Classes**

## Key Components

### Core Classes

- **`FundCompany`**: Represents an investment fund company that may offer multiple fund series
- **`FundSeries`**: Represents a specific fund product/strategy
- **`FundClass`**: Represents a specific share class with its own ticker and fee structure

### Smart Factory Function

- **`find_fund(identifier)`**: Smart factory that returns the appropriate entity type based on the identifier:
  - Returns a `FundCompany` for CIKs
  - Returns a `FundSeries` for series IDs (starting with S)
  - Returns a `FundClass` for class IDs (starting with C) or ticker symbols

### Specialized Getters

- **`get_fund_company(cik)`**: Get a fund company by its CIK
- **`get_fund_series(series_id)`**: Get a fund series by its series ID
- **`get_fund_class(class_id_or_ticker)`**: Get a fund class by its class ID or ticker
- **`get_series_by_name(company_cik, name)`**: Get a series by its name within a fund company
- **`get_class_by_ticker(ticker)`**: Get a fund class by its ticker symbol (convenience method)

### Reports

- **`FundReport`**: Base class for working with fund regulatory filings
- **`ThirteenF`**: Specialized class for handling 13F filings (portfolio holdings)

## Usage Examples

### Lookup by Identifier

```python
from edgar.funds import find_fund, get_class_by_ticker

# Get fund entity by ticker (returns a FundClass)
fund_class = find_fund("FCNTX")  # Fidelity Contrafund
print(fund_class.name)           # "Contrafund Class K"
print(fund_class.ticker)         # "FCNTX"

# Get fund entity by series ID (returns a FundSeries)
fund_series = find_fund("S000007")
print(fund_series.name)          # "Fidelity Contrafund"

# Get fund entity by company CIK (returns a FundCompany)
fund_company = find_fund("0000315700")
print(fund_company.data.name)    # "Fidelity"

# Direct lookup
fund_class = get_class_by_ticker("FCNTX")
```

### Navigate Fund Hierarchy

```python
# Start with a fund class
class_obj = find_fund("FCNTX")

# Get the parent fund series
series = class_obj.series
print(f"Parent series: {series.name}")

# Get the fund company
company = class_obj.company  # or class_obj.fund_company for backward compatibility
print(f"Fund company: {company.data.name}")

# Get all series offered by the fund company
all_series = company.get_series()
print(f"Number of series: {len(all_series)}")

# Get all share classes for a specific series
series_classes = series.get_classes()
print(f"Classes in {series.name}: {len(series_classes)}")
for class_obj in series_classes:
    print(f"- {class_obj.name} ({class_obj.ticker or 'No ticker'})")
```

### Get Portfolio Holdings

```python
# Get portfolio holdings from latest filing
company = find_fund("0000315700")  # Fidelity
portfolio = company.get_portfolio()
print(portfolio.head())
```

## Fund Entity Resolution

The package includes sophisticated entity resolution capabilities:

1. **Smart Entity Resolution**
   - Returns the most appropriate entity type based on the identifier
   - Makes exploration of the fund hierarchy more intuitive

2. **Identifier Resolution**
   - Resolves tickers, series IDs (S######), class IDs (C######) and CIKs

3. **Series-Class Association**
   - Associates classes with their parent series even when data is incomplete
   - Uses multiple inference techniques including:
     - Direct series ID matching
     - Name pattern matching ("Series Name Class X")
     - Ticker prefix matching

## Rich Display Support

All entity classes support rich text display via the Rich library:

```python
from rich import print
fund = find_fund("VFINX")
print(fund)  # Displays a rich panel with detailed fund information
```

## Implementation Status

The package currently implements ~75% of the planned user journeys. See [fund_domain_model.md](./fund_domain_model.md) for a detailed status assessment and roadmap.

## Backward Compatibility

The package maintains backward compatibility with the previous API:

```python
# Old API (still works)
from edgar.funds import get_fund, Fund

# Get fund using the legacy function
fund_class = get_fund("FCNTX")

# Legacy Fund class (now representing a FundCompany)
fund_company = Fund("0000315700")
```

## Future Enhancements

1. **Enhanced Search**
   - Improved name-based search
   - Fuzzy matching for fund names
  
2. **Richer Comparison Data**
   - Fee data (expense ratios)
   - Performance metrics
   - Holdings comparison

3. **Advanced Portfolio Analysis**
   - Sector breakdowns
   - Time-series analysis
   - Performance attribution