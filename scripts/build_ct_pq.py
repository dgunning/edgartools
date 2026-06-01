"""
Rebuild edgar/reference/data/ct.pq (CUSIP -> Ticker mapping used by 13F parsers).

Strategy (Option 2 — merge, no coverage regression):
  - Primary source: FailsToDeliver_cusip_to_ticker.parquet (fresh, SEC Fails-to-Deliver
    derived, last_seen up to 2026). Provides cusip/symbol/description/last_seen.
  - Fallback: the existing ct.pq, used ONLY for CUSIPs absent from the primary source,
    so we keep the ~1,981 mappings that exist in the old file but not the new one.

Output schema matches what edgar/reference/tickers.py expects: columns ['Cusip', 'Ticker'].
"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "edgar" / "reference" / "data"
PRIMARY = DATA_DIR / "FailsToDeliver_cusip_to_ticker.parquet"
TARGET = DATA_DIR / "ct.pq"
BACKUP = DATA_DIR / "ct.pq.bak"


def main() -> None:
    new = pd.read_parquet(PRIMARY)
    old = pd.read_parquet(TARGET)

    # Normalize primary source to the [Cusip, Ticker] schema.
    primary = (
        new[["cusip", "symbol"]]
        .rename(columns={"cusip": "Cusip", "symbol": "Ticker"})
        .drop_duplicates(subset="Cusip", keep="first")
    )

    # Fallback: rows from old ct.pq whose CUSIP is not covered by the primary source.
    missing_mask = ~old["Cusip"].isin(set(primary["Cusip"]))
    fallback = old.loc[missing_mask, ["Cusip", "Ticker"]].drop_duplicates(
        subset="Cusip", keep="first"
    )

    merged = (
        pd.concat([primary, fallback], ignore_index=True)
        .sort_values("Cusip", kind="stable")
        .reset_index(drop=True)
    )

    # Back up the existing file before overwriting.
    if TARGET.exists():
        BACKUP.write_bytes(TARGET.read_bytes())

    merged.to_parquet(TARGET, index=False)

    print(f"primary (fresh) cusips : {len(primary):,}")
    print(f"fallback (old-only)    : {len(fallback):,}")
    print(f"merged total           : {len(merged):,}")
    print(f"backup written to      : {BACKUP}")
    print(f"wrote                  : {TARGET}")


if __name__ == "__main__":
    main()
