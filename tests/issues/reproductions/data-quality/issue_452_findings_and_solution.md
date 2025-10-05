# Issue #452: DNUT Revenue Value Discrepancy - Root Cause Analysis and Solution

**GitHub Issue**: https://github.com/dgunning/edgartools/issues/452
**Reporter**: staplestack
**Category**: Data Quality - Fiscal Year Labeling
**Severity**: Moderate - Affects companies with 52/53-week fiscal calendars ending in early January

## Executive Summary

EdgarTools is incorrectly labeling fiscal years for Krispy Kreme (DNUT), resulting in the wrong revenue values being displayed. The period ending January 1, 2023 (fiscal year 2022) is being labeled as "FY 2023", causing the system to show $1.530B in revenue instead of the correct $1.686B.

## Issue Details

### User Report
- **Company**: Krispy Kreme (DNUT)
- **Form**: 10-K FY2023
- **Expected Revenue**: $1.686B
- **Actual Revenue Shown**: $1.530B
- **User Hypothesis**: "Latest 10-K filing has both dec 1 2023 and jan 1 2023 so this is probably the source of the error"

### Investigation Findings

The user's hypothesis was correct - DNUT changed their fiscal year-end from early January to late December:

| Period Start | Period End | Duration | Actual FY | EdgarTools Label | Revenue |
|--------------|------------|----------|-----------|------------------|---------|
| 2022-01-03 | 2023-01-01 | 363 days | **FY 2022** | FY 2023 (WRONG) | $1.530B |
| 2023-01-02 | 2023-12-31 | 363 days | **FY 2023** | FY 2023 (skipped) | $1.686B |
| 2024-01-01 | 2024-12-29 | 363 days | **FY 2024** | FY 2024 (correct) | $1.665B |

### Root Cause

Located in `/Users/dwight/PycharmProjects/edgartools/edgar/entity/enhanced_statement.py` at **line 1094**:

```python
# Use the actual period year instead of fiscal year in the label
label = f"FY {pk[2].year}"  # pk[2] is period_end
```

This logic uses `period_end.year` to generate the fiscal year label. For most companies this works, but fails for:

1. **52/53-week fiscal calendars ending in early January**: A period ending January 1, 2023 is labeled "FY 2023" but is actually FY 2022 (the prior calendar year).

2. **Fiscal year-end changes**: When companies change their fiscal year-end (as DNUT did), the simple period_end.year logic creates collisions where two different periods get the same label.

## Why This Matters

### Accounting Standard
According to US fiscal year conventions:
- A fiscal year ending January 1-7 of year N is considered the fiscal year ending in year N-1
- This is because the vast majority of the fiscal year occurred in the prior calendar year
- Example: Fiscal year ending January 1, 2023 → FY 2022

### Impact
- **DNUT and similar companies**: Shows incorrect revenue values
- **52/53-week retailers**: Many retail companies use 52/53-week calendars ending in early January (e.g., Walmart, Target, Best Buy)
- **Fiscal year changes**: Any company changing their fiscal year-end dates

## Proposed Solution

### Option 1: Use fiscal_year from Facts API (Recommended)

The SEC's Company Facts API already provides the correct `fiscal_year` field. We should use this instead of calculating from dates:

```python
# In enhanced_statement.py, line 1094
# BEFORE:
label = f"FY {pk[2].year}"  # Uses period_end.year

# AFTER:
label = f"FY {info['fiscal_year']}"  # Uses fact.fiscal_year from SEC
```

**Pros**:
- Matches SEC's official fiscal year designation
- Handles all edge cases (52/53-week calendars, fiscal year changes, etc.)
- Simple one-line fix

**Cons**:
- None - this is the authoritative source

### Option 2: Smart Date Logic (Fallback)

If fiscal_year is unavailable, use smart logic for period_end dates in early January:

```python
if annual and info.get('is_annual') and pk[2]:  # pk[2] is period_end
    period_end = pk[2]

    # Use fiscal_year from facts if available (most reliable)
    if 'fiscal_year' in info and info['fiscal_year']:
        label = f"FY {info['fiscal_year']}"
    # For periods ending Jan 1-7, use prior year (52/53-week calendar convention)
    elif period_end.month == 1 and period_end.day <= 7:
        label = f"FY {period_end.year - 1}"
    else:
        label = f"FY {period_end.year}"
else:
    label = info['label']
```

### Option 3: Detect Duplicates and Use Latest

When multiple periods map to the same fiscal year, prefer the one with the latest filing_date:

```python
# After creating labels, detect duplicates and keep most recent
seen_labels = {}
for i, (period_key, info) in enumerate(selected_period_info):
    label = f"FY {period_end.year}"  # Initial label

    if label in seen_labels:
        # Duplicate found - compare filing dates
        existing_idx = seen_labels[label]
        if info['filing_date'] > selected_period_info[existing_idx][1]['filing_date']:
            # Current period is more recent, replace
            seen_labels[label] = i
        # else: keep existing
    else:
        seen_labels[label] = i
```

## Recommended Fix

**Use Option 1** (fiscal_year from SEC) as the primary solution, with Option 2 as a fallback for edge cases.

## Testing

### Test Case 1: DNUT Fiscal Year Change
```python
def test_dnut_fiscal_year_labeling():
    """Test that DNUT revenue values are correctly labeled after fiscal year change"""
    company = Company("DNUT")
    income_stmt = company.income_statement(periods=5, annual=True)
    income_df = income_stmt.to_dataframe()

    # FY 2023 should show $1.686B (period ending Dec 31, 2023)
    # NOT $1.530B (period ending Jan 1, 2023, which is FY 2022)
    fy_2023_revenue = income_df.loc[
        income_df['label'].str.contains('Total Revenue'), 'FY 2023'
    ].values[0]

    assert abs(fy_2023_revenue - 1_686_104_000) < 1_000_000, \
        f"FY 2023 revenue should be ~$1.686B, got ${fy_2023_revenue:,.0f}"
```

### Test Case 2: 52/53-Week Retailer (e.g., Walmart)
```python
def test_52_week_fiscal_year_labeling():
    """Test fiscal year labeling for 52/53-week calendar companies"""
    company = Company("WMT")  # Walmart, FYE typically late January
    income_stmt = company.income_statement(periods=3, annual=True)
    income_df = income_stmt.to_dataframe()

    # Verify that periods ending in January are labeled with prior year
    # e.g., period ending Jan 31, 2023 should be labeled "FY 2023" (correct)
    # but period ending Jan 3, 2023 should be labeled "FY 2022"
```

## Files Modified

1. `/Users/dwight/PycharmProjects/edgartools/edgar/entity/enhanced_statement.py` - Line 1094
   - Update fiscal year label calculation to use `fiscal_year` from facts

2. `/Users/dwight/PycharmProjects/edgartools/tests/test_entity_facts.py` - Add regression tests
   - Test DNUT fiscal year change scenario
   - Test 52/53-week calendar labeling

## Additional Notes

### Why the User Saw the Issue
The user was looking at the most recent 10-K filing (FYE 2024-12-29), which contains comparative periods:
- FY 2024 (ending Dec 29, 2024) - Correctly labeled, shows $1.665B ✓
- FY 2023 (ending Dec 31, 2023) - Should show $1.686B but was SKIPPED
- FY 2022 (ending Jan 1, 2023) - Incorrectly labeled as "FY 2023", shows $1.530B ✗

### Similar Companies at Risk
Companies with 52/53-week fiscal calendars ending in early January:
- Walmart (WMT) - Ends late January/early February
- Target (TGT) - Ends early February
- Best Buy (BBY) - Ends early February
- Home Depot (HD) - Ends early February
- Lowe's (LOW) - Ends early February

### SEC Facts API Behavior
The SEC Company Facts API correctly identifies fiscal years even with calendar changes:
- `fiscal_year`: The official fiscal year designation
- `fiscal_period`: "FY" for annual, "Q1-Q4" for quarterly
- `period_end`: The actual period ending date

EdgarTools should trust the SEC's `fiscal_year` field as the source of truth.

## References

- SEC Company Facts API: https://data.sec.gov/api/xbrl/companyfacts/CIK0001857154.json
- DNUT 10-K Filing (FY 2024): https://www.sec.gov/ix?doc=/Archives/edgar/data/0001857154/000185715425000013/dnut-20241229.htm
- 52/53-week fiscal year convention: https://en.wikipedia.org/wiki/Fiscal_year#52-53-week_fiscal_year
