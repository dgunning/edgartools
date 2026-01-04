#!/usr/bin/env python3
"""
MAG7 Financial Data Explorer - Using Bulk Downloaded Data

This script demonstrates how to:
1. Download EDGAR bulk data (facts, submissions)
2. Enable local storage mode
3. Extract MAG7 financial metrics from LOCAL data (no API calls to SEC)

This is a modified version of explore_mag7.py that uses bulk data instead of live API.
"""
import pandas as pd
from pathlib import Path
from edgar import Company, set_identity, download_edgar_data, use_local_storage
from typing import Dict, Optional, List
import warnings
import time

# Set identity (still required even for local storage operations)
set_identity("Dev Gunning developer-gunning@gmail.com")

TICKERS = ['GOOG', 'AMZN', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'META']
START_YEAR = 2009
END_YEAR = 2026

# Legacy CIKs for companies that underwent restructuring
LEGACY_CIKS = {
    'GOOG': [
        (1652044, 'Alphabet Inc. (2015-present)'),
        (1288776, 'GOOGLE INC. (2004-2016)')
    ]
}

# Concept mapping for raw fact extraction
CONCEPTS = {
    'Revenue': ['RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'Revenues', 'Revenue', 'TotalRevenues', 'NetSales'],
    'COGS': ['CostOfGoodsAndServicesSold', 'CostOfRevenue', 'CostOfGoodsSold', 'CostOfSales'],
    'SGA': ['SellingGeneralAndAdministrativeExpense', 'SellingAndMarketingExpense', 'GeneralAndAdministrativeExpense'],
    'OperatingIncome': ['OperatingIncomeLoss'],
    'PretaxIncome': ['IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItems', 'IncomeLossFromContinuingOperationsBeforeIncomeTaxes'],
    'NetIncome': ['NetIncomeLoss', 'ProfitLoss', 'NetIncome', 'NetEarnings'],
    'OperatingCashFlow': ['NetCashProvidedByUsedInOperatingActivities'],
    'Capex': ['PaymentsToAcquirePropertyPlantAndEquipment'],
    'TotalAssets': ['Assets', 'TotalAssets'],
    'Goodwill': ['Goodwill'],
    'IntangibleAssets': ['IntangibleAssetsNetExcludingGoodwill', 'FiniteLivedIntangibleAssetsNet', 'IndefiniteLivedIntangibleAssetsExcludingGoodwill'],
    'ShortTermDebt': ['ShortTermBorrowings', 'DebtCurrent'],
    'LongTermDebt': ['LongTermDebt', 'LongTermDebtNoncurrent'],
    'CashAndEquivalents': ['CashAndCashEquivalentsAtCarryingValue', 'CashAndCashEquivalents']
}


def download_bulk_data(force: bool = False):
    """
    Download EDGAR bulk data if not already present.
    
    Args:
        force: If True, re-download even if data exists
    """
    print("=" * 60)
    print("STEP 1: DOWNLOADING EDGAR BULK DATA")
    print("=" * 60)
    print("\nThis will download approximately 7GB of data:")
    print("  - Company facts (XBRL financial data)")
    print("  - Submission metadata (filing information)")
    print("  - Reference data (lookup tables)")
    print()
    
    start_time = time.time()
    
    try:
        # Download bulk data
        download_edgar_data(
            facts=True,        # Company facts/XBRL data
            submissions=True,  # Filing submissions
            reference=True     # Reference/lookup data
        )
        
        elapsed = time.time() - start_time
        print(f"\n✅ Bulk data download complete! (took {elapsed:.1f}s)")
        
    except Exception as e:
        print(f"\n❌ Error downloading bulk data: {e}")
        raise


def enable_local_storage():
    """Enable local storage mode so all API calls read from local files."""
    print("\n" + "=" * 60)
    print("STEP 2: ENABLING LOCAL STORAGE MODE")
    print("=" * 60)
    
    use_local_storage(True)
    print("✅ Local storage enabled - all API calls now use local data")


def get_filing_count(ticker: str) -> tuple:
    """Get filing counts from local data."""
    all_filings = []
    
    if ticker in LEGACY_CIKS:
        for cik, desc in LEGACY_CIKS[ticker]:
            company = Company(cik)
            filings = company.get_filings(form=['10-K', '10-Q'])
            if filings:
                all_filings.extend(filings.data['filing_date'].to_pylist())
    else:
        company = Company(ticker)
        filings = company.get_filings(form=['10-K', '10-Q'])
        if filings:
            all_filings = filings.data['filing_date'].to_pylist()
    
    total = len(all_filings)
    
    # Filter to date range
    if all_filings:
        in_range = sum(1 for d in all_filings 
                       if START_YEAR <= pd.to_datetime(d).year <= END_YEAR)
    else:
        in_range = total
    
    return total, in_range


def fetch_company_data(ticker: str) -> Optional[pd.DataFrame]:
    """Fetch financial data from local bulk data."""
    print(f"\nProcessing {ticker}...")
    
    all_dfs = []
    
    if ticker in LEGACY_CIKS:
        ciks_to_fetch = LEGACY_CIKS[ticker]
        print(f"  {ticker} has legacy CIKs, fetching from multiple entities:")
    else:
        company = Company(ticker)
        ciks_to_fetch = [(company.cik, company.name)]
    
    for cik, desc in ciks_to_fetch:
        try:
            company = Company(cik)
            print(f"    - {desc}: CIK {cik}")
            
            # Get facts from LOCAL storage
            facts = company.get_facts()
            if not facts:
                print(f"      No facts found")
                continue
            
            # Convert to DataFrame
            df = facts.to_dataframe(include_metadata=True)
            
            # Strip namespace
            df['concept_stripped'] = df['concept'].apply(lambda x: x.split(':')[-1] if ':' in x else x)
            
            # Filter for relevant years
            df = df[df['fiscal_year'].between(START_YEAR, END_YEAR)]
            
            if not df.empty:
                all_dfs.append(df)
                print(f"      Found {len(df)} facts")
            
        except Exception as e:
            print(f"      Error: {e}")
    
    if not all_dfs:
        print(f"  No facts found for {ticker}")
        return None
    
    # Merge all DataFrames
    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    # Deduplicate
    combined_df = combined_df.sort_values('filing_date', ascending=False).drop_duplicates(
        subset=['concept', 'fiscal_year', 'fiscal_period']
    )
    
    return combined_df


def process_metrics(ticker: str, df: pd.DataFrame) -> pd.DataFrame:
    """Extract and process standardized metrics."""
    extracted = []
    
    for metric, concepts in CONCEPTS.items():
        mask = df['concept_stripped'].isin(concepts)
        metric_df = df[mask].copy()
        metric_df['metric'] = metric
        extracted.append(metric_df)
    
    if not extracted:
        return pd.DataFrame()
    
    result_df = pd.concat(extracted)
    
    # Deduplicate
    result_df = result_df.sort_values('filing_date', ascending=False).drop_duplicates(
        subset=['fiscal_year', 'fiscal_period', 'metric']
    )
    
    # Pivot to get metrics as columns
    pivot_df = result_df.pivot(
        index=['fiscal_year', 'fiscal_period'], 
        columns='metric', 
        values='numeric_value'
    ).reset_index()
    
    pivot_df['ticker'] = ticker
    
    # Calculate derived metrics
    if 'OperatingCashFlow' in pivot_df.columns and 'Capex' in pivot_df.columns:
        pivot_df['FreeCashFlow'] = pivot_df['OperatingCashFlow'] - pivot_df['Capex'].fillna(0)
    
    if 'TotalAssets' in pivot_df.columns:
        goodwill = pivot_df.get('Goodwill', 0)
        if isinstance(goodwill, pd.Series):
            goodwill = goodwill.fillna(0)
        intangibles = pivot_df.get('IntangibleAssets', 0)
        if isinstance(intangibles, pd.Series):
            intangibles = intangibles.fillna(0)
        pivot_df['TangibleAssets'] = pivot_df['TotalAssets'] - goodwill - intangibles
    
    if 'CashAndEquivalents' in pivot_df.columns:
        st_debt = pivot_df.get('ShortTermDebt', 0)
        if isinstance(st_debt, pd.Series):
            st_debt = st_debt.fillna(0)
        lt_debt = pivot_df.get('LongTermDebt', 0)
        if isinstance(lt_debt, pd.Series):
            lt_debt = lt_debt.fillna(0)
        pivot_df['NetDebt'] = st_debt + lt_debt - pivot_df['CashAndEquivalents']
    
    return pivot_df


def main():
    """Main function: Download bulk data, enable local storage, extract MAG7 data."""
    
    # Step 1: Download bulk data
    download_bulk_data()
    
    # Step 2: Enable local storage
    enable_local_storage()
    
    # Step 3: Extract MAG7 data using local storage
    print("\n" + "=" * 60)
    print("STEP 3: EXTRACTING MAG7 DATA FROM LOCAL BULK DATA")
    print("=" * 60)
    
    all_data = []
    summary = []
    
    for ticker in TICKERS:
        total_filings, filings_in_range = get_filing_count(ticker)
        df = fetch_company_data(ticker)
        
        if df is not None:
            metrics_df = process_metrics(ticker, df)
            all_data.append(metrics_df)
            
            periods_extracted = len(metrics_df)
            summary.append({
                'ticker': ticker,
                'filings_total': total_filings,
                'filings_in_range': filings_in_range,
                'periods_extracted': periods_extracted
            })
    
    if all_data:
        final_df = pd.concat(all_data)
        
        # Save to parquet
        output_dir = Path(__file__).parent.parent.parent / "data"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "mag7_financials_bulk.parquet"
        final_df.to_parquet(output_file)
        
        # Print summary
        print("\n" + "=" * 60)
        print("EXTRACTION SUMMARY (from LOCAL bulk data)")
        print("=" * 60)
        summary_df = pd.DataFrame(summary)
        print(summary_df.to_string(index=False))
        
        print(f"\n✅ Saved {len(final_df)} records to {output_file}")
        
        # Show sample
        print("\n=== Sample Data ===")
        print(final_df.head())
    else:
        print("No data extracted.")


if __name__ == "__main__":
    main()
