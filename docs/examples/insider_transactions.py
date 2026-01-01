"""
Example: Processing Insider Transactions at Scale with Local Storage

This script demonstrates how to use EdgarTools' local storage feature
to efficiently process large numbers of Form 4 insider transaction filings.

Key concepts:
- use_local_storage() to enable disk caching
- filings.download() to batch download filings
- form4.get_ownership_summary() to get TransactionSummary with computed metrics
- summary.to_dataframe() for easy DataFrame export
"""

from edgar import get_filings, use_local_storage
from pathlib import Path
import pandas as pd
from tqdm.auto import tqdm

# Setup local storage
LOCAL_STORAGE = Path("~/.edgar").expanduser()
LOCAL_STORAGE.mkdir(exist_ok=True)
use_local_storage(LOCAL_STORAGE)

# Get Form 4 filings for a date range
filings = get_filings(
    form="4",
    filing_date="2024-12-16:2024-12-20"
)
print(f"Found {len(filings)} Form 4 filings")

# Batch download all filings (skips already downloaded)
filings.download()


def process_form4_filings(filings) -> pd.DataFrame:
    """
    Process Form 4 filings using TransactionSummary API.

    Returns a DataFrame with one row per transaction.
    """
    all_dfs = []

    for filing in tqdm(filings, desc="Processing Form 4s"):
        try:
            form4 = filing.obj()
            summary = form4.get_ownership_summary()

            # Get detailed transactions as DataFrame
            df = summary.to_dataframe(detailed=True, include_metadata=True)
            df['accession_no'] = filing.accession_number
            df['filing_date'] = filing.filing_date
            all_dfs.append(df)

        except Exception as e:
            print(f"Error processing {filing.accession_number}: {e}")
            continue

    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


def get_filing_summaries(filings) -> pd.DataFrame:
    """
    Get summary-level data for each Form 4 filing.

    Returns a DataFrame with one row per filing (aggregated metrics).
    """
    summaries = []

    for filing in tqdm(filings, desc="Processing summaries"):
        try:
            form4 = filing.obj()
            summary = form4.get_ownership_summary()

            summaries.append({
                "accession_no": filing.accession_number,
                "filing_date": filing.filing_date,
                "issuer": summary.issuer,
                "ticker": summary.issuer_ticker,
                "insider": summary.insider_name,
                "position": summary.position,
                "activity": summary.primary_activity,
                "net_change": summary.net_change,
                "net_value": summary.net_value,
                "remaining_shares": summary.remaining_shares,
                "transaction_types": ", ".join(summary.transaction_types),
            })
        except Exception as e:
            print(f"Error: {e}")
            continue

    return pd.DataFrame(summaries)


if __name__ == "__main__":
    # Get detailed transactions
    print("\n--- Processing detailed transactions ---")
    df_detailed = process_form4_filings(filings)
    print(f"Extracted {len(df_detailed)} transactions from {df_detailed['accession_no'].nunique()} filings")

    # Show top insider buyers
    if not df_detailed.empty and 'Code' in df_detailed.columns:
        purchases = df_detailed[df_detailed['Code'] == 'P']
        if not purchases.empty:
            top_buyers = purchases.groupby('Insider')['Shares'].sum().sort_values(ascending=False)
            print("\nTop 10 Insider Buyers (by shares):")
            print(top_buyers.head(10))

    # Get filing-level summaries
    print("\n--- Processing filing summaries ---")
    df_summaries = get_filing_summaries(filings)

    # Show significant purchases
    if not df_summaries.empty:
        big_buys = df_summaries[
            (df_summaries['activity'] == 'Purchase') &
            (df_summaries['net_value'] > 50000)
        ].sort_values('net_value', ascending=False)

        print(f"\nSignificant purchases (>$50,000): {len(big_buys)}")
        if not big_buys.empty:
            print(big_buys[['issuer', 'insider', 'net_change', 'net_value']].head(10))