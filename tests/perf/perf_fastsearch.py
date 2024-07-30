from pyinstrument import Profiler

from search.datasearch import create_search_index, company_ticker_preprocess, company_ticker_score, search
from edgar.reference.tickers import get_company_tickers

data = get_company_tickers(as_dataframe=False)
index = create_search_index(data,
                            columns=['ticker', 'company'],
                            preprocess_func=company_ticker_preprocess,
                            score_func=company_ticker_score)

if __name__ == '__main__':
    with Profiler() as p:
        results = search(index, 'TESLA', top_n=10)
    p.print(timeline=True)
