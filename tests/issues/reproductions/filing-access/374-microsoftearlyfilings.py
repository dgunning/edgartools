#!/usr/bin/env python3
"""
Migrated from gists/bugs/374-MicrosoftEarlyFilings.py
Microsoft Early Filings - Filing Access Issue

Original file: 374-MicrosoftEarlyFilings.py
Category: filing-access
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
# While trying to fetch filings for Microsoft, an error occurs due to issues with fetching company tickers.
# Legacy import - consider updating
from edgar import *
from rich import print
import pandas as pd
pd.options.display.max_colwidth = 120
pd.options.display.max_columns = 12

c = Company("MSFT")

filings = c.get_filings(form="10-K")
print("Date Range for 10-K filings for MSFT", filings.date_range)
print(filings)

filings = c.get_filings()
print("Date Range for all filings for MSFT", filings.date_range)
print(filings)

"""
Error fetching company tickers from [https://www.sec.gov/include/ticker.txt]: 'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte
Error fetching company tickers from [https://www.sec.gov/files/company_tickers.json]: 'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte
Traceback (most recent call last):
  File "/Users/dwight/PycharmProjects/edgartools/gists/bugs/374-MicrosoftEarlyFilings.py", line 3, in <module>
    c = Company("MSFT")
        ^^^^^^^^^^^^^^^
  File "/Users/dwight/PycharmProjects/edgartools/edgar/entity/core.py", line 394, in __init__
    super().__init__(cik_or_ticker)
  File "/Users/dwight/PycharmProjects/edgartools/edgar/entity/core.py", line 198, in __init__
    cik = find_cik(cik_or_identifier)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/dwight/PycharmProjects/edgartools/edgar/reference/tickers.py", line 389, in find_cik
    cik = find_company_cik(ticker)
          ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/dwight/PycharmProjects/edgartools/edgar/reference/tickers.py", line 338, in find_company_cik
    lookup = get_company_cik_lookup()
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/dwight/PycharmProjects/edgartools/edgar/reference/tickers.py", line 202, in get_company_cik_lookup
    df = get_cik_tickers()
         ^^^^^^^^^^^^^^^^^
  File "/Users/dwight/PycharmProjects/edgartools/edgar/reference/tickers.py", line 180, in get_cik_tickers
    raise Exception("Both data sources are unavailable")
Exception: Both data sources are unavailable


The error came from here probably
httprequests:153
{UnicodeDecodeError}UnicodeDecodeError('utf-8', b'\x80\x04\x95\xf8\x01', 0, 1, 'invalid start byte')

"""

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
