#!/usr/bin/env python3
"""
Migrated from gists/bugs/349-ToExcel.py
To Excel - Data Quality Issue

Original file: 349-ToExcel.py
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

company=Company("AAPL")
filings=company.get_filings(form="10-K").head(3)
multifinancials=MultiFinancials.extract(filings)
multifinancials.income_statement().to_dataframe().to_excel("income_statement_aapl.xlsx")

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
