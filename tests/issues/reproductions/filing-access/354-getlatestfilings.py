#!/usr/bin/env python3
"""
Migrated from gists/bugs/354-GetLatestFilings.py
Get Latest Filings - Filing Access Issue

Original file: 354-GetLatestFilings.py
Category: filing-access
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
# Legacy import - consider updating
from edgar import *
from rich import print
import pandas as pd
pd.options.display.max_colwidth = 120
pd.options.display.max_columns = 12
import pyarrow as pa


def get_todays_filings(form:str="8-K"):
    filings = get_all_current_filings()
    print(filings)
    print(filings.tail(50))



if __name__ == '__main__':
    get_todays_filings()

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
