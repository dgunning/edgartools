# Issue #412 Regression Tests - TSLA Data Access

## Problem Summary
- **Original Issue**: "TSLA revenue just isn't there from 2019 to 2022"
- **Root Cause**: SGML parsing failed on XBRL inline content with multiple '>' characters
- **Error**: `ValueError: too many values to unpack (expected 2)`

## Solution Implemented
- **File**: `edgar/sgml/sgml_header.py`
- **Fix**: Changed `line.split('>')` to `line.split('>', 1)` to split only on first '>' character
- **Impact**: Unlocked access to Tesla financial data for years 2019-2022

## Regression Tests

### `test_issue_412_tsla_data_access_regression.py`

1. **`test_sgml_parsing_fix_regression()`** - Core unit test
   - Tests SGML parsing with problematic XBRL inline content
   - Ensures "too many values to unpack" error doesn't return
   - **Status**: ✅ Passes

2. **`test_issue_412_solution_demonstrates_fix()`** - Solution verification
   - Tests the complete parsing pipeline 
   - Verifies our solution approach works
   - **Status**: ✅ Passes

3. **Integration tests** - Live API tests (may be skipped)
   - Tests actual TSLA filing access
   - May skip due to network/API limitations in CI
   - **Status**: ⚠️ Environment dependent

## Verification Scripts

### Working Demo Scripts
- **`simple_tsla_demo.py`** - Shows TSLA data is now accessible
- **`view_tsla_financials_fixed.py`** - Displays actual financial data
- **`tests/issues/reproductions/data-quality/issue_412_solution_and_examples.py`** - Complete solution demo

### Expected Results
All scripts should show successful XBRL access for TSLA 2019-2022:
```
✅ 2019: 2,093 XBRL facts accessible
✅ 2020: 2,087 XBRL facts accessible  
✅ 2021: 2,093 XBRL facts accessible
✅ 2022: 1,898 XBRL facts accessible
```

## Key Files Created/Modified

### Tests
- `tests/issues/regression/test_issue_412_tsla_data_access_regression.py` - Regression test suite
- `tests/issues/regression/test_issue_412_revenue_data_access.py` - Revenue access tests
- `tests/test_filing_sgml.py` - SGML parsing unit test

### Test Data  
- `data/sgml/0001564590-20-004475-minimal.txt` - Minimal test file (5KB vs 20MB original)

### Bug Fix
- `edgar/sgml/sgml_header.py` - Core SGML parsing fix

### Documentation/Demos
- `simple_tsla_demo.py` - Impact demonstration
- `view_tsla_financials_fixed.py` - Financial data display
- `tests/issues/reproductions/data-quality/issue_412_solution_and_examples.py` - Complete solution

## Regression Prevention

The regression tests ensure that:
1. **No specific parsing error return**: The "too many values to unpack" error is caught
2. **Solution continues working**: Our documented solution approach is validated
3. **Integration remains functional**: Live API access is tested when possible

## Impact Verification

✅ **RESOLVED**: TSLA financial data 2019-2022 is now accessible  
✅ **VERIFIED**: Revenue data can be extracted from all test years  
✅ **PROTECTED**: Regression tests prevent future breakage of this fix