#!/usr/bin/env python3
"""
Migrated from gists/bugs/339-AMDIncome.py
A M D Income - Data Quality Issue

Original file: 339-AMDIncome.py
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

c = Company("AMD")
filings = c.get_filings(form="10-K").latest(2)
xbs = XBRLS.from_filings(filings)
income_statement = xbs.statements.income_statement()
print(income_statement)

f = filings[0]
xb = f.xbrl()
inc = xb.statements.income_statement()
print(inc)

print(xb.query()
      .by_value(lambda v: v == 12_114_000_000 or v == -13_060_000_000)
      )

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
