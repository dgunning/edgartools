import asyncio

from pyinstrument import Profiler

from edgar import httprequests

if __name__ == '__main__':
    url = 'https://www.sec.gov/Archives/edgar/daily-index/2024/QTR2/form.20240501.idx'
    asyncio.run(httprequests.download_file_async(url))

