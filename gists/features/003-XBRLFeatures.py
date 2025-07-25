from edgar import *

c = Company("AAPL")
f= c.latest("10-K")
xb:XBRL = f.xbrl()

fact = xb.parser.dei_facts.get('EntityCommonStockSharesOutstanding')
print(int(fact.value))