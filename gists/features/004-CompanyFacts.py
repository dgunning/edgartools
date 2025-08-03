from edgar.entity import EntityFacts
from edgar import *
from rich import print


c = Company("TSLA")

facts:EntityFacts = c.get_facts()
print(facts)

income_statement = facts.income_statement()
print(income_statement)

print(facts
      .query()
      .by_concept("us-gaap:GrossProfit")
      .by_period_length(12)
      .pivot_by_period()
)