#!/usr/bin/env python3
"""
Migrated from gists/bugs/333-TSLAMaxPeriods.py
T S L A Max Periods - Xbrl Parsing Issue

Original file: 333-TSLAMaxPeriods.py
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

ticker = 'TSLA'
cc = Company(ticker)

ff = cc.get_filings(form="10-K", year=[2025, 2024, 2023, 2022], amendments=False)
print(ff)
x = XBRL.from_filing(ff[0])

xx = XBRLS.from_filings(ff)
#ss = xx.get_statement('IncomeStatement', max_periods=3)

stt = stitch_statements(
            xx.xbrl_list,
            statement_type='IncomeStatement',
            period_type=StatementStitcher.PeriodType.ALL_PERIODS,
            max_periods=3,
            standard=True,
            use_optimal_periods=True
        )

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
