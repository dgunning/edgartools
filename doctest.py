import pandas as pd

from edgar import *

company = Company("AAPL")

"""
financials = company.get_financials()
income_statement = financials.income_statement()
print(income_statement)
"""

filings = company.get_filings(form="4").head(10)
f = filings[0]
transactions = pd.concat([f.obj()
                         .to_dataframe()
                         .fillna('')
                for f in filings])

fund = Company("BRK-A")
holdings = fund.get_filings(form="13F-HR").latest().obj()

filing = company.get_filings(form="10-K").latest()
text = filing.text()  # Clean, readable text

company = Company("TSLA")
latest_10k = company.get_filings(form="10-K").latest()
financials = latest_10k.obj().financials
