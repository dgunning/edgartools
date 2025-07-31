from edgar.entity import EntityFacts
from edgar import *
from rich import print


c = Company("TSLA")

facts:EntityFacts = c.get_facts()
print(facts)
