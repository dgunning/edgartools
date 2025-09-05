#!/usr/bin/env python3
"""
Migrated from gists/bugs/315-AppleBalanceSheet.py
Apple Balance Sheet - Xbrl Parsing Issue

Original file: 315-AppleBalanceSheet.py
Category: xbrl-parsing
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
import xbrl
from edgar import *
from edgar.xbrl import *
from rich import print


if __name__ == '__main__':
    c = Company("AAPL")
    filings = c.get_filings(form="10-K", year=[2025, 2024, 2023, 2022])
    xb = XBRL.from_filing(filings[0])
    xbs = XBRLS.from_filings(filings)
    bb = xbs.statements.balance_sheet()
    print(
    xb.query().by_text('Marketable Securities')
    )
    print(
    xbs.query().by_text('Marketable Securities')
    )
    print(bb)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
