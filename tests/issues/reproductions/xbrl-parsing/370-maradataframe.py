#!/usr/bin/env python3
"""
Migrated from gists/bugs/370-MaraDataframe.py
Mara Dataframe - Xbrl Parsing Issue

Original file: 370-MaraDataframe.py
Category: xbrl-parsing
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
# Legacy import - consider updating
from edgar import *
from rich import print
import pandas as pd
pd.options.display.max_colwidth = 120
pd.options.display.max_columns = 12

c = Company("MARA")
#f = c.latest("10-Q")
f = Filing(company='MARA Holdings, Inc.', cik=1507605, form='10-Q', filing_date='2025-07-29',
           accession_no='0001507605-25-000018')

x = f.xbrl()

inc = x.statements.income_statement()
print(inc)
cashflow = x.statements.cashflow_statement()
print(cashflow)
bs = x.statements.balance_sheet()
print(bs)


# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
