#!/usr/bin/env python3
"""
Migrated from gists/bugs/AAA-AESFiscalPeriod.py
A A A A E S Fiscal Period - Xbrl Parsing Issue

Original file: AAA-AESFiscalPeriod.py
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
pd.options.display.max_columns = 999
c = Company("AES")
filings = c.get_filings(form=['10-K', '10-Q'], filing_date='2022-01-01:2024-12-31')
xbrls = [f.xbrl() for f in filings]

periods = []
for index, f in enumerate(filings):
    xb = xbrls[index]
    entity_info = xb.entity_info
    periods.append(f"[bold blue]{entity_info['document_type']}[/bold blue] filed on [bold green]{f.filing_date}[/bold green] Fiscal Period [bold blue]{entity_info['fiscal_year']}-{entity_info['fiscal_period']}[/bold blue] {f.period_of_report}")

for period in periods[::-1]:
    print(period)

xbrl_reversed = xbrls[::-1]
print(xbrl_reversed[7].query()
      .by_text("DocumentFiscal")
      )
print(xbrl_reversed[6].query()
      .by_text("DocumentFiscal")
      )
print(xbrl_reversed[4].query()
      .by_text("DocumentFiscal")
      )
print(xbrl_reversed[3].query()
      .by_text("DocumentFiscal")
      )
print(xbrl_reversed[2].query()
      .by_text("DocumentFiscal")
      )
print(xbrl_reversed[1].query()
      .by_text("DocumentFiscal")
      )


# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
