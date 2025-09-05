#!/usr/bin/env python3
"""
Migrated from gists/bugs/321-DifferentFilingCount.py
Different Filing Count - Filing Access Issue

Original file: 321-DifferentFilingCount.py
Category: filing-access
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
# Legacy import - consider updating
from edgar import *
from rich import print
import pandas as pd
pd.options.display.max_colwidth = 120
pd.options.display.max_columns = 12
from edgar import get_filings, Company, set_identity
pd.options.display.max_columns = 15


cik = 26537
accession_number = "0000950123-10-073332"
f = find(accession_number)


filings = get_filings(2010, 3).filter(cik=cik)
print(filings)
dup_filing = filings.filter(accession_number=accession_number)
print(dup_filing)

c = Company(cik)
company_filings = c.get_filings(year=2010, quarter=3)
print(company_filings)
com_filings = company_filings.filter(accession_number=accession_number)
print(com_filings.to_pandas())
com_filing = com_filings.latest(1)
print(com_filing)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
