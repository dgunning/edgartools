# EdgarTools 5.3.0 Release Notes

Release Date: 2025-12-15

## Overview

EdgarTools 5.3.0 is a feature release that adds significant new capabilities for Asset-Backed Securities (ABS) filings, filer categorization, and XBRL standardization. This release also includes important bug fixes and code quality improvements.

## What's New

### Form 10-D (ABS Distribution Report) Support

Full parsing support for Asset-Backed Securities Distribution Reports:

```python
from edgar import Filing

# Get a Form 10-D filing
filing = Filing(company='1234567', cik='1234567', form='10-D', filing_date='2024-01-15', accession_no='0001234567-24-000001')

# Access structured ABS data
ten_d = filing.obj()
print(ten_d.issuing_entity)
print(ten_d.depositor)
print(ten_d.distribution_period)
print(ten_d.abs_type)  # CMBS, AUTO, CREDIT_CARD, RMBS, etc.

# Access CMBS XML asset data from EX-102 exhibits
if ten_d.has_cmbs_data:
    cmbs_data = ten_d.cmbs_assets
```

### Filer Category Identification

Easy identification of filer status for regulatory and analytical purposes:

```python
from edgar import Company

company = Company("AAPL")

# Check filer status
if company.is_large_accelerated_filer:
    print("Large accelerated filer")

if company.is_smaller_reporting_company:
    print("Smaller reporting company")

if company.is_emerging_growth_company:
    print("Emerging growth company")

# Access full category details
category = company.filer_category
print(category.status)  # FilerStatus.LARGE_ACCELERATED
```

### XBRL Synonym Management

Standardize financial analysis across companies without needing to know company-specific XBRL tag variants:

```python
from edgar.standardization import SynonymGroups

# Get all known tag variants for revenue
revenue_tags = SynonymGroups.get_tags("Revenue")
# Returns: ['Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax', ...]

# Find the standardized concept for a company-specific tag
concept = SynonymGroups.get_concept("SalesRevenueNet")
# Returns: "Revenue"

# Use with EntityFacts for consistent cross-company analysis
facts = company.get_facts()
revenue_facts = facts[facts['concept'].isin(revenue_tags)]
```

## Bug Fixes

- Fixed `get_icon_from_ticker` to support tickers with hyphens (e.g., BRK-B) - issue #246
- Fixed 22 failing regression tests for improved reliability
- Addressed ruff linting issues and pyright type errors across codebase
- Corrected API documentation for statement extraction

## Code Quality

- High priority code quality issues in edgar/ directory addressed
- Improved type safety with pyright type error fixes
- Better code maintainability through linting fixes

## Compatibility

This release maintains full backward compatibility with v5.2.0. No code changes are required for existing users.

## Installation

```bash
pip install --upgrade edgartools
```

## Next Steps

After installing, verify your version:

```python
import edgar
print(edgar.__version__)  # Should print 5.3.0
```

## Contributors

Thank you to all contributors who helped with this release!

## Full Changelog

For a complete list of changes, see [CHANGELOG.md](CHANGELOG.md#530---2025-12-15)
