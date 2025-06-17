from edgar import *
from rich import print

set_identity("Mike@indeco.com")
c = Company("AAPL")
filing = c.latest("10-K")
print(filing.attachments)
filing.attachments[85].view()
#print(c.__doc__)

