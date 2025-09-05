#!/usr/bin/env python3
"""
Migrated from gists/bugs/341-NVDAEarningsPerShare.py
N V D A Earnings Per Share - Data Quality Issue

Original file: 341-NVDAEarningsPerShare.py
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
from rich import print

c  = Company("NVDA")
filings = c.latest("10-Q", 4)
print(filings)
filings = c.latest("10-K", 2)
f = filings[0]
xb = f.xbrl()
income_statement = xb.statements.income_statement()
print(income_statement)

print(
    xb.query()
    .by_text("Basic")
    #.by_date_range("2025-01-27")
    #.by_value(lambda v : v < 0)
)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
