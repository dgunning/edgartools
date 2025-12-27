# TTM (Trailing Twelve Months) Feature Implementation Summary

## Overview

Successfully implemented comprehensive TTM (Trailing Twelve Months) calculation functionality for EdgarTools. TTM calculations aggregate 4 consecutive quarters into rolling 12-month metrics, providing a smoothed view of financial performance that eliminates seasonal variations.

## Implementation Summary

### Phase 1: Core TTM Calculation Logic ✅

**Files Created:**
- `edgar/entity/ttm.py` (546 lines)
- `tests/test_ttm_calculator.py` (500 lines)

**Key Components:**

1. **TTMMetric** - Result dataclass containing:
   - `value`: TTM value (sum of 4 quarters)
   - `periods`: List of fiscal periods included
   - `period_facts`: List of FinancialFact objects used
   - `has_gaps`: Boolean indicating data quality
   - `warning`: Optional warning message
   - Rich console representation with `__rich__()`

2. **TTMCalculator** - Core calculation engine:
   - `calculate_ttm(as_of)`: Calculate single TTM value
   - `calculate_ttm_trend(periods)`: Calculate rolling TTM values
   - `_filter_quarterly_facts()`: Filter to quarterly duration (80-100 days)
   - `_select_ttm_window()`: Select 4 consecutive quarters
   - `_check_for_gaps()`: Detect gaps in quarterly data
   - `_generate_warning()`: Generate data quality warnings

3. **TTMStatement** - Full financial statement with TTM values:
   - Statement type (IncomeStatement, CashFlowStatement)
   - Multiple line items with TTM values
   - Rich console table output
   - `to_dataframe()`: Convert to pandas DataFrame

4. **TTMStatementBuilder** - Build TTM statements:
   - `build_income_statement(as_of)`: Build TTM income statement
   - `build_cashflow_statement(as_of)`: Build TTM cash flow statement

**Tests:**
- 20 comprehensive unit tests (all passing)
- Test coverage:
  - Basic TTM calculation (4 and 8 quarters)
  - Error handling (insufficient data)
  - Data quality warnings
  - Period filtering (quarterly vs instant vs annual)
  - Gap detection
  - TTM trend calculation with YoY growth

### Phase 2: EntityFacts Integration ✅

**Files Modified:**
- `edgar/entity/entity_facts.py` (+239 lines)

**Files Created:**
- `tests/test_entity_facts_ttm.py` (300 lines)

**New Methods Added to EntityFacts:**

1. **Core TTM Methods:**
   - `get_ttm(concept, as_of)`: Calculate TTM for any concept
   - `_parse_as_of_parameter(as_of)`: Parse period strings and dates

2. **Convenience Methods:**
   - `get_ttm_revenue(as_of)`: TTM revenue
   - `get_ttm_net_income(as_of)`: TTM net income
   - `get_ttm_operating_cash_flow(as_of)`: TTM operating cash flow

**Features:**
- Automatic concept name normalization (adds `us-gaap:` prefix)
- Handles multiple concept name variations for each metric
- Supports period string parsing: "2024-Q2", "2024-FY"
- Supports date object parsing
- Error handling with clear messages

**Tests:**
- 11 unit tests for EntityFacts integration (all passing)
- Test coverage for period string parsing (Q1-Q4, FY)
- Error handling tests (invalid format, invalid period)

### Phase 3: TTM Trend Analysis ✅

**Files Modified:**
- `edgar/entity/entity_facts.py` (+93 lines)

**New Methods:**
1. `get_ttm_trend(concept, periods)`: Calculate rolling TTM values
2. `get_ttm_revenue_trend(periods)`: Revenue trend convenience method

**Features:**
- Returns pandas DataFrame with:
  - `as_of_quarter`: e.g., 'Q2 2024'
  - `ttm_value`: TTM value for that quarter
  - `fiscal_year`: e.g., 2024
  - `fiscal_period`: e.g., 'Q2'
  - `yoy_growth`: % change vs 4 quarters ago
  - `periods_included`: List of quarters in TTM window
- Most recent quarter first (descending order)
- YoY growth calculation when 8+ quarters available
- Configurable number of periods (default: 8)

**Integration Test Results:**
- Successfully tested with Apple (AAPL) data
- TTM Revenue: $399.5B (most recent)
- TTM Net Income: $106.0B
- Historical TTM calculations verified
- Trend analysis with YoY growth verified

### Phase 4: TTM Statement Support ✅

**Files Modified:**
- `edgar/entity/entity_facts.py` (+66 lines)
- `edgar/entity/ttm.py` (fixed `cash_flow()` method name)

**New Methods:**
1. `get_ttm_income_statement(as_of)`: Build complete TTM income statement
2. `get_ttm_cashflow_statement(as_of)`: Build complete TTM cash flow statement

**Features:**
- Leverages existing TTMStatementBuilder class
- Integrates with EntityFacts period parsing
- Returns TTMStatement objects with rich output
- Supports historical statement building (as_of parameter)
- Converts to DataFrame for analysis

### Phase 5: Documentation and Examples ✅

**Files Created:**
- `examples/ttm_example.py` (221 lines)
- `test_ttm_integration.py` (manual integration tests)
- `TTM_FEATURE_SUMMARY.md` (this file)

**Documentation:**
- Comprehensive docstrings for all methods with examples
- 13 detailed examples in `ttm_example.py`:
  1. Most recent TTM revenue
  2. TTM net income
  3. TTM profit margin calculation
  4. Historical TTM (specific quarter)
  5. Historical TTM (specific date)
  6. TTM for specific concepts
  7. TTM revenue trend (8 quarters)
  8. TTM Year-over-Year growth analysis
  9. Custom TTM trend for multiple concepts
  10. Complete TTM income statement
  11. Complete TTM cash flow statement
  12. Compare TTM vs Annual results
  13. Multi-company TTM comparison

## Code Statistics

**Total Lines Added:** ~2,100 lines
- Production code: ~800 lines
- Test code: ~800 lines
- Documentation/Examples: ~500 lines

**Files Created:** 6
**Files Modified:** 2

## Testing Summary

**Unit Tests:** 31 tests (all passing)
- TTMCalculator: 20 tests
- EntityFacts integration: 11 tests

**Integration Tests:** Verified with real Apple (AAPL) data
- All TTM methods working correctly
- Trend analysis producing valid results
- Statement building functioning as expected

## API Surface

### Core Functions

```python
from edgar import Company

# Get company facts
aapl = Company("AAPL")
facts = aapl.get_facts()

# Basic TTM calculations
ttm_revenue = facts.get_ttm_revenue()
ttm_net_income = facts.get_ttm_net_income()
ttm_ocf = facts.get_ttm_operating_cash_flow()

# Historical TTM
ttm_q2 = facts.get_ttm_revenue(as_of='2024-Q2')
ttm_date = facts.get_ttm_revenue(as_of=date(2024, 6, 30))

# TTM for any concept
ttm = facts.get_ttm('OperatingIncomeLoss')

# TTM trend analysis
trend = facts.get_ttm_revenue_trend(periods=8)

# TTM statements
income_stmt = facts.get_ttm_income_statement()
cf_stmt = facts.get_ttm_cashflow_statement()
```

## Key Features

1. **Automatic Period Selection:**
   - Filters to quarterly facts (80-100 day duration)
   - Selects most recent 4 consecutive quarters
   - Allows calendar variations (70-110 days between quarters)

2. **Data Quality Validation:**
   - Minimum 4 quarters required
   - Warns if < 8 quarters available (can't calculate YoY)
   - Detects gaps in quarterly data
   - Provides clear error messages

3. **Flexible Period Specification:**
   - Period strings: "2024-Q2", "2024-FY"
   - Date objects: `date(2024, 6, 30)`
   - None for most recent TTM

4. **Multiple Concept Support:**
   - Handles various concept name variations
   - Revenue: 6 different concept names supported
   - Net Income: 5 variations
   - Operating Cash Flow: 4 variations

5. **Rich Output:**
   - TTMMetric with `__rich__()` method
   - TTMStatement with formatted table output
   - pandas DataFrame conversion

## Use Cases

1. **Current Performance Analysis:**
   - Get most recent 12-month performance
   - Compare to annual results
   - Calculate profit margins and ratios

2. **Trend Analysis:**
   - Track TTM revenue over time
   - Calculate YoY growth rates
   - Identify growth trends and inflection points

3. **Multi-Company Comparisons:**
   - Compare TTM metrics across companies
   - Normalize for seasonality
   - Fair comparisons regardless of fiscal year end

4. **Statement Analysis:**
   - Build complete TTM financial statements
   - Compare line items to annual statements
   - Analyze current run-rate

## Technical Decisions

1. **Used Company Facts API** as primary data source
   - Cleaner, more reliable than XBRL
   - Better performance
   - Simpler integration

2. **Lenient Validation** approach
   - Minimum 4 quarters (vs strict 8)
   - Allows gaps with warnings
   - Flexible calendar variations

3. **Period Filtering** based on duration
   - 80-100 days for quarterly
   - 350-380 days for annual
   - Excludes instant/point-in-time facts

4. **Follows EdgarTools Patterns:**
   - Similar to `get_revenue()`, `income_statement()` methods
   - Rich output with `__rich__()` methods
   - Pandas DataFrame conversion support
   - Comprehensive docstrings with examples

## Future Enhancements (Not Implemented)

1. TTM balance sheet support (requires different logic - instant vs duration facts)
2. Caching of TTM calculations
3. TTM calculation history/audit trail
4. More advanced gap-filling strategies
5. Support for fiscal year variations (non-calendar year ends)

## Git Commits

1. `568193c3` - feat: add TTM (Trailing Twelve Months) calculation feature
2. `067cd2ca` - docs: add comprehensive TTM calculation examples

## Branch

All changes committed to: `TTM-feature`

## Next Steps

1. Code review and feedback
2. Merge to main branch
3. Update changelog
4. Release notes
5. User documentation updates

---

**Implementation Date:** 2025-12-27
**Implementation Time:** ~4 hours
**Status:** ✅ Complete - All phases finished, all tests passing
