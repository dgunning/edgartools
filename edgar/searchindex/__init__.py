from edgar.reference.tickers import get_company_tickers
from edgar.searchindex.fastsearch import FastSearch, create_search_index, search, company_ticker_preprocess, company_ticker_score

__all__ = ['get_company_search_index']


def get_company_search_index():
    data = get_company_tickers(as_dataframe=False)
    index = create_search_index(data,
                                columns=['ticker', 'company'],
                                preprocess_func=company_ticker_preprocess,
                                score_func=company_ticker_score)
    return index
