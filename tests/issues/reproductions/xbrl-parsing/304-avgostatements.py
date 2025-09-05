#!/usr/bin/env python3
"""
Migrated from gists/bugs/304-AVGOStatements.py
A V G O Statements - Xbrl Parsing Issue

Original file: 304-AVGOStatements.py
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

c = Company("AVGO")
f = c.latest("10-Q")
xb = f.xbrl()
print(xb.statements.income_statement())

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
