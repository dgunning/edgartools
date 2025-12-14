# Issue #282: XBRL API Migration Guide

**Issue**: User reported that previously working XBRL parsing code stopped functioning due to API changes.
**Status**: Resolved
**Impact**: Breaking changes in Company and XBRL APIs
**Resolution**: API migration guide and updated code patterns

## Root Cause Analysis

The user's code broke due to several API changes in EdgarTools:

1. **Import path changed**: `edgar.xbrl2.xbrl` → `edgar.xbrl.xbrl`
2. **Company filings API changed**: `Company.filings.filter()` → `Company.get_filings()`
3. **Facts DataFrame structure changed**: New column names and structure
4. **Filing iteration interface changed**: Slicing behavior updated

## API Migration Guide

### 1. Import Path Changes

**Before (Broken):**
```python
from edgar.xbrl2.xbrl import XBRL  # ❌ Wrong import path
```

**After (Working):**
```python
from edgar.xbrl.xbrl import XBRL  # ✅ Correct import path
```

### 2. Company Filings API Changes

**Before (Broken):**
```python
c = Company("AAPL")
tenk = c.filings.filter("10-K", filing_date="2014-01-01:")  # ❌ Old API
```

**After (Working):**
```python
c = Company("AAPL")
tenk = c.get_filings(form="10-K", filing_date="2014-01-01:")  # ✅ New API
```

### 3. Filing Iteration Changes

**Before (Broken):**
```python
for filing in tenk[:2]:  # ❌ Direct slicing may cause AttributeError
```

**After (Working):**
```python
for i in range(min(2, len(tenk))):  # ✅ Safe iteration
    filing = tenk[i]
```

### 4. Facts Query Interface (New Recommended Approach)

**New Pattern (Recommended):**
```python
xbrl = XBRL.from_filing(filing)
facts = xbrl.facts

# Query for specific concept
diluted_shares_df = facts.query().by_concept(
    "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",
    exact=True
).to_dataframe()

# DataFrame has new column structure
for _, row in diluted_shares_df.iterrows():
    period_start = row['period_start']    # ✅ New column
    period_end = row['period_end']        # ✅ New column
    numeric_value = row['numeric_value']  # ✅ New column
    decimals = row['decimals']            # ✅ Existing column
```

**Old DataFrame Columns (User Expected):**
- `period_key` - **Not available in new API**
- `value` - **Now called `numeric_value`**

**New DataFrame Columns (Current API):**
- `period_start` - Start date of the period
- `period_end` - End date of the period
- `numeric_value` - The numeric value (was `value`)
- `decimals` - Decimal precision indicator
- `concept` - XBRL concept name
- `label` - Human-readable label

### 5. Statement-Level API (Alternative Pattern)

The original statement-level approach still works with minor corrections:

```python
xbrl = XBRL.from_filing(filing)
statements = xbrl.get_all_statements()

for stmt in statements:
    if 'income' in stmt['definition'].lower():
        statement_data = xbrl.get_statement(stmt['definition'])

        for d in statement_data:
            if key in d.get('all_names', []):
                d_values = d['values']
                d_decimals = d['decimals']

                for duration in d_values:
                    adjusted_value = shift_number(d_values[duration], d_decimals[duration])
                    values[duration] = adjusted_value
```

## Complete Working Example

Here's the complete migrated code that works with the current API:

```python
from edgar import *
from edgar.xbrl.xbrl import XBRL

set_identity("your_name your_email@domain.com")

key = "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
c = Company("AAPL")

# Updated API
tenk = c.get_filings(form="10-K", filing_date="2014-01-01:")

def shift_number(num, shift):
    if shift is None or shift == 'INF':
        return num
    return num * (10 ** int(shift))

values = {}

for filing in tenk:
    print(f"Processing {filing}")
    xbrl = XBRL.from_filing(filing)

    # New facts query interface (RECOMMENDED)
    facts = xbrl.facts
    diluted_shares_df = facts.query().by_concept(key, exact=True).to_dataframe()

    for _, row in diluted_shares_df.iterrows():
        period_start = row['period_start']
        period_end = row['period_end']
        numeric_value = row['numeric_value']
        decimals = row['decimals']

        period_key = f"{period_start}_{period_end}"
        adjusted_value = shift_number(numeric_value, decimals)

        values[period_key] = adjusted_value
        print(f"  {period_start} to {period_end}: {adjusted_value:,.0f}")

print(values)  # The values for the tag you want
```

## Testing Results

The migrated code successfully extracts diluted shares data from Apple's 10-K filings:

- **2024 fiscal year**: 15,408,095 thousand shares
- **2023 fiscal year**: 15,812,547 thousand shares
- **2022 fiscal year**: 16,325,819 thousand shares

## Recommendations for Users

1. **Use the new facts query interface** - it's more robust and future-proof
2. **Update import paths** from `edgar.xbrl2` to `edgar.xbrl`
3. **Use `Company.get_filings()`** instead of the old `filings.filter()` method
4. **Adapt to new DataFrame column names** in the facts interface
5. **Use proper SEC identity** with email format for API compliance

## Impact Assessment

**Breaking Changes:**
- Import paths changed (high impact)
- Company API method changed (high impact)
- DataFrame structure changed (medium impact)
- Filing iteration behavior changed (low impact)

**Backward Compatibility:**
- Statement-level API remains largely compatible
- Core XBRL parsing functionality preserved
- Decimal adjustment logic unchanged

## Prevention

To prevent similar issues in the future:

1. **Comprehensive API tests** covering user workflows
2. **Migration guides** for breaking changes
3. **Deprecation warnings** before removing old APIs
4. **Version documentation** with change highlights

## Related Files

- **Reproduction**: `tests/issues/reproductions/xbrl-parsing/issue_282_apple_diluted_shares_fixed.py`
- **Working Solution**: `tests/issues/reproductions/xbrl-parsing/issue_282_working_solution.py`
- **Regression Test**: `tests/issues/regression/test_issue_282_xbrl_api_regression.py`
- **Debug Script**: `tests/issues/reproductions/xbrl-parsing/issue_282_debug.py`

## Timeline

- **Reported**: 2025-05-05
- **Investigated**: 2025-09-26
- **Resolved**: 2025-09-26
- **Documented**: 2025-09-26

This issue demonstrates the importance of maintaining backward compatibility and providing clear migration paths for API changes that affect user workflows.