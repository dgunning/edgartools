# Cell Shifting Behavior Analysis

## Summary

The `preprocess_currency_cells()` and `preprocess_percent_cells()` functions from `llm_extraction.py` merge adjacent cells (e.g., `$` + `100` → `$100`) and adjust colspan to maintain table width.

## How It Works

1. **Scans each row** for currency/percent symbols in standalone cells
2. **Merges with next cell**: `$` cell + `100` cell → `$100` cell
3. **Adjusts colspan**: Increases merged cell colspan by 1
4. **Removes original symbol cell**: Deletes the `$` cell from DOM

## Test Results

### ✅ Test Case 1: Basic Currency (SAFE)
- All rows have `$` in same positions
- **Result**: Perfect alignment maintained (5 columns)
- **Pattern**: Consistent structure across all rows

### ✅ Test Case 2: Mixed Currency/Percent (SAFE)
- Different rows have `$` or `%` but in consistent positions
- **Result**: All rows maintain 3 columns
- **Pattern**: Each row type has consistent structure

### ⚠️ Test Case 3: Irregular Structure (UNSAFE)
- Row 1: 4 columns, Row 2: 5 columns (extra cell), Row 3: 4 columns
- **Result**: Row 2 becomes 5 columns after shifting, others stay 4
- **Problem**: Inconsistent initial structure

### ⚠️ Test Case 4: Mixed Presence (UNSAFE)
- Some rows have `$` pattern, some have `$` already in text (`$45.50`)
- **Result**: Misalignment (2, 2, 3 columns)
- **Problem**: Not all rows follow the pattern

### ⚠️ Test Case 5: Header Mismatch (UNSAFE)
- Header has no `%` to shift, data rows do
- **Result**: Header stays 3 columns, data becomes 5 columns
- **Problem**: Header doesn't match data pattern

### ✅ Test Case 6: Real-World Financial Statement (SAFE)
- All data rows have consistent `$` positions
- Header uses colspan=2 to pre-align with data structure
- Mixed currency and percent in different rows
- **Result**: Perfect alignment (all rows = 5 columns)
- **Pattern**: Real SEC filing structure

## Critical Insights

### When SAFE to Use:
1. ✅ **Financial statement tables** - All data rows have identical structure
2. ✅ **SEC filing tables** - Headers use colspan to align with data
3. ✅ **Homogeneous tables** - All rows follow same pattern

### When UNSAFE:
1. ❌ **Mixed structures** - Some rows have pattern, some don't
2. ❌ **Irregular layouts** - Varying cell counts per row
3. ❌ **Pre-merged data** - Currency already in values (`$45.50`)

## Recommendation for EdgarTools

**SAFE for our use case** because:
- SEC financial statements have consistent row structure
- Real-world test (Case 6) passes perfectly
- This is exactly the pattern in actual 10-K/10-Q filings

**Implementation strategy**:
- Apply preprocessing by default for LLM optimization
- Add validation check (optional): Verify all data rows have same pre-shift width
- Document the assumptions clearly

## Example: Real Financial Table

**Before shifting**:
```
| Line Item       | $ | Amount  | $ | Amount |  (5 cells → 5 logical columns)
| Revenue         | $ | 100,000 | $ | 90,000 |  (5 cells → 5 logical columns)
| Gross Margin    | 40| %       | 39| %      |  (5 cells → 5 logical columns)
```

**After shifting**:
```
| Line Item       | $Amount     | $Amount     |  (3 cells with colspan → 5 logical columns)
| Revenue         | $100,000    | $90,000     |  (3 cells with colspan → 5 logical columns)
| Gross Margin    | 40%         | 39%         |  (3 cells with colspan → 5 logical columns)
```

**Key**: Total logical columns stays at 5 because colspan adjustment compensates.

## Conclusion

✅ **Safe to implement** for EdgarTools with LLM optimization
✅ **Real SEC filings match the working pattern**
⚠️ **Document assumptions** and add optional validation
