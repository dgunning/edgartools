#!/usr/bin/env python3
"""
Coverage Measurement for Concept Mapping

Measures what % of expected financial metrics we can extract per company.
Uses unique fiscal periods (from 10-K/10-Q) as denominator.

Usage:
    python -m edgar.xbrl.standardization.coverage --companies MAG7
    python -m edgar.xbrl.standardization.coverage --companies AAPL MSFT GOOG
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from edgar import Company, set_identity


# MAG7 tickers for initial testing
MAG7 = ['GOOG', 'AMZN', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'META']

# Legacy CIKs for companies that underwent restructuring
LEGACY_CIKS = {
    'GOOG': [
        (1652044, 'Alphabet Inc. (2015-present)'),
        (1288776, 'GOOGLE INC. (2004-2016)')
    ]
}

# Expected metrics (from MAG7 study)
REQUIRED_METRICS = [
    'Revenue', 'COGS', 'SGA', 'OperatingIncome', 'PretaxIncome', 'NetIncome',
    'OperatingCashFlow', 'Capex', 'TotalAssets', 'Goodwill', 'IntangibleAssets',
    'ShortTermDebt', 'LongTermDebt', 'CashAndEquivalents'
]

# Concept mapping: metric name -> list of XBRL concepts that represent it
CONCEPT_MAPPING = {
    'Revenue': [
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet', 'Revenues', 'Revenue', 'TotalRevenues', 'NetSales'
    ],
    'COGS': [
        'CostOfGoodsAndServicesSold', 'CostOfRevenue', 'CostOfGoodsSold', 'CostOfSales'
    ],
    'SGA': [
        'SellingGeneralAndAdministrativeExpense', 'SellingAndMarketingExpense',
        'GeneralAndAdministrativeExpense'
    ],
    'OperatingIncome': ['OperatingIncomeLoss'],
    'PretaxIncome': [
        'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItems',
        'IncomeLossFromContinuingOperationsBeforeIncomeTaxes'
    ],
    'NetIncome': ['NetIncomeLoss', 'ProfitLoss', 'NetIncome', 'NetEarnings'],
    'OperatingCashFlow': ['NetCashProvidedByUsedInOperatingActivities'],
    'Capex': ['PaymentsToAcquirePropertyPlantAndEquipment'],
    'TotalAssets': ['Assets', 'TotalAssets'],
    'Goodwill': ['Goodwill'],
    'IntangibleAssets': [
        'IntangibleAssetsNetExcludingGoodwill', 'FiniteLivedIntangibleAssetsNet',
        'IndefiniteLivedIntangibleAssetsExcludingGoodwill'
    ],
    'ShortTermDebt': ['ShortTermBorrowings', 'DebtCurrent'],
    'LongTermDebt': ['LongTermDebt', 'LongTermDebtNoncurrent'],
    'CashAndEquivalents': ['CashAndCashEquivalentsAtCarryingValue', 'CashAndCashEquivalents']
}


def get_unique_fiscal_periods(facts_df: pd.DataFrame, start_year: int = 2009, end_year: int = 2026) -> Set[Tuple[int, str]]:
    """
    Get unique fiscal periods from facts data.
    
    Returns set of (fiscal_year, fiscal_period) tuples, e.g., (2024, 'Q1'), (2023, 'FY').
    Filters to date range and deduplicates.
    """
    if facts_df is None or facts_df.empty:
        return set()
    
    periods = set()
    
    for _, row in facts_df.iterrows():
        fy = row.get('fiscal_year')
        fp = row.get('fiscal_period', 'FY')
        
        if fy and start_year <= int(fy) <= end_year:
            periods.add((int(fy), fp))
    
    return periods


def get_facts_for_company(ticker: str) -> Optional[pd.DataFrame]:
    """Fetch all facts for a company, merging legacy CIKs if applicable."""
    all_dfs = []
    
    ciks_to_fetch = LEGACY_CIKS.get(ticker, [(None, ticker)])
    
    for cik, desc in ciks_to_fetch:
        try:
            company = Company(cik) if cik else Company(ticker)
            facts = company.get_facts()
            
            if not facts:
                continue
            
            df = facts.to_dataframe(include_metadata=True)
            
            # Strip namespace from concept
            df['concept_stripped'] = df['concept'].apply(
                lambda x: x.split(':')[-1] if ':' in str(x) else x
            )
            
            all_dfs.append(df)
            
        except Exception as e:
            print(f"  Warning: Error getting facts for {desc}: {e}")
    
    if not all_dfs:
        return None
    
    combined = pd.concat(all_dfs, ignore_index=True)
    
    # Deduplicate by taking latest filing per (concept, fiscal_year, fiscal_period)
    combined = combined.sort_values('filing_date', ascending=False).drop_duplicates(
        subset=['concept', 'fiscal_year', 'fiscal_period']
    )
    
    return combined


def measure_coverage(ticker: str) -> Dict:
    """
    Measure coverage for a single company.
    
    Returns dict with:
    - total_periods: number of unique fiscal periods
    - metric_coverage: {metric: {found: N, missing: N, coverage_pct: X}}
    - unmapped_concepts: list of concepts we couldn't map
    """
    print(f"Processing {ticker}...")
    
    # Get facts first
    facts_df = get_facts_for_company(ticker)
    
    if facts_df is None or facts_df.empty:
        print(f"  No facts found")
        return {
            'ticker': ticker,
            'total_periods': 0,
            'metric_coverage': {m: {'found': 0, 'coverage_pct': 0.0} for m in REQUIRED_METRICS},
            'error': 'No facts found'
        }
    
    # Get unique fiscal periods from facts (denominator)
    periods = get_unique_fiscal_periods(facts_df)
    total_periods = len(periods)
    print(f"  Found {total_periods} unique fiscal periods, {len(facts_df)} facts")
    
    # Build set of all concepts we have
    all_concepts = set(facts_df['concept_stripped'].unique())
    
    # Measure coverage per metric
    metric_coverage = {}
    unmapped_concepts = []
    
    for metric, concepts in CONCEPT_MAPPING.items():
        # Which concepts for this metric exist in facts?
        matching_concepts = [c for c in concepts if c in all_concepts]
        
        if not matching_concepts:
            # Metric not found
            metric_coverage[metric] = {
                'found': 0,
                'coverage_pct': 0.0,
                'matched_concepts': []
            }
            continue
        
        # Count periods where metric has data
        metric_facts = facts_df[facts_df['concept_stripped'].isin(matching_concepts)]
        
        # Get unique periods with data
        periods_with_data = set()
        for _, row in metric_facts.iterrows():
            fy = row.get('fiscal_year')
            fp = row.get('fiscal_period', 'FY')
            if fy:
                periods_with_data.add((int(fy), fp))
        
        found = len(periods_with_data.intersection(periods))
        coverage_pct = (found / total_periods * 100) if total_periods > 0 else 0
        
        metric_coverage[metric] = {
            'found': found,
            'coverage_pct': round(coverage_pct, 1),
            'matched_concepts': matching_concepts
        }
    
    # Find unmapped concepts (concepts in facts not in our mapping)
    mapped_concepts = set()
    for concepts in CONCEPT_MAPPING.values():
        mapped_concepts.update(concepts)
    
    unmapped = all_concepts - mapped_concepts
    
    # Filter to likely financial concepts (skip internal/meta concepts)
    financial_keywords = ['revenue', 'income', 'asset', 'liabilit', 'equity', 'cash', 
                          'expense', 'cost', 'profit', 'loss', 'debt', 'tax']
    unmapped_financial = [
        c for c in unmapped 
        if any(kw in c.lower() for kw in financial_keywords)
    ]
    
    return {
        'ticker': ticker,
        'total_periods': total_periods,
        'metric_coverage': metric_coverage,
        'unmapped_concepts': sorted(unmapped_financial)[:50],  # Top 50
        'total_unmapped': len(unmapped_financial)
    }


def print_coverage_report(results: List[Dict]):
    """Print formatted coverage report."""
    print("\n" + "=" * 70)
    print("COVERAGE REPORT")
    print("=" * 70)
    
    # Summary table
    print("\n### Per-Company Summary ###\n")
    print(f"{'Ticker':<8} {'Periods':<10} {'Avg Coverage':<15} {'<95% Metrics'}")
    print("-" * 50)
    
    for r in results:
        ticker = r['ticker']
        periods = r['total_periods']
        
        if 'error' in r and not r['metric_coverage']:
            print(f"{ticker:<8} {periods:<10} {'ERROR':<15} {r.get('error', '')}")
            continue
        
        coverages = [m['coverage_pct'] for m in r['metric_coverage'].values()]
        avg_cov = sum(coverages) / len(coverages) if coverages else 0
        
        low_cov_metrics = [
            name for name, data in r['metric_coverage'].items() 
            if data['coverage_pct'] < 95
        ]
        
        status = '✅' if avg_cov >= 95 else '❌'
        print(f"{ticker:<8} {periods:<10} {avg_cov:>5.1f}% {status:<8} {', '.join(low_cov_metrics[:3])}")
    
    # Detailed per-metric breakdown
    print("\n### Per-Metric Coverage ###\n")
    
    # Aggregate across companies
    metric_totals = defaultdict(lambda: {'found': 0, 'total': 0})
    
    for r in results:
        total_periods = r['total_periods']
        for metric, data in r.get('metric_coverage', {}).items():
            metric_totals[metric]['found'] += data.get('found', 0)
            metric_totals[metric]['total'] += total_periods
    
    print(f"{'Metric':<25} {'Coverage':<12} {'Status'}")
    print("-" * 45)
    
    for metric in REQUIRED_METRICS:
        data = metric_totals[metric]
        if data['total'] > 0:
            pct = data['found'] / data['total'] * 100
            status = '✅' if pct >= 95 else '❌'
            print(f"{metric:<25} {pct:>5.1f}%       {status}")
        else:
            print(f"{metric:<25} {'N/A':<12} ❓")
    
    # Unmapped concepts
    print("\n### Top Unmapped Concepts ###\n")
    
    all_unmapped = defaultdict(int)
    for r in results:
        for concept in r.get('unmapped_concepts', []):
            all_unmapped[concept] += 1
    
    sorted_unmapped = sorted(all_unmapped.items(), key=lambda x: -x[1])[:20]
    
    for concept, count in sorted_unmapped:
        print(f"  {concept} (appears in {count} companies)")


def main():
    parser = argparse.ArgumentParser(description='Measure concept mapping coverage')
    parser.add_argument('--companies', nargs='+', default=['MAG7'],
                        help='Company tickers or "MAG7" for all MAG7 companies')
    parser.add_argument('--output', type=str, default=None,
                        help='Output JSON file for results')
    parser.add_argument('--identity', type=str, default='Dev Gunning developer-gunning@gmail.com',
                        help='SEC API identity string')
    
    args = parser.parse_args()
    
    # Set identity
    set_identity(args.identity)
    
    # Resolve company list
    if args.companies == ['MAG7']:
        tickers = MAG7
    else:
        tickers = args.companies
    
    print(f"Measuring coverage for: {', '.join(tickers)}")
    print("-" * 50)
    
    # Measure each company
    results = []
    for ticker in tickers:
        result = measure_coverage(ticker)
        results.append(result)
    
    # Print report
    print_coverage_report(results)
    
    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {output_path}")


if __name__ == '__main__':
    main()
