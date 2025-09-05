#!/usr/bin/env python3
"""
Migrated from gists/bugs/395-MissingColumn.py
Missing Column - Xbrl Parsing Issue

Original file: 395-MissingColumn.py
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

c = Company("ADGM")
#f = c.latest("10-K")
f = Filing(form='10-Q', filing_date='2024-08-26', company='Adagio Medical Holdings, Inc.', cik=2006986, accession_no='0001410578-24-001560')
xb = f.xbrl()
cashflow:Statement = xb.statements.cashflow_statement()
print(cashflow)

print(xb.query()
      .by_statement_type("CashFlowStatement"))

facts = c.facts
cf = facts.cash_flow(annual=False, periods=6)
print(cf)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
