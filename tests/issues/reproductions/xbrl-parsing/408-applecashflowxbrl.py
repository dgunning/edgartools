#!/usr/bin/env python3
"""
Migrated from gists/bugs/408-AppleCashflowXBRL.py
Apple Cashflow X B R L - Xbrl Parsing Issue

Original file: 408-AppleCashflowXBRL.py
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

aapl = Company("AAPL")
#filing = aapl.get_filings(form='10-Q').latest()
filing = Filing(company='Apple Inc.', cik=320193, form='10-Q', filing_date='2025-08-01', accession_no='0000320193-25-000073')
print(str(filing))
xb = filing.xbrl()
cf = xb.statements.cashflow_statement()
print(cf)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
