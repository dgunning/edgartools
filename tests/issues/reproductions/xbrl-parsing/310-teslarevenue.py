#!/usr/bin/env python3
"""
Migrated from gists/bugs/310-TeslaRevenue.py
Tesla Revenue - Xbrl Parsing Issue

Original file: 310-TeslaRevenue.py
Category: xbrl-parsing
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
from edgar import *
import pandas as pd
pd.options.display.max_colwidth = 120
pd.options.display.max_columns = 20

c = Company("TSLA")
filings = c.latest("10-Q", 6)
f = filings[0]

xb = f.xbrl()
ic = xb.statements.income_statement()
print(ic)

print(xb.query()
      .by_value(lambda v : v == -11_000_000 or v == 409_000_000)
      .by_statement_type("IncomeStatement")
      .to_dataframe('concept', 'label', 'value', 'period_end')
      )

"""
for index, filing in enumerate(filings):
    xb = filing.xbrl()
    ic =    xb.statements.income_statement()
    print(ic.to_dataframe()[["concept", "label"]])
    print(filing.filing_date)
    print(xb.query()
                  .by_label("Revenue")
                  .by_statement_type("IncomeStatement")
                  .by_dimension(None)
                  .to_dataframe('concept', 'label', 'value', 'period_end', 'statement_type')
                  #.sort_values(by='period_end', ascending=False)
                  .reset_index(drop=True)
                  .head(1)
               )



print(xb.query()
      .by_value(lambda v : v == 24_927_000_000 or v == 567_000_000 or v == 2_703_000_000 or v == 2_614_000_000)
      .to_dataframe('concept', 'label', 'value', 'period_end')
      )
"""


# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
