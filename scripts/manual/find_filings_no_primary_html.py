from edgar import *
from tqdm.auto import tqdm

def find_filings_with_no_primary_html():
    use_local_storage("/Volumes/T9/.edgar")
    filings = get_filings(filing_date="2025-07-14:2025-07-18").sample(5000)
    for filing in tqdm(filings):
        sgml = filing.sgml()
        html = sgml.html()
        if not html:
            print(filing)
            continue
        #if html.startswith("<?xml") and not filing.form in ['3', '3/A', '4', '4/A', '5', '5/A']:
        #    print(filing)

if __name__ == "__main__":
    find_filings_with_no_primary_html()
