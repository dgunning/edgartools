#!/usr/bin/env python3
"""
Migrated from gists/bugs/394-FilterByDimension.py
Filter By Dimension - Xbrl Parsing Issue

Original file: 394-FilterByDimension.py
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
from edgar.xbrl import *

company = Company("AAPL")
xbrl = company.latest("10-Q").xbrl()

# This works
print(xbrl.query()
     .by_dimension("srt_ProductOrServiceAxis", "us-gaap:ServiceMember"))

# These don't
print(xbrl.query()
     .by_dimension("srt_ProductOrServiceAxis", "us-gaap_ServiceMember"))

print(xbrl.query()
     .by_dimension("srt_ProductOrServiceAxis", "ServiceMember"))

print(xbrl.query()
     .by_dimension("ProductOrServiceAxis", "us-gaap:ServiceMember"))
#print(q.to_dataframe())


# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
