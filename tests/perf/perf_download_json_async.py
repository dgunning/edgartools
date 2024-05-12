from edgar.httprequests import download_json_async
import asyncio

if __name__ == '__main__':
    asyncio.run(download_json_async("https://www.sec.gov/files/company_tickers.json"))
