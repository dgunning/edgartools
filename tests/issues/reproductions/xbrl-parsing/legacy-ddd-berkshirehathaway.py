#!/usr/bin/env python3
"""
Migrated from gists/bugs/DDD-BerkshireHathaway.py
D D D Berkshire Hathaway - Xbrl Parsing Issue

Original file: DDD-BerkshireHathaway.py
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


c = Company('BRK.A')
f = c.get_filings(form="10-K", amendments=False).latest(1)
x = f.xbrl()
inc = x.statements.income_statement()
print(inc)

print(inc.to_dataframe()
      .query("label.str.match('Revenue')")
      .filter(['concept', 'label', '2024-12-31'])
      )

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
