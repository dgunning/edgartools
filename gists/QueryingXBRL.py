from edgar import *
from rich import print


c = Company('AAPL')
f = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2024-11-01', accession_no='0000320193-24-000123')
xb  = f.xbrl()

print(len(xb.facts))

# Query by concept
results = xb.query().by_concept("us-gaap:PaymentsToAcquireAvailableForSaleSecuritiesDebt")
print(results)
print(type(results))

#
revenue_query = xb.query().by_label("Revenue")
print(revenue_query)

revenue_query = xb.query().by_label("Revenue", exact=True)
print(revenue_query)

income_facts = xb.query().by_statement_type("IncomeStatement")

print(income_facts)

sorted_query = xb.query().sort_by('value', ascending=False)
print(sorted_query.limit(10))

stats = xb.query().by_statement_type("IncomeStatement").stats()
