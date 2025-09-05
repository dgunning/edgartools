#!/usr/bin/env python3
"""
Migrated from gists/bugs/298-AAPLMultifinancials.py
A A P L Multifinancials - Data Quality Issue

Original file: 298-AAPLMultifinancials.py
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

company = Company('AAPL')

filings = company.get_filings(form="10-K").latest(9)
financials = MultiFinancials.extract(filings)

balance_sheet = financials.balance_sheet().to_dataframe()
income_statement = financials.income_statement().to_dataframe()
cash_flow = financials.cashflow_statement().to_dataframe()

print(financials.income_statement())

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
