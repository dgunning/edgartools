# Issue #452: DNUT Revenue Value Discrepancy - Complete Root Cause Analysis

**GitHub Issue**: https://github.com/dgunning/edgartools/issues/452
**Reporter**: staplestack
**Status**: Root cause identified - SEC Facts API data inconsistency
**Priority**: Moderate - Affects companies with fiscal year-end changes

## Executive Summary

EdgarTools is showing $1.530B for DNUT's FY 2023 revenue instead of the correct $1.686B. The root cause is **inconsistent fiscal_year assignments in the SEC Company Facts API** when companies change their fiscal year-end dates. The same period (ending Jan 1, 2023) appears with three different fiscal_year values (2022, 2023, 2024) across different filings.

## Investigation Results

### User Report
- **Company**: Krispy Kreme (DNUT)
- **Expected**: $1.686B revenue for FY 2023
- **Actual**: $1.530B revenue shown as FY 2023
- **Hypothesis**: "Latest 10-K filing has both dec 1 2023 and jan 1 2023" ✓ Confirmed

### Fiscal Year-End Change

Krispy Kreme changed their fiscal year-end:
- **Old FYE**: Early January (e.g., Jan 1, 2023)
- **New FYE**: Late December (e.g., Dec 31, 2023)

This transition created two periods in 2023:
1. Jan 2, 2023 - Jan 1, 2023 (363 days) → Should be FY 2022
2. Jan 2, 2023 - Dec 31, 2023 (363 days) → Should be FY 2023

### The SEC Facts API Issue

The SEC Company Facts API returns **duplicate periods with conflicting fiscal_year values**:

```
Period ending 2023-12-31 (correct value: $1.686B):
├─ fiscal_year=2023, filing=2024 10-K → ✓ CORRECT
├─ fiscal_year=2024, filing=2024 10-K → Comparative data
└─ fiscal_year=2024, filing=2024 10-K → Duplicate

Period ending 2023-01-01 (value: $1.530B):
├─ fiscal_year=2022, filing=2023 10-K → ✓ CORRECT
├─ fiscal_year=2023, filing=2023 10-K → ✗ WRONG - Comparative mislabeled
├─ fiscal_year=2024, filing=2024 10-K → Comparative data
└─ fiscal_year=2024, filing=2024 10-K → Duplicate
```

### Why EdgarTools Shows the Wrong Value

The current period selection logic in `enhanced_statement.py`:

1. Groups facts by `(fiscal_year, fiscal_period, period_end)`
2. For annual periods, selects based on `period_end` year and filing_date
3. The period `(2023, 'FY', 2023-01-01)` is selected for "FY 2023"
4. This period has $1.530B revenue (should be FY 2022)

Meanwhile, the correct period `(2023, 'FY', 2023-12-31)` with $1.686B exists but may not be selected due to the period selection algorithm preferring earlier comparative filings.

## Root Cause Analysis

### Primary Issue
**SEC Company Facts API has inconsistent fiscal_year assignments** when:
- Companies change their fiscal year-end
- Comparative periods are included from multiple filings
- The same period_end appears in multiple annual filings

### Secondary Issue
**EdgarTools period selection doesn't validate fiscal_year against period_end**:
- A fiscal_year=2023 with period_end=2023-01-01 is invalid (too early)
- Should apply heuristics: fiscal_year should be within reasonable range of period_end.year

## Impact

### Affected Companies
1. **DNUT (Krispy Kreme)**: Fiscal year-end change from Jan to Dec
2. **Any company changing fiscal year-end**: Transition periods create duplicates
3. **52/53-week calendar companies**: May have similar issues if FYE shifts

### User Impact
- Incorrect financial values shown in statements
- Confusion when comparing to official SEC filings
- Potential for investment decisions based on wrong data

## Recommended Solution

### Approach: Validate fiscal_year Against period_end

Add validation logic in `enhanced_statement.py` to filter out invalid fiscal_year/period_end combinations:

```python
# After grouping periods, validate fiscal_year matches period_end
for pk, info in period_list:
    fiscal_year, fiscal_period, period_end = pk

    if annual and period_end:
        # fiscal_year should be within -1 to +1 years of period_end.year
        # Allow -1 for early-Jan fiscal year ends (Jan 2023 → FY 2022)
        # Allow +1 for late-Dec fiscal year ends (Dec 2022 → FY 2023)
        year_diff = fiscal_year - period_end.year

        # For periods ending Jan 1-7, expect fiscal_year = period_end.year - 1
        if period_end.month == 1 and period_end.day <= 7:
            if year_diff != -1 and year_diff != 0:
                continue  # Skip invalid combination

        # For all other periods, expect fiscal_year = period_end.year
        elif year_diff < -1 or year_diff > 1:
            continue  # Skip invalid combination
```

### Alternative: Prefer Primary Filing Over Comparatives

When multiple fiscal_years exist for the same period_end, prefer the one from the primary filing:

```python
# Group by period_end and select the correct fiscal_year
period_end_groups = defaultdict(list)
for pk, info in period_list:
    fiscal_year, fiscal_period, period_end = pk
    period_end_groups[period_end].append((pk, info))

# For each period_end, select the fiscal_year where
# filing_date is closest to period_end (primary filing)
selected_periods = []
for period_end, candidates in period_end_groups.items():
    # Find candidate where fiscal_year best matches period_end
    best_candidate = min(candidates,
                        key=lambda x: abs(x[0][0] - period_end.year))
    selected_periods.append(best_candidate)
```

## Next Steps

1. **Implement validation logic** to filter invalid fiscal_year/period_end pairs
2. **Add regression test** for DNUT and fiscal year-end changes
3. **Document SEC Facts API quirk** for future reference
4. **Consider filing a note** with SEC about inconsistent fiscal_year values in comparative periods

## Files for Reference

### Investigation Scripts
- `/Users/dwight/PycharmProjects/edgartools/tests/issues/reproductions/data-quality/issue_452_dnut_revenue_investigation.py`
- `/Users/dwight/PycharmProjects/edgartools/tests/issues/reproductions/data-quality/issue_452_period_selection_debug.py`
- `/Users/dwight/PycharmProjects/edgartools/tests/issues/reproductions/data-quality/issue_452_fiscal_year_mapping.py`
- `/Users/dwight/PycharmProjects/edgartools/tests/issues/reproductions/data-quality/issue_452_debug_period_info.py`

### Code Location
- **Bug location**: `/Users/dwight/PycharmProjects/edgartools/edgar/entity/enhanced_statement.py` lines 1088-1107

## SEC Company Facts API Example

Example data from https://data.sec.gov/api/xbrl/companyfacts/CIK0001857154.json:

```json
{
  "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": {
    "units": {
      "USD": [
        {
          "end": "2023-01-01",
          "val": 1529898000,
          "fy": 2022,  // Correct in 2022 filing
          "fp": "FY",
          "form": "10-K",
          "filed": "2023-03-01"
        },
        {
          "end": "2023-01-01",
          "val": 1529898000,
          "fy": 2023,  // WRONG - Comparative in 2023 filing
          "fp": "FY",
          "form": "10-K",
          "filed": "2024-02-28"
        },
        {
          "end": "2023-12-31",
          "val": 1686104000,
          "fy": 2023,  // Correct
          "fp": "FY",
          "form": "10-K",
          "filed": "2024-02-28"
        }
      ]
    }
  }
}
```

## Conclusion

This is a **data quality issue in the SEC Company Facts API** that EdgarTools must handle defensively. The SEC provides inconsistent fiscal_year values for comparative periods. EdgarTools should validate that fiscal_year aligns with period_end before using facts, and prefer primary filings over comparative data when conflicts exist.

The fix is straightforward but requires careful validation logic to handle edge cases like 52/53-week calendars and fiscal year-end changes.
