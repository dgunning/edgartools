#!/usr/bin/env python3
"""
Migrated from gists/bugs/405-AAPLFacts.py
A A P L Facts - Data Quality Issue

Original file: 405-AAPLFacts.py
Category: data-quality
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
from edgar import *


c = Company("AAPL")
facts = c.facts

income_statement = facts.income_statement(annual=True, periods=7)
print(income_statement)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
