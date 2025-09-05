#!/usr/bin/env python3
"""
Migrated from gists/bugs/322-XOMEarnings.py
X O M Earnings - Data Quality Issue

Original file: 322-XOMEarnings.py
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

c = Company('XOM')
filings = c.get_filings(form="10-K").latest(4)
xbs = XBRLS.from_filings(filings)
income_statement = xbs.statements.income_statement()
print(income_statement)
income_df = (income_statement.to_dataframe()
             .query("concept.isin(['us-gaap_EarningsPerShareBasic', 'us-gaap_EarningsPerShareDiluted'])")
             .set_index('concept')
             )
print(income_df.T)

c.get_financials()



# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
