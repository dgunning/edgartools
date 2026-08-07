"""
Rebuild edgar/reference/data/company_tickers.parquet (ticker <-> CIK <-> company <-> exchange).

Source: SEC company_tickers_exchange.json
  https://www.sec.gov/files/company_tickers_exchange.json
  Shape: {"fields": ["cik", "name", "ticker", "exchange"], "data": [[...], ...]}

This file backs ticker/CIK resolution across the library (Company("AAPL"), find_cik,
find_ticker, exchange lookups). It is loaded by edgar.reference.tickers.

Output schema matches what load_company_tickers_from_package() expects:
  columns ['cik', 'ticker', 'exchange', 'name'], cik as 10-char zero-padded string.

Requires EDGAR_IDENTITY to be set (SEC User-Agent), which edgar.httprequests uses.
"""
from pathlib import Path

import pandas as pd

from edgar.httprequests import download_json
from edgar.urls import build_company_tickers_exchange_url

DATA_DIR = Path(__file__).resolve().parent.parent / "edgar" / "reference" / "data"
TARGET = DATA_DIR / "company_tickers.parquet"
BACKUP = DATA_DIR / "company_tickers.parquet.bak"


def main() -> None:
    payload = download_json(build_company_tickers_exchange_url())
    df = pd.DataFrame(payload["data"], columns=payload["fields"])

    # Normalize CIK to 10-char zero-padded string (matches existing bundled schema).
    df["cik"] = df["cik"].astype("int64").astype(str).str.zfill(10)

    # Reorder to the bundled schema: [cik, ticker, exchange, name].
    df = df[["cik", "ticker", "exchange", "name"]]

    # Empty exchange strings -> None, matching the existing file's nan handling.
    df["exchange"] = df["exchange"].replace("", None)

    if TARGET.exists():
        BACKUP.write_bytes(TARGET.read_bytes())

    df.to_parquet(TARGET, index=False)

    print(f"rows               : {len(df):,}")
    print(f"unique ciks        : {df['cik'].nunique():,}")
    print(f"unique tickers     : {df['ticker'].nunique():,}")
    print(f"exchange breakdown : {df['exchange'].value_counts(dropna=False).to_dict()}")
    print(f"backup written to  : {BACKUP}")
    print(f"wrote              : {TARGET}")


if __name__ == "__main__":
    main()
