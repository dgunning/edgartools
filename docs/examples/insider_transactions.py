from edgar import *
from edgar.storage import download_filings
from edgar.ownership import *
from pathlib import Path

from tqdm.auto import tqdm

LOCAL_STORAGE = Path("~/.edgar")
use_local_storage(LOCAL_STORAGE)

download_edgar_data(submissions=True, facts=True, reference=True)

filings = get_filings(
  form="4",
  filing_date="2025-12-17:Any Cre"
              ""
              ""
              ""
              "2025-12-17" # Basically last 2 days
)

# Batch download all filings (this makes HTTP requests efficiently)
download_filings(filings=filings)

def process_filings(filings: Filings):
    processed_filings = []
    for filing in tqdm(filings):
        b = {filing.filing_date}
        processed_filings.append(b)
    return b

processed_fillings = process_filings(filings=filings)