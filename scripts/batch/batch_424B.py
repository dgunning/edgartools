from edgar import *
from edgar.offerings.prospectus import *
from tqdm.auto import tqdm
from rich import print

filings = get_filings(year=[2025], form=['424B1', '424B3', '424B4', '424B5', '424B6', '424B7', '424B8']).sample(1000)
for filing in tqdm(filings):
    offering: Prospectus424B = filing.obj()
    deal:Deal = offering.deal
    lifecycle:ShelfLifecycle = offering.lifecycle
    print(offering)