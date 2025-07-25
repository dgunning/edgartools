# XBRL Statement Stitching - Period Selection Logic

## Overview

The period selection system is responsible for intelligently choosing the most appropriate reporting periods from multiple XBRL filings to create coherent, multi-period financial statement views. This document provides comprehensive documentation of the refactored period selection logic implemented in `periods.py`.

## Architecture Overview

The period selection system has been refactored from a monolithic function into a clean, class-based architecture with clear separation of concerns:

```
PeriodOptimizer (Main Orchestrator)
├── PeriodSelectionConfig (Configuration)
├── PeriodMatcher (Exact Matching Logic)
├── FiscalPeriodClassifier (Period Classification)
├── StatementTypeSelector (Statement-Specific Logic)
├── PeriodMetadataEnricher (Metadata Enhancement)
└── PeriodDeduplicator (Deduplication & Sorting)
```

## Core Classes and Responsibilities

### 1. PeriodSelectionConfig

A dataclass that centralizes all configuration parameters for period selection behavior.

```python
@dataclass
class PeriodSelectionConfig:
    # Duration ranges for different period types
    annual_duration_range: Tuple[int, int] = (350, 380)
    quarterly_duration_range: Tuple[int, int] = (80, 100)
    q2_ytd_range: Tuple[int, int] = (175, 190)
    q3_ytd_range: Tuple[int, int] = (260, 285)
    q4_annual_range: Tuple[int, int] = (350, 380)
    
    # Target durations for optimization
    target_annual_days: int = 365
    target_quarterly_days: int = 90
    target_q2_ytd_days: int = 180
    target_q3_ytd_days: int = 270
    
    # Behavior flags
    require_exact_matches: bool = True
    allow_fallback_when_no_doc_date: bool = True
    max_periods_default: int = 8
```

**Key Features:**
- **Configurable Duration Ranges**: All period duration expectations are configurable
- **Target Optimization**: Periods are selected based on proximity to target durations
- **Behavior Control**: Flags control exact matching requirements and fallback behavior
- **Extensible**: Easy to add new configuration parameters

### 2. PeriodMatcher

Handles exact period matching logic, eliminating all approximate matching to prevent fiscal year boundary bugs.

**Key Methods:**
- `find_exact_instant_match()`: Finds instant periods that exactly match a target date
- `find_exact_duration_match()`: Finds duration periods that end exactly on a target date
- `filter_by_duration_range()`: Filters periods by duration and sorts by proximity to target

**Critical Design Decision:**
The system now requires **exact matches only** when `document_period_end_date` is available. This eliminates the fiscal year boundary bugs that occurred with approximate matching (3-day and 14-day tolerances).

### 3. FiscalPeriodClassifier

Classifies and filters periods based on fiscal information and duration characteristics.

**Classification Methods:**
- `classify_annual_periods()`: Identifies periods with 350-380 day durations
- `classify_quarterly_periods()`: Identifies periods with 80-100 day durations  
- `classify_ytd_periods()`: Identifies year-to-date periods based on fiscal quarter
- `get_expected_durations()`: Returns expected duration ranges for fiscal periods

**Fiscal Period Logic:**
- **FY (Fiscal Year)**: Expects annual periods (~365 days)
- **Q1**: Expects quarterly periods (~90 days)
- **Q2**: Expects quarterly (~90 days) + YTD periods (~180 days)
- **Q3**: Expects quarterly (~90 days) + YTD periods (~270 days)
- **Q4**: Expects quarterly (~90 days) + annual periods (~365 days)

### 4. StatementTypeSelector

Handles statement-specific period selection logic with different approaches for different statement types.

#### Balance Sheet Logic (`select_balance_sheet_periods`)

Balance sheets require **instant periods** (point-in-time snapshots):

1. **Filter for Instant Periods**: Only considers periods with `type == 'instant'`
2. **Exact Date Matching**: If `document_period_end_date` is available:
   - Searches for instant period with exactly matching date
   - Returns the exact match if found
   - Returns empty list if no exact match (prevents fiscal year boundary issues)
3. **Fallback**: If no `document_period_end_date`, uses the most recent instant period

#### Income Statement Logic (`select_income_statement_periods`)

Income statements require **duration periods** (time ranges):

1. **Filter for Duration Periods**: Only considers periods with `type == 'duration'`
2. **Duration Calculation**: Calculates `duration_days` for all periods
3. **Exact End Date Matching**: If `document_period_end_date` is available:
   - Finds all periods that end exactly on the document date
   - Applies fiscal period classification to select appropriate durations
4. **Fiscal Period Selection**: Based on `fiscal_period`:
   - **Annual (FY)**: Selects annual duration periods
   - **Quarterly (Q1-Q4)**: Selects quarterly + appropriate YTD periods
5. **Fallback**: Conservative fallback when no document date available

#### Cash Flow Logic (`select_cash_flow_periods`)

Uses the same logic as income statements since cash flow statements also use duration periods.

### 5. PeriodMetadataEnricher

Adds comprehensive metadata to selected periods for downstream processing and display.

**Metadata Added:**
- `xbrl_index`: Index of source XBRL object
- `period_key`, `period_label`, `period_type`: Core period information
- `entity_info`: Complete entity information from filing
- `doc_period_end_date`: Document period end date
- `fiscal_period`, `fiscal_year`: Fiscal calendar information
- `date` (instant) or `start_date`/`end_date` (duration): Parsed date objects
- `duration_days`: Calculated duration for duration periods
- `display_date`: Formatted date for display purposes

### 6. PeriodDeduplicator

Handles deduplication, sorting, and limiting of periods to produce the final result set.

**Deduplication Logic:**
- **Exact Date Matching**: Periods are considered duplicates only if they have exactly the same date
- **Type Awareness**: Only compares periods of the same type (instant vs duration)
- **Conservative Approach**: Preserves legitimate different periods that might have been incorrectly filtered by approximate matching

**Sorting Logic:**
- **Balance Sheets**: Sorted by instant date (most recent first)
- **Other Statements**: Sorted by end date (most recent first)

**Limiting:**
- Limits results to `max_periods` (default 8) to keep output manageable

## Period Selection Process Flow

### 1. Main Entry Point

```python
def determine_optimal_periods(xbrl_list: List[XBRL], statement_type: str, max_periods: int = 8):
    optimizer = PeriodOptimizer()
    return optimizer.determine_optimal_periods(xbrl_list, statement_type, max_periods)
```

The main function maintains the original API while delegating to the new class-based system.

### 2. PeriodOptimizer Orchestration

The `PeriodOptimizer.determine_optimal_periods()` method orchestrates the entire process:

```python
def determine_optimal_periods(self, xbrl_list, statement_type, max_periods):
    # Step 1: Extract periods from all XBRLs
    all_periods = self._extract_all_periods(xbrl_list, statement_type)
    
    # Step 2: Enrich with metadata
    enriched_periods = self._enrich_with_metadata(all_periods)
    
    # Step 3: Deduplicate, sort, and limit
    final_periods = self._deduplicate_and_limit(enriched_periods, max_periods, statement_type)
    
    return final_periods
```

### 3. Period Extraction (`_extract_all_periods`)

For each XBRL object:

1. **Skip Empty XBRLs**: Skip XBRLs with no reporting periods
2. **Extract Entity Info**: Get entity information including fiscal data
3. **Parse Document Date**: Extract and parse `document_period_end_date`
4. **Statement-Specific Selection**: Delegate to `StatementTypeSelector`
5. **Context Addition**: Add context information to each selected period

### 4. Statement-Specific Selection

The `StatementTypeSelector` applies different logic based on statement type:

- **BalanceSheet** → `select_balance_sheet_periods()`
- **IncomeStatement** → `select_income_statement_periods()`
- **CashFlowStatement** → `select_cash_flow_periods()`
- **Other** → Defaults to income statement logic

### 5. Metadata Enrichment (`_enrich_with_metadata`)

Each selected period is enriched with comprehensive metadata using `PeriodMetadataEnricher`.

### 6. Final Processing (`_deduplicate_and_limit`)

The final step processes all enriched periods:

1. **Chronological Sorting**: Sort by appropriate date field
2. **Deduplication**: Remove exact duplicates
3. **Limiting**: Limit to maximum number of periods

## Key Design Principles

### 1. Exact Matching Only

**Problem Solved**: The original system used approximate matching (3-day and 14-day tolerances) which caused fiscal year boundary bugs, where periods from the wrong fiscal year could be selected.

**Solution**: The refactored system requires exact matches when `document_period_end_date` is available:
- Balance sheets: Instant periods must have exactly matching dates
- Income/Cash flow: Duration periods must end exactly on the document date

**Benefits**:
- Eliminates fiscal year boundary crossing
- Ensures period selection accuracy
- Prevents incorrect period selection (e.g., 2025-01-01 instead of 2024-12-31)

### 2. Conservative Fallback

When `document_period_end_date` is not available, the system uses conservative fallback logic:
- Selects the most recent appropriate period
- Applies fiscal period classification when possible
- Avoids aggressive assumptions that could lead to incorrect selections

### 3. Fiscal Period Intelligence

The system understands fiscal period semantics:
- **Annual periods**: ~365 days, appropriate for FY filings
- **Quarterly periods**: ~90 days, appropriate for quarterly filings
- **YTD periods**: Variable duration based on fiscal quarter (Q2: ~180 days, Q3: ~270 days, Q4: ~365 days)

### 4. Configuration-Driven Behavior

All duration ranges, target values, and behavior flags are configurable through `PeriodSelectionConfig`, making the system:
- **Adaptable**: Easy to adjust for different requirements
- **Testable**: Different configurations can be tested independently
- **Maintainable**: Changes don't require code modifications

### 5. Comprehensive Error Handling

The system includes robust error handling:
- **Graceful Degradation**: Invalid periods are skipped rather than causing failures
- **Logging**: Comprehensive logging for debugging and monitoring
- **Type Safety**: Proper type checking and validation

## Testing Considerations

### 1. Unit Testing Strategy

Each class can be tested independently:
- **PeriodMatcher**: Test exact matching logic with various date scenarios
- **FiscalPeriodClassifier**: Test period classification with different durations
- **StatementTypeSelector**: Test statement-specific logic with mock data
- **PeriodDeduplicator**: Test deduplication and sorting logic

### 2. Integration Testing

Test the complete pipeline:
- **Multi-XBRL Scenarios**: Test with multiple XBRL objects
- **Cross-Fiscal-Year**: Test fiscal year boundary scenarios
- **Mixed Statement Types**: Test with different statement types
- **Edge Cases**: Test with missing data, invalid dates, etc.

### 3. Regression Testing

Critical scenarios to test:
- **Fiscal Year Boundaries**: Ensure no cross-year period selection
- **Exact Matching**: Verify only exact matches are selected when document dates available
- **Fallback Behavior**: Test conservative fallback when no document dates
- **Configuration Changes**: Test different configuration parameters

## Performance Considerations

### 1. Efficient Data Structures

- **Dictionary Lookups**: O(1) access for period lookups
- **List Comprehensions**: Efficient filtering operations
- **Minimal Copying**: Periods are copied only when necessary

### 2. Lazy Evaluation

- **On-Demand Processing**: Periods are processed only when needed
- **Early Termination**: Processing stops when sufficient periods found
- **Caching Friendly**: Results can be cached at multiple levels

### 3. Memory Management

- **Minimal Memory Footprint**: Only necessary data is retained
- **Garbage Collection Friendly**: No circular references
- **Scalable**: Handles large numbers of XBRL objects efficiently

## Migration from Legacy System

### API Compatibility

The main `determine_optimal_periods()` function maintains the same signature:

```python
# Legacy and new system both support:
determine_optimal_periods(xbrl_list, statement_type, max_periods=8)
```

### Behavioral Changes

**Exact Matching**: The new system is more strict about exact matching, which may result in fewer periods being selected in some cases. This is intentional and prevents incorrect period selection.

**Configuration**: The new system allows configuration of behavior that was previously hard-coded.

### Testing Migration

Existing tests should continue to work, but may need updates if they relied on approximate matching behavior.

## Future Enhancement Opportunities

### 1. Advanced Period Selection

- **Machine Learning**: Use ML to learn optimal period selection patterns
- **Industry-Specific Logic**: Customize selection logic for different industries
- **Regulatory Compliance**: Add logic for specific regulatory requirements

### 2. Performance Optimizations

- **Parallel Processing**: Process multiple XBRLs in parallel
- **Incremental Updates**: Update period selections incrementally
- **Advanced Caching**: Cache period selections across sessions

### 3. Enhanced Configuration

- **Dynamic Configuration**: Allow runtime configuration changes
- **Profile-Based Configuration**: Different configurations for different use cases
- **Validation**: Configuration validation and error reporting

## Conclusion

The refactored period selection system represents a significant improvement in maintainability, testability, and correctness. By eliminating approximate matching and implementing a clean class-based architecture, the system provides:

- **Accurate Period Selection**: Eliminates fiscal year boundary bugs
- **Maintainable Code**: Clear separation of concerns and single responsibility classes
- **Configurable Behavior**: All parameters can be adjusted without code changes
- **Robust Error Handling**: Comprehensive error handling and logging
- **Extensible Design**: Easy to add new features and functionality

The system successfully addresses the critical bugs in the original implementation while providing a solid foundation for future enhancements.
