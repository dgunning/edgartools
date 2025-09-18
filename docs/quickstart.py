from rich import print

from edgar import *

# 1. Getting your first filings

filings = get_filings()
print(filings)

## 1b Filtering for certain filings
insider_filings = get_filings(form="4")
print(insider_filings)

## 1c Getting a specific filing
f = filings[10]

# 2. Getting a company

c = Company("AAPL")
print(c)

## 2b Getting a company's filings
aapl_filings = c.get_filings()
print(aapl_filings)

## 2c Getting insider filings for a company
insider_filings = c.get_filings(form="4")

## 2d Getting a specific filing for a company
f = insider_filings[0]

## 2e Getting data from a filing
form4 = f.obj()
print(form4)


# 3 Getting company financials

tenq_filings = c.get_filings(form="10-Q")
f = tenq_filings.latest()
xb = f.xbrl()

inc = xb.statements.income_statement()
print(inc)
