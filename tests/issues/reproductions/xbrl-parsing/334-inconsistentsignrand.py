#!/usr/bin/env python3
"""
Migrated from gists/bugs/334-InconsistentSignRanD.py
Inconsistent Sign Ran D - Xbrl Parsing Issue

Original file: 334-InconsistentSignRanD.py
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
from edgar.entity import EntityFacts

f = Filing(form='10-K', filing_date='2024-07-30', company='MICROSOFT CORP', cik=789019, accession_no='0000950170-24-087843')

xb = f.xbrl()

print(
    xb.query().by_text("us-gaap:ResearchAndDevelopmentExpense")
    .to_dataframe()
)

c = Company("MSFT")
facts = c.get_facts()

print(facts
      .query()
      .by_concept("us-gaap:ResearchAndDevelopmentExpense")
      .by_period_length(12)
      .date_range(start="2023-07-01", end="2024-06-30")
      )

"""
income_statement = xb.statements.income_statement()
print(income_statement)


f = Filing(company='Autodesk, Inc.', cik=769397, form='10-K', filing_date='2025-03-06', accession_no='0000769397-25-000019')
xb = f.xbrl()
income_statement = xb.statements.income_statement()
print(income_statement)

"""


# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
