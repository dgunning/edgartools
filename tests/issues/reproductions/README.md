# EdgarTools Issue Reproduction Files

This directory contains reproduction scripts and tests for reported issues in EdgarTools. The files are organized by the type of data source they test.

## Directory Structure

### `/entity-facts/` - Facts API Issues
Files testing issues with the SEC Facts API data source (`edgar.entity` module).

**What goes here:**
- Issues with `Company.income_statement()`, `Company.balance_sheet()`, `Company.cash_flow()` methods
- Facts API data completeness or accuracy problems  
- Period selection issues in Facts API data
- Revenue classification and deduplication issues
- Historical data availability problems

**Examples:**
- Issue #412: Missing historical balance sheet data (Facts API period selection)
- Issue #438: NVDA revenue missing (Facts API concept mapping)

### `/xbrl-parsing/` - XBRL Document Issues  
Files testing issues with direct XBRL document parsing (`edgar.xbrl` module).

**What goes here:**
- Issues with `filing.xbrl()` and XBRL statement parsing
- XBRL presentation tree problems
- Dimensional data filtering issues
- XBRL concept mapping problems
- Statement classification issues in XBRL documents

**Examples:**
- Issue #427: XBRL data parsing inconsistencies
- Issue #429: Statement regression in XBRL parsing

### `/data-quality/` - Cross-API Data Quality
Files testing data quality, consistency, and accuracy across both APIs.

**What goes here:**
- Multi-year financial data consistency
- Cross-validation between XBRL and Facts APIs
- Financial metrics accuracy tests
- Data standardization issues

### `/performance/` - Performance Issues
Files testing performance bottlenecks and optimization.

### `/filing-access/` - Filing Access Issues  
Files testing filing retrieval, caching, and access problems.

## File Naming Conventions

- **Reproduction scripts**: `XXX-descriptive-name.py` (e.g., `438-nvda-revenue-missing.py`)
- **Regression tests**: `test_XXX_regression.py` (e.g., `test_438_regression.py`)
- **Investigation files**: `XXX-investigation-type.py` (e.g., `438-concept-mapping-debug.py`)

## EdgarTools Data Sources

EdgarTools provides financial data from two distinct sources:

1. **Facts API** (`edgar.entity` module)
   - SEC's structured facts endpoint
   - Accessed via `Company.income_statement()`, `Company.balance_sheet()`, etc.
   - Pre-processed, standardized data
   - Better for multi-year analysis and comparisons

2. **XBRL API** (`edgar.xbrl` module)  
   - Direct XBRL document parsing
   - Accessed via `filing.xbrl()` and statement methods
   - Raw XBRL data with full dimensional information
   - Better for detailed analysis and custom processing

## Important Notes

- **Regression tests** must use `@pytest.mark.regression` decorator
- **Temporary debug files** should be cleaned up after issue resolution
- **Issue numbers** should be included in file names for traceability
- **API source** should be clear from file location and content