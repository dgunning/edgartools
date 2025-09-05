#!/usr/bin/env python3
"""
Migrated from gists/bugs/353-BlankMultistatements.py
Blank Multistatements - Xbrl Parsing Issue

Original file: 353-BlankMultistatements.py
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


def show_statement(ticker):
    c = Company(ticker)
    filings = c.get_filings(form="10-K", amendments=False).latest(5)
    xbs:XBRLS = XBRLS.from_filings(filings)
    inc:StitchedStatement = xbs.statements.income_statement()
    print(inc)


if __name__ == '__main__':
    tickers = ['CME', 'REGN', 'STZ', 'MTD']
    for ticker in tickers:
        print(f"Showing statement for {ticker}")
        show_statement(ticker)
        print("\n" + "=" * 80 + "\n")

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
