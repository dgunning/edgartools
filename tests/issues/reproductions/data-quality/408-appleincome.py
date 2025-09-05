#!/usr/bin/env python3
"""
Migrated from gists/bugs/408-AppleIncome.py
Apple Income - Data Quality Issue

Original file: 408-AppleIncome.py
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
"""
A user reported in bug 408

For some of the code I used, there seems to be some discrepancy with some values. 
If we look at AAPL, 2020 and after, things like Revenue from Contract with Customer, Operating Income (Loss), Income (Loss) from Continuing Operations before Income Taxes, and Gross Profit (as well as others), seem to be decreased before 2021 to an incorrect amount.

For example, AAPL revenue in 2021 was $365 billion, consistent with the code in the guide above. But for 2020, it says it was $65 billion, despite it being $275 billion. The quarter revenue posted in 2020 in Septemeber was around $65 billion, so maybe it's drawing from that?

"""
import os


c = Company("AAPL")
facts = c.facts
print(facts.income_statement(annual=True, periods=8))

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
