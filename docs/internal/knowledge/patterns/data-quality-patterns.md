# Data-Quality Issue Patterns

Analysis of 13 issues in the data-quality category.

## Common Companies Affected
- **AAPL**: 6 issues
- **XBRLS**: 5 issues
- **NVDA**: 2 issues
- **XOM**: 1 issues
- **AMD**: 1 issues

## Typical Form Types
- **10-K**: 9 issues
- **10-Q**: 2 issues

## Common Error Types

## Frequently Used APIs
- **income_statement**: 10 usages
- **Company"[^"]+)")**: 9 usages
- **.latest**: 8 usages
- **get_filings**: 7 usages
- **.statements.**: 7 usages

## Data Quality Issues  
5 out of 13 issues show data quality concerns.

## Issue Numbers
[298, 322, 329, 339, 339, 341, 342, 349, 350, 352, 362, 405, 408, 412]

## New Patterns Identified

### Issue #412: Revenue Data Access Confusion
- **Pattern**: Users confusing annual vs quarterly revenue values
- **Root Cause**: AAPL 2020 annual revenue ($274.5B) ÷ 4 ≈ $68.6B appears "quarterly"  
- **Solution**: User education on dataframe column structure (year-based columns contain annual values)
- **Fix**: Enhanced documentation with clear examples of revenue data access patterns

### Issue #412: Historical SGML Parsing Failures  
- **Pattern**: "Unknown SGML format" errors for older filings (2019-2020 TSLA)
- **Root Cause**: Version/environment conflicts in SGML parser detection logic
- **Investigation**: Manual parsing works correctly, but `filing.sgml()` method fails
- **Workaround**: Company Facts API can serve as fallback for historical data access
- **Status**: Requires further investigation of version-specific SGML parsing differences

## Recommendations
Based on the patterns identified:

1. **Testing Focus**: Prioritize testing with AAPL filings
2. **Form Coverage**: Ensure robust handling of 10-K forms
3. **Error Handling**: Improve error handling for common errors
4. **API Robustness**: Focus on income_statement reliability
