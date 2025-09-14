from edgar import *

c = Company("NVDA")
income_statement = c.income_statement(periods=6)
print(income_statement)