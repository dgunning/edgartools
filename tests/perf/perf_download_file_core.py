from pyinstrument import Profiler

from edgar import core

if __name__ == '__main__':
    url = 'https://www.sec.gov/Archives/edgar/daily-index/2024/QTR2/form.20240501.idx'
    core.download_file(url)
