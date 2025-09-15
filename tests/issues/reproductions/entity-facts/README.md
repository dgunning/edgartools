# Entity Facts API Issue Reproduction

This directory contains reproduction scripts and tests for issues with EdgarTools' Facts API integration.

## What Is The Facts API?

The SEC Facts API provides structured, pre-processed financial data accessed through EdgarTools' `edgar.entity` module. This is the data source used by:

- `Company.income_statement()`
- `Company.balance_sheet()`  
- `Company.cash_flow()`
- `Company.financials`

## Files In This Directory

### Issue #412 - Missing Historical Balance Sheet Data
- `412-FactsAvailability.py` - Facts availability analysis
- `412-FactsForCompanies.py` - Company-specific facts testing
- `test_412_regression.py` - Regression tests ensuring fix continues working

**Problem:** Historical years (2021-2022) showed sparse data (~2% completeness) instead of comprehensive balance sheet data, despite comprehensive data being available in Facts API.

**Root Cause:** Period selection logic prioritized recent filing dates over data completeness, selecting amended filings with sparse comparative data.

**Fix:** Implemented "Recency + Availability" approach with ≥5 facts threshold in `enhanced_statement.py`.

### Issue #438 - NVDA Revenue Missing/Duplicated  
- `438-nvda-revenue-missing.py` - Original issue reproduction
- `438-facts-api-verification.py` - Fix verification test
- `test_fix_438.py` - Statement mapping fix test
- `test_integration_438_fix.py` - Integration test for fix
- `test_nvda_2020_duplicate_issue.py` - Duplicate detection test
- `nvda-income.py` - Simple NVDA income statement test

**Problem:** NVDA income statement showed "Total Revenue" only in FY 2020 column, missing in recent years. When fixed, created duplicate entries.

**Root Cause:** Facts API used different code path than XBRL, requiring separate concept mapping and deduplication logic.

**Fix:** Added 'Revenues': 'IncomeStatement' to STATEMENT_MAPPING and implemented intelligent revenue deduplication in Facts API path.

## Testing Guidelines

- All regression tests must use `@pytest.mark.regression` decorator
- Tests should not hardcode specific years but check relative periods (3rd-5th columns)
- Focus on data completeness thresholds (>40% for historical periods)
- Verify both programmatic access and rich output (__rich__ method)

## Facts API vs XBRL API

**Facts API** (this directory):
- Pre-processed, standardized data
- Better performance for multi-year analysis  
- Accessed via Company methods
- Period selection and concept mapping handled by EdgarTools

**XBRL API** (../xbrl-parsing/):
- Raw XBRL document parsing
- Full dimensional information available
- Accessed via filing.xbrl() methods  
- Direct control over parsing and filtering

Choose the appropriate directory based on which data source the issue affects.