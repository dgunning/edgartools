#!/usr/bin/env python3
"""
Migrated from gists/bugs/406-AAPLIncome.py
A A P L Income - Xbrl Parsing Issue

Original file: 406-AAPLIncome.py
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

c = Company("AAPL")
filing = c.get_filings(form="10-Q", accession_number="0000320193-23-000006").latest()

xb:XBRL = filing.xbrl()
print(xb.period_of_report)
income:Statement = xb.statements.income_statement()
print(income)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
