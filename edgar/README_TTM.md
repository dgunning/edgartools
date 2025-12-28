# Rolling TTM (Trailing Twelve Months) Feature

This release introduces enhanced Trailing Twelve Months (TTM) capabilities to the EdgarTools library, enabling powerful trend analysis and better handling of complex financial reporting structures.

## Key Features

### 1. Rolling TTM Analysis
Instead of just a single "latest TTM" snapshot, you can now generate **Rolling TTM** statements that show annualized performance over time (e.g., TTM as of Q3, TTM as of Q2, etc.). This smoothes out seasonality and reveals underlying growth trends.

### 2. Multi-Period Support
The standard `income_statement`, `balance_sheet`, and `cash_flow` methods now accept a `period='ttm'` argument, integrating seamlessly with the existing API.

### 3. Robust Calculation Logic
*   **Fiscal Year Alignment:** Intelligently handles companies with non-standard fiscal years (e.g., NVIDIA, Apple) to align data correctly across periods.
*   **Adjustment Handling:** Correctly processes derived quarterly data even when accounting adjustments result in negative calculated values (with debug logging).
*   **Revenue Prioritization:** Improved logic to correctly identify "Total Revenue" for conglomerates with mixed revenue streams (e.g., Contracts + Leasing).

## Usage Examples

### Basic TTM Income Statement

```python
from edgar import Company

company = Company("AAPL")

# Get the latest Rolling TTM Income Statement (default 4 periods)
ttm_income = company.income_statement(period='ttm')
print(ttm_income)
```

### Trend Analysis (Last 3 Years)

```python
# Analyze annual trends over 12 quarters (3 years)
trend_stmt = company.income_statement(periods=12, period='ttm')

# Convert to DataFrame for analysis
df = trend_stmt.to_dataframe()

# Inspect Revenue Trend
revenue_row = df.loc['Revenues'] # Concept name may vary slightly
print(revenue_row)
```

### Cash Flow TTM

```python
company = Company("NVDA")

# TTM Cash Flow to analyze operating cash generation
cash_flow = company.cash_flow(periods=4, period='ttm')
print(cash_flow)
```

## Technical Details

*   **Period Type:** Use `period='ttm'` in `income_statement()`, `balance_sheet()`, and `cash_flow()`.
*   **Legacy Support:** `annual=True` still works and defaults to `period='annual'`.
*   **Labels:** TTM columns are labeled with their fiscal period and "LTM" (Last Twelve Months), e.g., `Q3 2025 LTM`.

## Implementation Notes

The TTM calculation engine:
1.  Retrieves raw quarterly facts.
2.  "Quarterizes" the data (deriving Q2/Q3/Q4 from YTD/FY filings if necessary).
3.  Aggregates the 4 most recent consecutive quarters for each rolling window.
4.  Injects these synthetic TTM facts into the standard statement builder to preserve hierarchical formatting and calculated fields (like Gross Profit).
