# XBRL Parsing Issue Reproduction

This directory contains reproduction scripts and tests for issues with EdgarTools' direct XBRL document parsing.

## What Is XBRL Parsing?

XBRL parsing involves directly processing XBRL documents from SEC filings through EdgarTools' `edgar.xbrl` module. This is the data source used by:

- `filing.xbrl()`
- `xbrl.statements.income_statement()`
- `xbrl.statements.balance_sheet()`
- `xbrl.statements.cash_flow_statement()`
- `xbrl.facts` and dimensional filtering

## Files In This Directory

### Issue #427 - XBRL Data Parsing Inconsistencies
- `issue_427_clean_reproduction.py` - Clean reproduction of parsing issues
- `issue_427_historical_data_investigation.py` - Historical data analysis
- `issue_427_xbrl_data_cap_2018.py` - 2018 data cap investigation
- `issue_427_xbrls_investigation.py` - Multiple XBRL investigation
- `issue_427_xbrls_stitching_investigation.py` - Data stitching analysis

### Issue #429 - Statement Regression
- `issue_429_statement_regression.py` - Statement regression reproduction
- `test_fix_429.py` - Fix verification for statement selection
- `test_multiple_companies_429.py` - Multi-company regression test

### Legacy Issues (Historical Reference)
- `304-avgostatements.py` through `434-solution_example.py` - Numbered reproduction files
- `legacy-*.py` - Legacy reproduction scripts for reference

### Recent Analysis
- `issue-403_standard_parameter.py` - Standard parameter testing
- `issue-434_*.py` - Exhibit content and search issues
- `test_issue_*.py` - Various XBRL-specific tests

## Common XBRL Issues

### Presentation Tree Problems
- Incorrect statement classification
- Missing or misaligned presentation nodes
- Role-based statement organization issues

### Dimensional Data Issues  
- Segment and dimension filtering problems
- Member selection and filtering
- Complex dimensional hierarchies

### Period and Context Issues
- Period selection for multi-year data
- Context matching and alignment
- Duration vs instant period handling

### Concept Mapping Issues
- XBRL concept to statement mapping
- Custom vs standard taxonomies
- Extension concept handling

## Testing Guidelines

- All regression tests must use `@pytest.mark.regression` decorator
- Test both individual XBRL documents and cross-filing patterns
- Verify presentation tree structure and statement organization
- Check dimensional filtering and member selection
- Validate period and context handling

## XBRL API vs Facts API

**XBRL API** (this directory):
- Raw XBRL document parsing
- Full dimensional information available
- Direct control over presentation trees and roles
- Accessed via filing.xbrl() methods
- Better for detailed analysis and custom processing

**Facts API** (../entity-facts/):
- Pre-processed, standardized data  
- Better performance for multi-year analysis
- Accessed via Company methods
- Period selection handled automatically

Choose the appropriate directory based on which data source the issue affects.