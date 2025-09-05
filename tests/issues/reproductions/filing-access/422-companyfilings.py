#!/usr/bin/env python3
"""
Migrated from gists/bugs/422-CompanyFilings.py
Company Filings - Filing Access Issue

Original file: 422-CompanyFilings.py
Category: filing-access
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
from rich import print
from edgar import Company, set_identity


company = Company("AAPL")
filings = company.get_filings(year=2025)
print(filings)


"""
Throws the following error:

pyarrow.lib.ArrowInvalid: Cannot locate timezone 'UTC': Timezone database not found at "C:\..."

Expected behavior is to return all filings filtered by the year.

System is Windows 10, Python 3.13, edgartools 4.9.0
"""

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
