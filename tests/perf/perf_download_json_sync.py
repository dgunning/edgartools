from edgar.httprequests import download_json
import asyncio
from pyinstrument import Profiler

def my_function():
    print("My function called at {datetime.datetime.now()}")

if __name__ == '__main__':
    with Profiler() as p:
        #download_json("https://www.sec.gov/files/company_tickers.json")
        my_function()

    p.print()


throttler = my_function.__closure__[0].cell_contents
throttler.print_metrics()