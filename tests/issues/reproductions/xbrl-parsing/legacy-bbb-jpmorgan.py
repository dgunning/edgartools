#!/usr/bin/env python3
"""
Migrated from gists/bugs/BBB-JPMorgan.py
B B B J P Morgan - Xbrl Parsing Issue

Original file: BBB-JPMorgan.py
Category: xbrl-parsing
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
from edgar import *
from rich import print
import pandas as pd
pd.options.display.max_colwidth = 120
f = Filing(company='MORGAN STANLEY', cik=895421, form='10-K', filing_date='2025-02-21', accession_no='0000895421-25-000304')

x = f.xbrl()
ic = x.statements.income_statement()
print(ic)
df = ic.to_dataframe()
print(df)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
