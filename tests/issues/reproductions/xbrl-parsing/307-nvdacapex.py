#!/usr/bin/env python3
"""
Migrated from gists/bugs/307-NVDACapex.py
N V D A Capex - Xbrl Parsing Issue

Original file: 307-NVDACapex.py
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

c = Company("NVDA")
filings = c.get_filings(form="10-K").latest(5)
xbs = XBRLS.from_filings(filings)
cashflow_statement = xbs.statements.cashflow_statement()
print(cashflow_statement)
df = cashflow_statement.to_dataframe()
print(df.query("concept=='us-gaap_PaymentsToAcquireProductiveAssets'"))

print(xbs.query().by_text('PaymentsToAcquireProductiveAssets'))

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
