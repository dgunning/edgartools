# TTM Package Usage Guide

Trailing Twelve Months (TTM) calculations, Q4 derivation, and stock split adjustments for EdgarTools.

## Overview

TTM functionality is **integrated directly into the Company class**:

- **TTM Calculations**: `company.get_ttm()`, `company.get_ttm_revenue()`, `company.get_ttm_net_income()`
- **TTM Statements**: `company.income_statement(period='ttm')`
- **Q4 Derivation**: Automatically calculates Q4 from fiscal year and YTD data
- **Stock Split Adjustments**: Automatically detects and adjusts for stock splits

## Quick Start

```python
from edgar import Company

company = Company("AAPL")

# Get TTM revenue
ttm_revenue = company.get_ttm_revenue()
print(f"TTM Revenue: ${ttm_revenue.value / 1e9:.1f}B")
print(f"As of: {ttm_revenue.as_of_date}")
print(f"Periods: {ttm_revenue.periods}")

# Get TTM income statement
stmt = company.income_statement(period='ttm')
print(stmt)
```

## Company TTM Methods

### get_ttm()

Calculate TTM for any XBRL concept.

```python
from edgar import Company

company = Company("MSFT")

# By concept name (with or without namespace)
ttm = company.get_ttm("Revenues")
ttm = company.get_ttm("us-gaap:NetIncomeLoss")
ttm = company.get_ttm("GrossProfit")

# As of specific date
ttm = company.get_ttm("Revenues", as_of="2024-Q2")
ttm = company.get_ttm("Revenues", as_of="2024-06-30")

# Access TTM result
print(f"Value: ${ttm.value / 1e9:.1f}B")
print(f"As of: {ttm.as_of_date}")
print(f"Periods: {ttm.periods}")  # [(2024, 'Q1'), (2024, 'Q2'), ...]
print(f"Has gaps: {ttm.has_gaps}")
print(f"Q4 derived: {ttm.has_calculated_q4}")
```

### get_ttm_revenue() / get_ttm_net_income()

Convenience methods that try common concept names.

```python
from edgar import Company

company = Company("AAPL")

# These try multiple concept names automatically
ttm_revenue = company.get_ttm_revenue()  # Tries Revenues, SalesRevenueNet, etc.
ttm_income = company.get_ttm_net_income()  # Tries NetIncomeLoss, NetIncome, etc.

print(f"TTM Revenue: ${ttm_revenue.value / 1e9:.1f}B")
print(f"TTM Net Income: ${ttm_income.value / 1e9:.1f}B")
```

### Financial Statements with period='ttm'

```python
from edgar import Company

company = Company("NVDA")

# TTM income statement (rolling 4 quarters)
income_stmt = company.income_statement(period='ttm')

# TTM cash flow statement
cash_flow = company.cash_flow(period='ttm')

# Convert to DataFrame
df = company.income_statement(period='ttm', as_dataframe=True)

# Other period options
annual = company.income_statement(period='annual')      # Default
quarterly = company.income_statement(period='quarterly')

# Backward compatible (legacy parameter)
annual = company.income_statement(annual=True)
quarterly = company.income_statement(annual=False)
```

Note: `period='ttm'` is not available for balance_sheet (point-in-time data).

## TTMMetric Object

The result of `get_ttm()` calls:

```python
from edgar import Company

company = Company("AAPL")
ttm = company.get_ttm_revenue()

# Attributes
ttm.concept        # 'us-gaap:Revenues'
ttm.label          # 'Revenues'
ttm.value          # 394328000000.0
ttm.unit           # 'USD'
ttm.as_of_date     # date(2024, 9, 28)
ttm.periods        # [(2023, 'Q4'), (2024, 'Q1'), (2024, 'Q2'), (2024, 'Q3')]
ttm.period_facts   # List of FinancialFact objects used
ttm.has_gaps       # False (True if quarters not consecutive)
ttm.has_calculated_q4  # True if any Q4 was derived
ttm.warning        # Optional warning message
```

## Stock Split Handling

Stock splits are automatically detected and applied when using TTM methods.

### How It Works

1. **Detection**: Finds `StockSplitConversionRatio` facts in SEC filings
2. **Filtering**: Rejects stale facts (>280 day filing lag)
3. **Adjustment**:
   - EPS and per-share metrics: Divided by cumulative ratio
   - Share counts: Multiplied by cumulative ratio

### Manual Split Detection

```python
from edgar import Company
from edgar.ttm import detect_splits, apply_split_adjustments

company = Company("NVDA")
facts = company.facts._facts

# Detect splits
splits = detect_splits(facts)
for split in splits:
    print(f"Split on {split['date']}: {split['ratio']}:1")

# Output:
# Split on 2021-06-03: 4.0:1
# Split on 2024-05-31: 10.0:1

# Manual adjustment
adjusted_facts = apply_split_adjustments(facts, splits)
```

## Q4 Derivation (Quarterization)

Many companies report Q2 and Q3 as year-to-date (YTD) cumulative values. The TTM system automatically derives discrete quarters:

```
Company reports:           TTM derives:
Q1: $100B (discrete)       Q1: $100B (reported)
YTD_6M: $220B (Jan-Jun)    Q2: $120B = YTD_6M - Q1
YTD_9M: $350B (Jan-Sep)    Q3: $130B = YTD_9M - YTD_6M
FY: $480B (full year)      Q4: $130B = FY - YTD_9M
```

### EPS Derivation

EPS cannot be derived by subtraction (shares change over time). Q4 EPS is calculated from:

```
Q4 EPS = Q4 Net Income / Q4 Weighted Average Shares
Where: Q4 Shares = 4 * FY_Shares - 3 * YTD9_Shares
```

## Direct Access to TTM Utilities

For advanced use cases, access the calculation utilities directly:

```python
from edgar import Company
from edgar.ttm import TTMCalculator, TTMStatementBuilder

company = Company("AAPL")
facts = company.facts._facts

# Filter facts for a concept
revenue_facts = [f for f in facts if 'Revenue' in f.concept]

# Create calculator
calc = TTMCalculator(revenue_facts)

# Calculate TTM
ttm = calc.calculate_ttm()

# Calculate TTM trend over time
trend_df = calc.calculate_ttm_trend(periods=8)
print(trend_df[['as_of_quarter', 'ttm_value', 'yoy_growth']])
```

## Examples

### Compare TTM vs Annual

```python
from edgar import Company

company = Company("AAPL")

# Annual (fiscal year)
annual_stmt = company.income_statement(period='annual')

# TTM (rolling 4 quarters) - more current
ttm_stmt = company.income_statement(period='ttm')

# TTM gives you up-to-date financials
ttm_revenue = company.get_ttm_revenue()
print(f"TTM Revenue as of {ttm_revenue.as_of_date}: ${ttm_revenue.value/1e9:.1f}B")
```

### Handle Data Quality Issues

```python
from edgar import Company

company = Company("MSFT")
ttm = company.get_ttm_revenue()

if ttm.has_gaps:
    print("Warning: Non-consecutive quarters detected")

if ttm.has_calculated_q4:
    print("Note: Some quarters were derived from YTD/annual data")

if ttm.warning:
    print(f"Data quality: {ttm.warning}")
```

### Multiple Companies

```python
from edgar import Company

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]

for ticker in tickers:
    try:
        company = Company(ticker)
        ttm = company.get_ttm_revenue()
        print(f"{ticker}: ${ttm.value / 1e9:.1f}B (as of {ttm.as_of_date})")
    except Exception as e:
        print(f"{ticker}: Error - {e}")
```

## API Reference

### Company Methods

| Method | Description |
|--------|-------------|
| `get_ttm(concept, as_of=None)` | Calculate TTM for any XBRL concept |
| `get_ttm_revenue(as_of=None)` | TTM revenue (tries common concepts) |
| `get_ttm_net_income(as_of=None)` | TTM net income (tries common concepts) |
| `income_statement(period='ttm')` | TTM income statement |
| `cash_flow(period='ttm')` | TTM cash flow statement |

### TTM Utility Functions

| Function | Description |
|----------|-------------|
| `TTMCalculator(facts)` | Create TTM calculator for facts |
| `detect_splits(facts)` | Find stock split events |
| `apply_split_adjustments(facts, splits)` | Adjust facts for splits |

### TTMCalculator Methods

| Method | Description |
|--------|-------------|
| `calculate_ttm(as_of=None)` | Calculate TTM value |
| `calculate_ttm_trend(periods=8)` | Rolling TTM values over time |
| `derive_eps_for_quarter(...)` | Calculate EPS for derived quarters |

## Limitations

1. **Balance Sheet**: TTM not applicable (point-in-time data)
2. **Non-additive metrics**: Ratios, averages cannot be derived by subtraction
3. **Fiscal year variations**: Non-calendar fiscal years may have alignment issues
4. **Data availability**: Requires Q1, YTD_6M, YTD_9M, and FY facts for full quarterization

## Dependencies

The TTM package is part of EdgarTools and requires:
- `pandas` (for DataFrame operations)
