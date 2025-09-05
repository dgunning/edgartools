#!/usr/bin/env python3
"""
Migrated from gists/bugs/327-TSLADepreciation.py
T S L A Depreciation - Xbrl Parsing Issue

Original file: 327-TSLADepreciation.py
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

f = Filing(form='10-Q', filing_date='2025-04-23', company='Tesla, Inc.', cik=1318605, accession_no='0001628280-25-018911')
x = f.xbrl()
statement_data = x.get_statement('CashFlowStatement')
c = x.statements.cashflow_statement()
r = c.render()
print(c)

facts = (
    x.query()
    .by_text('tsla:Depr')
)

print(facts)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
