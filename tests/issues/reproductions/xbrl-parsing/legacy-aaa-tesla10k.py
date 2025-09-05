#!/usr/bin/env python3
"""
Migrated from gists/bugs/AAA-Tesla10K.py
A A A Tesla10 K - Xbrl Parsing Issue

Original file: AAA-Tesla10K.py
Category: xbrl-parsing
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
from edgar import *
from rich import print

f = Filing(company='Tesla, Inc.', cik=1318605, form='10-K/A', filing_date='2025-04-30', accession_no='0001104659-25-042659')
x = f.xbrl()
ic = x.statements.income_statement()
print(ic)



# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
