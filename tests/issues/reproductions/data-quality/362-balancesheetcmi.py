#!/usr/bin/env python3
"""
Migrated from gists/bugs/362-BalanceSheetCMI.py
Balance Sheet C M I - Data Quality Issue

Original file: 362-BalanceSheetCMI.py
Category: data-quality
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
# Legacy import - consider updating
from edgar import *
from rich import print
import pandas as pd
pd.options.display.max_colwidth = 120
pd.options.display.max_columns = 12


from edgar.xbrl.stitching.xbrls import XBRLS


c = Company("CMI")
filings = c.get_filings(form="10-K", amendments=False).latest(5)
xbs = XBRLS.from_filings(filings)
#statements = xbs.statements
#balance_sheet = statements.balance_sheet()

#print(balance_sheet)

data = xbs.get_statement('BalanceSheet')

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
