#!/usr/bin/env python3
"""
Migrated from gists/bugs/396-ComprehensiveIncome.py
Comprehensive Income - Xbrl Parsing Issue

Original file: 396-ComprehensiveIncome.py
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


company = Company('AAPL')
filing = company.latest("10-K")
xbrl = XBRL.from_filing(filing)
statements:Statements = xbrl.statements
statement = statements['ComprehensiveIncome']
print(statement)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
