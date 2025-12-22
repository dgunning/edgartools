# Duplicate Fact Handling in Entity Facts API

## Current Behavior

### 1. Parser Level
The `EntityFactsParser` currently:
- Parses ALL facts from the JSON without deduplication
- Preserves filing metadata (`filing_date`, `accession`, `form_type`)
- Does not filter or prioritize facts during parsing

### 2. Query Level
Limited duplicate handling:
- `latest()` method sorts by `filing_date` descending
- `latest_instant()` groups by concept and keeps only the most recent `period_end`
- No general deduplication for duration facts (income/cash flow items)

### 3. Financial Statement Methods
- `income_statement()`: Uses `latest_periods()` but doesn't deduplicate within periods
- `balance_sheet()`: Uses `latest_instant()` which does deduplicate
- `time_series()`: Sorts by `filing_date` but keeps all facts

### 4. Selection Logic
When duplicates exist, current selection is:
- **get_fact()**: Uses `max(facts, key=lambda f: (f.filing_date, f.period_end))`
- **latest_instant()**: Keeps fact with maximum `period_end` per concept
- **Other queries**: Return all matching facts

## Problems with Current Approach

### 1. Inconsistent Behavior
- Balance sheets deduplicate, income statements don't
- `get_fact()` returns one value, queries return multiple

### 2. Potential Issues
- Income statements may show duplicate rows for the same concept/period
- Pivot tables might fail or show incorrect data with duplicates
- Time series analysis includes restated values multiple times

### 3. No Restatement Awareness
- Cannot distinguish between restatements and amendments
- No tracking of which values supersede others

## Example: Snowflake's Gross Profit

For the period Feb 1 - Apr 30, 2024:
```
Filing 1: May 31, 2024 (FY2025) - $556,192,000
Filing 2: May 30, 2025 (FY2026) - $556,192,000 (same value)
```

Current behavior:
- Both facts are stored
- Income statement might show both
- `get_fact()` returns the May 2025 filing (most recent)

## Recommended Improvements

### 1. Add Deduplication Strategy

```python
class DeduplicationStrategy(Enum):
    LATEST_FILING = "latest_filing"      # Most recent filing date
    LATEST_PERIOD = "latest_period"      # Most recent period end
    ORIGINAL_FILING = "original_filing"  # First filing
    HIGHEST_QUALITY = "highest_quality"  # Prioritize audited/10-K
```

### 2. Implement Fact Resolution

```python
def resolve_duplicate_facts(facts: List[FinancialFact], 
                          strategy: DeduplicationStrategy) -> FinancialFact:
    """Select the best fact from duplicates for the same concept/period."""
    if strategy == DeduplicationStrategy.LATEST_FILING:
        return max(facts, key=lambda f: (f.filing_date, f.form_type == '10-K'))
    # ... other strategies
```

### 3. Track Fact Lineage

Add fields to FinancialFact:
- `is_restated`: Boolean indicating if this is a restatement
- `supersedes_accession`: Previous accession if this is a restatement
- `revision_history`: List of all values/dates for this fact

### 4. Enhance Query Methods

```python
def by_concept(self, concept: str, 
               deduplicate: bool = True,
               strategy: DeduplicationStrategy = DeduplicationStrategy.LATEST_FILING):
    """Filter by concept with optional deduplication."""
```

### 5. Financial Statement Assembly

For financial statements, implement smart deduplication:

```python
def _prepare_statement_facts(self, facts: List[FinancialFact]) -> List[FinancialFact]:
    """Prepare facts for financial statement display."""
    # Group by concept and period
    grouped = defaultdict(list)
    for fact in facts:
        key = (fact.concept, fact.period_start, fact.period_end)
        grouped[key].append(fact)
    
    # Select best fact for each group
    deduped = []
    for facts in grouped.values():
        if len(facts) > 1:
            # Sort by filing date desc, prefer 10-K over 10-Q
            facts.sort(key=lambda f: (f.filing_date, f.form_type == '10-K'), 
                      reverse=True)
        deduped.append(facts[0])
    
    return deduped
```

## Impact on Financial Statements

### Current Issues
1. **Duplicate Rows**: Same line item appears multiple times
2. **Incorrect Totals**: Summing duplicates gives wrong results  
3. **Period Confusion**: Multiple values for same period

### With Proper Handling
1. **Clean Statements**: One value per concept per period
2. **Accurate Analysis**: Correct calculations and ratios
3. **Audit Trail**: Track which filing provided each number

## Best Practices

1. **Always Deduplicate for Display**: Financial statements should show one value per cell
2. **Preserve History for Analysis**: Keep all facts but mark which is "current"
3. **Document Selection**: Make it clear which filing/value was chosen
4. **Allow Override**: Let users choose different selection strategies
5. **Handle Amendments**: Prefer 10-K/A over 10-K when newer

## Implementation Priority

1. **High**: Fix `income_statement()` and `cash_flow()` to deduplicate
2. **High**: Add deduplication to `pivot_by_period()`
3. **Medium**: Enhance `FactQuery` with strategy parameter
4. **Low**: Add lineage tracking and restatement detection