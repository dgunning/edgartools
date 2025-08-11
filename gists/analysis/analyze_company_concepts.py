from edgar import *
from edgar.reference.tickers import get_company_tickers, popular_us_stocks, get_company_ticker_name_exchange
from tqdm.auto import tqdm
# /// script
# dependencies = [
#   "duckdb",
#   "rich",
# ]
# ///

def collect_company_concepts():
    df = get_company_ticker_name_exchange()
    df_top = df.head(1000)
    for t in tqdm(df_top.itertuples(), total=len(df_top), desc="Collecting company concepts"):
        ticker = t.ticker
        name = t.name
        exchange = t.exchange
        try:
            c = Company(ticker)
            f = c.latest(form="10-K")
            xb:XBRL = f.xbrl()
            #presentation = xb.parser.presentation_trees
        except Exception as e:
            print(f"Failed to collect XBRL for {ticker} ({name}) on {exchange}")
            print(e)
            continue




if __name__ == '__main__':
    collect_company_concepts()
