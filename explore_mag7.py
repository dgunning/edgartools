#!/usr/bin/env python3
"""
MAG7 Financial Data Explorer - Using High-Level API

This script extracts financial metrics for the MAG7 companies using
the high-level API (income_statement, balance_sheet, cash_flow) where possible,
with fallback to raw facts for metrics not directly exposed.
"""
import pandas as pd
from edgar import Company, set_identity
from typing import Dict, Optional, List
import warnings

# Set identity for EDGAR API
set_identity("Dev Gunning developer-gunning@gmail.com")

TICKERS = ['GOOG', 'AMZN', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'META']
START_YEAR = 2009
END_YEAR = 2026

# Legacy CIKs for companies that underwent restructuring
# Maps current ticker -> list of (CIK, description) tuples for historical data
LEGACY_CIKS = {
    'GOOG': [
        (1652044, 'Alphabet Inc. (2015-present)'),
        (1288776, 'GOOGLE INC. (2004-2016)')
    ]
}

# Standardized metric names we want to extract
TARGET_METRICS = [
    'Revenue', 'COGS', 'SGA', 'OperatingIncome', 'PretaxIncome', 'NetIncome',
    'OperatingCashFlow', 'Capex', 'TotalAssets', 'Goodwill', 'IntangibleAssets',
    'ShortTermDebt', 'LongTermDebt', 'CashAndEquivalents',
    # Derived
    'FreeCashFlow', 'TangibleAssets', 'NetDebt'
]

# Concept mapping for raw fact extraction (fallback)
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


def get_filing_count(ticker: str, filter_by_date: bool = True) -> tuple:
    """
    Get filing counts, optionally filtered to our date range.
    
    Returns:
        tuple: (total_filings, filings_in_range)
    """
    import pandas as pd
    
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
    if filter_by_date and all_filings:
        in_range = sum(1 for d in all_filings 
                       if START_YEAR <= pd.to_datetime(d).year <= END_YEAR)
    else:
        in_range = total
    
    return total, in_range


def fetch_company_data(ticker: str) -> Optional[pd.DataFrame]:
    """Fetch financial data, merging from legacy CIKs if applicable."""
    print(f"Processing {ticker}...")
    
    all_dfs = []
    
    # Determine which CIKs to fetch from
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
            
            # Check for former names
            former_names = getattr(company.data, 'former_names', [])
            if former_names:
                names = [fn.get('name', fn) if isinstance(fn, dict) else fn.name for fn in former_names]
                print(f"      Former names: {names}")
            
            # Get facts
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
    
    # Deduplicate by taking the latest filing for each (concept, fiscal_year, fiscal_period)
    combined_df = combined_df.sort_values('filing_date', ascending=False).drop_duplicates(
        subset=['concept', 'fiscal_year', 'fiscal_period']
    )
    
    filing_count = get_filing_count(ticker)
    print(f"  Total: {filing_count} 10-K/10-Q filings, {len(combined_df)} facts after merge")
    
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
    
    # Deduplicate by taking the latest filing_date for each period/metric
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


def detect_coverage_gap(ticker: str, filings_in_range: int, extracted_periods: int) -> Optional[str]:
    """
    Detect if there's a potential coverage gap indicating legacy CIKs may exist.
    
    Args:
        ticker: Company ticker
        filings_in_range: Number of 10-K/10-Q filings within our date range
        extracted_periods: Number of periods actually extracted
    
    Returns a warning message if gap detected, None otherwise.
    """
    # If ticker is in LEGACY_CIKS, skip (already handled)
    if ticker in LEGACY_CIKS:
        return None
    
    # Only warn if we have significantly fewer extracted periods than filings in range
    # Allow ~10% tolerance for edge cases
    if filings_in_range > 0:
        extraction_ratio = extracted_periods / filings_in_range
        
        if extraction_ratio < 0.80 and filings_in_range >= 20:
            # Significant gap - likely missing legacy CIK or concept mappings
            return (f"⚠️ COVERAGE GAP: {ticker} extracted {extracted_periods} periods "
                    f"from {filings_in_range} in-range filings ({extraction_ratio*100:.0f}%). "
                    f"Check for legacy CIKs or missing concept mappings!")
    
    return None


def main():
    all_data = []
    summary = []
    warnings_list = []
    
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
            
            # Check for coverage gaps (using in-range filings)
            warning = detect_coverage_gap(ticker, filings_in_range, periods_extracted)
            if warning:
                warnings_list.append(warning)
                print(f"  {warning}")
    
    if all_data:
        final_df = pd.concat(all_data)
        output_file = "mag7_financials.parquet"
        final_df.to_parquet(output_file)
        print(f"\nSaved data to {output_file}")
        
        # Export per-company CSV files
        export_to_csv(final_df)
        
        # Print summary
        print("\n=== Extraction Summary ===")
        summary_df = pd.DataFrame(summary)
        print(summary_df.to_string(index=False))
        
        # Print warnings if any
        if warnings_list:
            print("\n=== Coverage Gap Warnings ===")
            for w in warnings_list:
                print(w)
            print("\nTip: Add missing CIKs to LEGACY_CIKS in this script.")
        else:
            print("\n✅ No coverage gaps detected.")
        
        # Show sample
        print("\n=== Sample Data ===")
        print(final_df.head())
    else:
        print("No data extracted.")


def export_to_csv(df: pd.DataFrame):
    """
    Export per-company CSV files with metrics as columns and years as rows.
    
    Output folder: Notes/001_initial_mag7_mapping_observation/
    File format: {TICKER}_financials.csv
    """
    import os
    from pathlib import Path
    
    # Output directory
    output_dir = Path("Notes/001_initial_mag7_mapping_observation")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Metrics to include (ordered)
    csv_metrics = [
        'Revenue', 'COGS', 'SGA', 'OperatingIncome', 'PretaxIncome', 'NetIncome',
        'OperatingCashFlow', 'FreeCashFlow', 'TangibleAssets', 'NetDebt'
    ]
    
    print("\n=== Exporting CSV Files ===")
    
    for ticker in df['ticker'].unique():
        ticker_df = df[df['ticker'] == ticker].copy()
        
        # Filter to FY (annual) data only for cleaner output
        fy_df = ticker_df[ticker_df['fiscal_period'] == 'FY'].copy()
        
        if fy_df.empty:
            print(f"  {ticker}: No annual data, skipping")
            continue
        
        # Select and order columns
        available_metrics = [m for m in csv_metrics if m in fy_df.columns]
        output_df = fy_df[['fiscal_year'] + available_metrics].copy()
        
        # Rename for clarity
        output_df = output_df.rename(columns={'fiscal_year': 'Year'})
        
        # Sort by year
        output_df = output_df.sort_values('Year').reset_index(drop=True)
        
        # Save CSV
        csv_path = output_dir / f"{ticker}_financials.csv"
        output_df.to_csv(csv_path, index=False)
        print(f"  {ticker}: Saved {len(output_df)} years to {csv_path}")


if __name__ == "__main__":
    main()



