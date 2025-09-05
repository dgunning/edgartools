#!/usr/bin/env python3
"""
Migrated from gists/bugs/324-XbrlQueryNoDimensions.py
Xbrl Query No Dimensions - Xbrl Parsing Issue

Original file: 324-XbrlQueryNoDimensions.py
Category: xbrl-parsing
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
from edgar import *
import pandas as pd
pd.options.display.max_columns = 100

if __name__ == '__main__':
    c = Company("NVDA")
    f = c.latest("10-K")
    xb = XBRL.from_filing(f)
    facts = (xb.query()
             .by_statement_type('IncomeStatement')
             .by_concept('us-gaap:CostOfRevenue')
             .by_dimension(None)
             .to_dataframe('concept','label', 'value', 'dim_us-gaap_NatureOfExpenseAxis')
             )
    print(facts)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
