#!/usr/bin/env python3
"""
Migrated from gists/bugs/399-BalanceSheetPeriod.py
Balance Sheet Period - Xbrl Parsing Issue

Original file: 399-BalanceSheetPeriod.py
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

c = Company('TSLA')
filings = c.get_filings(form="10-K", amendments=True).head(7)
print(filings)
print(filings[0])
xbrl = XBRL.from_filing(filings[0])
statements = xbrl.statements
print(statements.balance_sheet())

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
