from edgar import *

c = Company("ORCL")
f = c.latest("10-K")
text = f.text()

def output_path(filing:Filing):
    return f"./data/{filing.cik}/{filing.accession_no}.txt"
print(text)
