import orjson as json
#import json
from pyinstrument import Profiler


if __name__ == '__main__':
    with Profiler() as p:
        with open('data/company_tickers.json') as f:
            json.loads(f.read())

        with open('data/company_submission.json') as f:
            json.loads(f.read())


    p.print()