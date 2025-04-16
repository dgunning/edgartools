# Ratios API

The `ratios` module in edgartools provides comprehensive tools for calculating and analyzing financial ratios from XBRL data. It is designed to help users assess company performance, efficiency, profitability, liquidity, and leverage using standardized financial statements.

## Key Classes

### FinancialRatios
- **Purpose:** Main interface for calculating a wide range of financial ratios from an XBRL object.
- **Usage:**
  ```python
  ratios = FinancialRatios(xbrl)
  liquidity = ratios.calculate_liquidity_ratios()  # Returns RatioAnalysisGroup
  all_ratios = ratios.calculate_all()  # Dict of RatioAnalysisGroup by category
  ```
- **Methods:**
  - `calculate_liquidity_ratios()`
  - `calculate_profitability_ratios()`
  - `calculate_efficiency_ratios()`
  - `calculate_leverage_ratios()`
  - `calculate_all()` — returns all categories
  - `get_ratio_data(ratio_type)` — get raw data for a specific ratio
  - Individual ratio methods: `calculate_current_ratio()`, `calculate_return_on_assets()`, `calculate_operating_margin()`, `calculate_gross_margin()`, `calculate_quick_ratio()`, etc.

### RatioAnalysisGroup
- **Purpose:** Container for a group of related ratio calculations (e.g., all liquidity ratios).
- **Attributes:**
  - `name`, `description`, `ratios` (dict of ratio name → RatioAnalysis)
- **Display:** Supports rich rendering for tables in notebooks/terminals.

### RatioAnalysis
- **Purpose:** Stores results and metadata for a single ratio calculation.
- **Attributes:**
  - `name`, `description`, `calculation_df` (raw data), `results` (Series/DataFrame), `components` (inputs), `equivalents_used` (how missing concepts were handled)
- **Display:** Supports rich rendering.

### ConceptEquivalent
- **Purpose:** Defines how to compute a concept if missing from the XBRL data, using alternate formulas.

## Supported Ratio Categories & Examples
- **Liquidity:** Current Ratio, Quick Ratio, Cash Ratio, Working Capital
- **Profitability:** Gross Margin, Operating Margin, Return on Assets, Return on Equity
- **Efficiency:** Asset Turnover, Inventory Turnover, Receivables Turnover
- **Leverage:** Debt to Assets, Interest Coverage, Equity Multiplier

## Example Usage
```python
from edgar.xbrl.analysis.ratios import FinancialRatios

ratios = FinancialRatios(xbrl)
liquidity = ratios.calculate_liquidity_ratios()
print(liquidity)  # Pretty table of ratios

# Access specific ratio
current_ratio = liquidity.ratios['current'].results

# Calculate all ratios
all_ratios = ratios.calculate_all()
profitability = all_ratios['profitability']
print(profitability)

# Get raw data for a ratio
calc_df, equivalents = ratios.get_ratio_data('current')
```

## Notes
- Handles missing XBRL concepts using defined equivalents (e.g., calculates Gross Profit if not reported).
- All calculations are vectorized for multi-period analysis.
- Designed for extensibility and integration with pandas workflows.

## See Also
- [Financial Statements API](financial_statements_api.md)
- [Company API](company_api.md)
