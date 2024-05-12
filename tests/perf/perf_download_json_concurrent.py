import asyncio
from edgar.httprequests import download_json_async, get_with_retry_async, TooManyRequestsError
from pyinstrument import Profiler
import pandas as pd

async def download_json_concurrent(url, num_concurrent=100):
    tasks = []
    for _ in range(num_concurrent):
        task = asyncio.create_task(download_json_async(url))
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

if __name__ == '__main__':
    url = "https://www.sec.gov/files/company_tickers.json"

    try:
        results = asyncio.run(download_json_concurrent(url))
        for result in results:
            if isinstance(result, TooManyRequestsError):
                raise result
    except TooManyRequestsError as e:
        print(f"Error: {str(e)}")
    except Exception as e:
        raise e
    finally:
        if hasattr(get_with_retry_async, '__closure__'):
            for cell in get_with_retry_async.__closure__:
                if hasattr(cell.cell_contents, 'get_metrics'):
                    throttler = cell.cell_contents
                    metrics = throttler.get_metrics()
                    metrics_df = pd.DataFrame.from_dict(metrics, orient='index', columns=['Value'])
                    print("Throttler Metrics:")
                    print(metrics_df)
                    break
            else:
                print("Throttler instance not found in the closure.")
        else:
            print("The 'get_with_retry_async' function does not have a closure.")
