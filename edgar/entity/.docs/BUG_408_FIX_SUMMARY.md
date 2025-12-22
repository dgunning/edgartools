# Bug #408 Fix Summary - Annual Period Selection Issue

## Executive Summary
Fixed a critical bug where Apple's (and other companies') annual financial statements were showing quarterly values ($64B) instead of annual values ($274B) for years 2019-2020.

## The Bug
**Issue**: `Company("AAPL").facts.income_statement(annual=True)` returned:
- FY 2020: $64.6B (Q4 only) ❌
- FY 2019: $64.0B (Q4 only) ❌

**Expected**:
- FY 2020: $274.5B (Full year) ✓
- FY 2019: $260.2B (Full year) ✓

## Root Cause Analysis

### 1. SEC Facts API Data Structure
The SEC Facts API contains multiple versions of the same fact:
- **Annual facts**: 363-365 day duration, full fiscal year values
- **Quarterly facts**: ~90 day duration, single quarter values
- **Both marked as `fiscal_period="FY"`** in the same filing

Example for Apple FY 2020:
```
FY 2020, ends 2020-09-26: $274,515,000,000 (duration: 363 days) ✓
FY 2020, ends 2020-09-26: $64,698,000,000 (duration: 90 days) ✗
```

### 2. Initial Deduplication Problem
The code was deduplicating facts by `(fiscal_year, fiscal_period)` key, which:
- Lost multiple period_end variations
- Arbitrarily kept the first fact encountered
- Often selected quarterly instead of annual values

### 3. Comparative Data Complexity
Each fiscal year can have multiple period_end dates:
```
FY 2024 → ends 2024-09-28 (current year)
FY 2024 → ends 2023-09-30 (1-year comparative)
FY 2024 → ends 2022-09-24 (2-year comparative)
```

## The Solution

### Code Changes Made

**File**: `edgar/entity/enhanced_statement.py`

#### 1. Preserve All Period Variations (Line 952)
```python
# OLD: period_key = (fact.fiscal_year, fact.fiscal_period)
# NEW: 
period_key = (fact.fiscal_year, fact.fiscal_period, fact.period_end)
```

#### 2. Duration-Based Period Selection (Lines 975-1029)
```python
# Filter for TRUE annual periods using duration
for pk, info in period_list:
    if sample_fact.period_start and sample_fact.period_end:
        duration = (sample_fact.period_end - sample_fact.period_start).days
        if duration > 300:  # This is truly annual
            true_annual_periods.append((pk, info))
```

#### 3. Flexible Year Matching (Lines 988-994)
```python
# Allow fiscal_year within reasonable range of period_end.year
year_diff = fiscal_year - period_end_date.year
if year_diff < -1 or year_diff > 3:
    continue  # Too far off to be valid
```

#### 4. Duration-Based Fact Filtering (Lines 1036-1047)
```python
# Filter facts within each period to only include annual duration
if fact.period_start and fact.period_end:
    duration = (fact.period_end - fact.period_start).days
    if duration > 300:
        filtered_facts.append(fact)
```

#### 5. Proper Period Labeling (Lines 1039-1041)
```python
# Use actual period year in labels
if annual and info.get('is_annual') and pk[2]:
    label = f"FY {pk[2].year}"
```

## Debug Process Issues

### Files Created in Root Directory (Suboptimal)
During debugging, we created multiple test files in the project root:
- `debug_apple_periods.py`
- `debug_apple_periods2.py` 
- `debug_fix_test.py`
- `debug_fix_test2.py`
- `debug_dedup_issue.py`
- `debug_duration_fix.py`
- `debug_statement_building.py`
- `debug_final_check.py`
- `debug_duplicate_facts.py`
- `check_period_ends.py`
- `analyze_period_durations.py`
- `test_solution_edge_cases.py`
- `test_edge_cases_detailed.py`
- `verify_fiscal_year_pattern.py`

**Total: 14 debug files in root** 🚫

### Recommended Debug Process Improvements

#### 1. Use Dedicated Debug Directory
```bash
# Create structure
edgar/entity/.docs/debug/      # Ephemeral debug scripts (gitignored)
gists/bugs/reproductions/       # Minimal bug reproductions
gists/bugs/fixed/              # Archived fixed bugs
```

#### 2. Debug Script Naming Convention
```
BUG_408_01_initial_check.py
BUG_408_02_period_analysis.py
BUG_408_03_duration_test.py
```

#### 3. Clean Up Protocol
```python
# Add to .git/info/exclude
edgar/**/.docs/debug/
**/BUG_*_*.py
**/debug_*.py
```

#### 4. Debug Documentation Template
```python
"""
Bug: #408 - Annual period selection
Step: 01 - Initial reproduction
Expected: Annual revenue ~$274B
Actual: Quarterly revenue $64B
"""
```

## Testing Coverage Gaps

### What We Tested
✅ Apple (Sept year-end)
✅ Microsoft (June year-end)
✅ Walmart (Jan year-end)
✅ Duration edge cases
✅ Leap year impact
✅ Multiple fiscal year patterns

### What We Should Test Systematically
```python
# tests/test_entity_facts_period_selection.py
def test_annual_vs_quarterly_duration_filtering():
    """Ensure annual=True returns full year, not quarterly"""
    
def test_fiscal_year_boundary_companies():
    """Test companies with non-calendar fiscal years"""
    
def test_comparative_period_deduplication():
    """Ensure we pick current year, not comparatives"""
```

## Architecture Recommendations

### 1. Data Model Enhancement
Consider adding to `FinancialFact`:
```python
@property
def is_annual(self) -> bool:
    """True if fact represents annual period (>300 days)"""
    if self.period_start and self.period_end:
        return (self.period_end - self.period_start).days > 300
    return self.fiscal_period == 'FY'

@property
def period_duration_days(self) -> Optional[int]:
    """Duration in days if available"""
    if self.period_start and self.period_end:
        return (self.period_end - self.period_start).days
    return None
```

### 2. Facts Loading Strategy
Consider pre-filtering at load time:
```python
class EntityFactsParser:
    def _filter_duplicate_periods(self, facts):
        """Remove quarterly facts marked as FY"""
        # Group by (fiscal_year, fiscal_period, period_end)
        # Keep only annual duration for FY periods
```

### 3. Configuration Options
```python
class EntityFacts:
    def income_statement(
        self,
        annual: bool = True,
        min_annual_days: int = 300,  # Configurable threshold
        prefer_latest_filing: bool = True,  # Dedup strategy
    ):
```

## Key Learnings

### 1. SEC Data Quirks
- Facts marked as "FY" can be quarterly (90 days) or annual (363+ days)
- Multiple versions exist from comparative filings
- Fiscal year field doesn't always match period_end year

### 2. Duration is King
- Period duration is the most reliable indicator
- Annual: 363-365 days (sometimes 370 for leap years)
- Quarterly: 88-91 days
- Use >300 days as safe threshold for annual

### 3. Testing with Real Data
- Bug reproductions in `gists/bugs/` are invaluable
- Need diverse company set (different fiscal year ends)
- Edge cases matter (leap years, amendments, restatements)

## Action Items for edgartools-architect

1. **Organize Debug Workflow**
   - Create `.docs/debug/` directory structure
   - Add debug script templates
   - Document debug best practices in CLAUDE.md

2. **Improve Test Coverage**
   - Add regression test for bug #408
   - Create period selection test suite
   - Add property-based tests for duration logic

3. **Refactor Period Selection**
   - Consider extracting to dedicated class
   - Add logging for debugging
   - Make thresholds configurable

4. **Documentation**
   - Update entity/CLAUDE.md with period selection details
   - Add FAQ about SEC data quirks
   - Document duration-based filtering approach

5. **Performance Optimization**
   - Cache duration calculations
   - Pre-filter at parse time
   - Consider indexing by (period_end.year, duration)

## Conclusion

The fix successfully resolves the issue by:
1. Preserving all fact variations during loading
2. Using duration (>300 days) as primary filter for annual data
3. Properly deduplicating by actual period year
4. Filtering facts within periods by duration

The solution is robust across different companies and fiscal year ends, but the debug process revealed opportunities for better organization and testing practices.

---
*Generated: 2024-11-27*
*Bug: #408*
*Fixed in: edgar/entity/enhanced_statement.py*