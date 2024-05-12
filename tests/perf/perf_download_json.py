import asyncio

from pyinstrument import Profiler
from rich import print

from edgar import core, httprequests
from edgar.core import download_json


if __name__ == '__main__':
    url = "https://www.sec.gov/files/company_tickers.json"

    with Profiler() as p:
        print("httprequests.download_json()...")
        httprequests.download_json(url)
    p.print()

if __name__ == '__main__':
    download_json("https://www.sec.gov/files/company_tickers.json")
