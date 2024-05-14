from edgar.attachments import Attachments
from pyinstrument import Profiler
import asyncio

if __name__ == '__main__':
    with Profiler(async_mode=True) as p:
        attachments = asyncio.run(Attachments.load('https://www.sec.gov/Archives/edgar/data/1881741/0001213900-24-041641-index.html'))
    p.print()