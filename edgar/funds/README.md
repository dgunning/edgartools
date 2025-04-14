# Fund Data Package

The `edgar.funds` package provides a comprehensive suite of tools for working with investment fund data from the SEC. It implements a domain model that reflects the hierarchical structure of investment funds:

- **Fund Company** → **Fund Series** → **Share Classes**

## Key Components

### Core Classes

- **`Fund`**: Represents an investment fund company that may offer multiple fund series
- **`FundSeries`**: Represents a specific fund product/strategy
- **`FundClass`**: Represents a specific share class with its own ticker and fee structure

### Data Access

- **`get_fund(identifier)`**: Smart factory function that returns the appropriate entity based on the identifier type (ticker, series ID, class ID, or CIK)
- **`get_fund_series(fund)`**: Get all fund series for a fund company
- **`get_fund_classes(fund)`**: Get all share classes for a fund company

### Reports

- **`FundReport`**: Base class for working with fund regulatory filings
- **`ThirteenF`**: Specialized class for handling 13F filings (portfolio holdings)

## Usage Examples

### Lookup by Ticker

```python
from edgar.funds import get_fund

# Get fund information from ticker
fidelity_fund = get_fund("FCNTX")  # Fidelity Contrafund
print(fidelity_fund.name)          # "Fidelity Contrafund"
print(fidelity_fund.ticker)        # "FCNTX"
```

### Navigate Fund Hierarchy

```python
# Get the fund company
fund = fidelity_fund.fund  

# Get all series offered by the fund company
all_series = fund.get_series()
print(f"Number of series: {len(all_series)}")

# Get all share classes for a specific series
series = all_series[0]
series_classes = series.get_classes()
print(f"Classes in {series.name}: {len(series_classes)}")
```

### Get Portfolio Holdings

```python
# Get portfolio holdings from latest filing
portfolio = fund.get_portfolio()
print(portfolio.head())
```

## Fund Entity Resolution

The package includes sophisticated entity resolution capabilities:

1. **Identifier Resolution**
   - Resolves tickers, series IDs (S######), class IDs (C######) and CIKs to the appropriate entity type

2. **Series-Class Association**
   - Associates classes with their parent series even when data is incomplete
   - Uses multiple inference techniques including:
     - Direct series ID matching
     - Name pattern matching ("Series Name Class X")
     - Ticker prefix matching

## Rich Display Support

All entity classes support rich text display via the Rich library:

```python
from rich import print
fund = get_fund("VFINX")
print(fund)  # Displays a rich panel with detailed fund information
```

## Implementation Status

The package currently implements ~70% of the planned user journeys. See [fund_domain_model.md](./fund_domain_model.md) for a detailed status assessment and roadmap.

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