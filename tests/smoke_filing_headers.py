
from edgar import *
from rich import print
from rich.text import Text
if __name__ == '__main__':
    for filing in get_filings().sample(100):
        try:
            print(Text(filing.header.header_text))
            print(filing.header)
        except Exception as e:
            print(f"Failed to get header for {filing.accession_no} {e}")