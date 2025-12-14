"""
DEF 14A (Proxy Statement) Data Extraction Examples

This script demonstrates reliable extraction patterns for DEF 14A filings
based on comprehensive research across 5 diverse companies (AAPL, MSFT, JPM, XOM, JNJ).

All examples use XBRL data, which is present in 100% of sampled DEF 14A filings
and provides highly structured, reliable data extraction.

Research Document: def-14a-comprehensive-guide.md
Research Date: 2025-12-10
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from edgar import Company, set_identity

# Set SEC identity (required)
set_identity("Research research@example.com")


def get_latest_def14a_filing(ticker: str):
    """Get the most recent DEF 14A filing for a company."""
    company = Company(ticker)
    filings = company.get_filings(form="DEF 14A").head(1)
    if len(filings) > 0:
        return filings[0]
    return None


def extract_concept_series(facts_df: pd.DataFrame, concept: str) -> pd.DataFrame:
    """
    Extract a time series for a specific XBRL concept.

    Returns DataFrame with period_end and value columns.
    """
    data = facts_df[facts_df['concept'] == concept].copy()
    if len(data) > 0:
        result = data[['period_end', 'numeric_value']].copy()
        result = result.sort_values('period_end')
        result.columns = ['period', 'value']
        return result
    return pd.DataFrame(columns=['period', 'value'])


def extract_concept_value(facts_df: pd.DataFrame, concept: str) -> Optional[str]:
    """Extract the first value for a specific XBRL concept (typically a text field)."""
    data = facts_df[facts_df['concept'] == concept]
    if len(data) > 0:
        return data.iloc[0]['value']
    return None


# =============================================================================
# EXAMPLE 1: Executive Compensation Time Series
# =============================================================================

def extract_executive_compensation(ticker: str) -> Dict[str, Any]:
    """
    Extract executive compensation metrics from DEF 14A XBRL data.

    Returns dictionary with PEO and NEO compensation over 5 years.

    Data includes:
    - PEO total compensation (Summary Compensation Table)
    - PEO compensation actually paid (Pay vs Performance)
    - Non-PEO NEO average compensation
    """
    filing = get_latest_def14a_filing(ticker)
    if not filing:
        return None

    xbrl = filing.xbrl()
    facts_df = xbrl.facts.to_dataframe()

    # Extract key compensation concepts
    data = {
        'ticker': ticker,
        'filing_date': str(filing.filing_date),
        'peo_total_comp': extract_concept_series(facts_df, 'ecd:PeoTotalCompAmt'),
        'peo_actually_paid': extract_concept_series(facts_df, 'ecd:PeoActuallyPaidCompAmt'),
        'neo_total_comp': extract_concept_series(facts_df, 'ecd:NonPeoNeoAvgTotalCompAmt'),
        'neo_actually_paid': extract_concept_series(facts_df, 'ecd:NonPeoNeoAvgCompActuallyPaidAmt')
    }

    return data


def display_executive_compensation(ticker: str):
    """Display executive compensation in a readable format."""
    data = extract_executive_compensation(ticker)

    if not data:
        print(f"No DEF 14A filing found for {ticker}")
        return

    print("=" * 80)
    print(f"EXECUTIVE COMPENSATION: {ticker}")
    print(f"Filing Date: {data['filing_date']}")
    print("=" * 80)

    # Merge PEO data
    peo_df = pd.merge(
        data['peo_total_comp'],
        data['peo_actually_paid'],
        on='period',
        suffixes=('_sct', '_paid')
    )

    print("\nPrincipal Executive Officer (CEO) Compensation:")
    print(peo_df.to_string(index=False))

    # Merge NEO data
    neo_df = pd.merge(
        data['neo_total_comp'],
        data['neo_actually_paid'],
        on='period',
        suffixes=('_sct', '_paid')
    )

    print("\nNon-PEO Named Executive Officers (Average) Compensation:")
    print(neo_df.to_string(index=False))


# =============================================================================
# EXAMPLE 2: Pay vs Performance Analysis
# =============================================================================

def extract_pay_vs_performance(ticker: str) -> pd.DataFrame:
    """
    Extract pay vs performance metrics from DEF 14A.

    Returns DataFrame with:
    - Total Shareholder Return (TSR)
    - Peer Group TSR
    - Net Income
    - PEO Compensation Actually Paid
    - Company-selected performance measure
    """
    filing = get_latest_def14a_filing(ticker)
    if not filing:
        return None

    xbrl = filing.xbrl()
    facts_df = xbrl.facts.to_dataframe()

    # Extract performance metrics
    metrics = {
        'tsr': extract_concept_series(facts_df, 'ecd:TotalShareholderRtnAmt'),
        'peer_tsr': extract_concept_series(facts_df, 'ecd:PeerGroupTotalShareholderRtnAmt'),
        'net_income': extract_concept_series(facts_df, 'us-gaap:NetIncomeLoss'),
        'peo_comp': extract_concept_series(facts_df, 'ecd:PeoActuallyPaidCompAmt'),
        'company_measure': extract_concept_series(facts_df, 'ecd:CoSelectedMeasureAmt')
    }

    # Get measure name
    measure_name = extract_concept_value(facts_df, 'ecd:CoSelectedMeasureName')

    # Merge all metrics
    pvp_df = metrics['tsr'].copy()
    for name, df in metrics.items():
        if name != 'tsr':
            pvp_df = pd.merge(pvp_df, df, on='period', how='outer', suffixes=('', f'_{name}'))

    # Rename columns
    pvp_df.columns = ['period', 'tsr', 'peer_tsr', 'net_income', 'peo_comp', 'company_measure']

    return pvp_df, measure_name


def display_pay_vs_performance(ticker: str):
    """Display pay vs performance metrics."""
    result = extract_pay_vs_performance(ticker)

    if not result:
        print(f"No DEF 14A filing found for {ticker}")
        return

    pvp_df, measure_name = result

    print("=" * 80)
    print(f"PAY VS PERFORMANCE: {ticker}")
    print("=" * 80)

    print(f"\nCompany-Selected Performance Measure: {measure_name}")

    print("\n5-Year Performance Metrics:")
    print(pvp_df.to_string(index=False))

    # Calculate correlation
    if len(pvp_df) > 1:
        print("\nPay-for-Performance Correlation:")
        corr = pvp_df[['peo_comp', 'tsr', 'net_income']].corr()
        print("\nPEO Compensation Actually Paid vs:")
        print(f"  TSR:        {corr.loc['peo_comp', 'tsr']:.3f}")
        print(f"  Net Income: {corr.loc['peo_comp', 'net_income']:.3f}")


# =============================================================================
# EXAMPLE 3: Named Executive Officers
# =============================================================================

def extract_named_executives(ticker: str) -> List[Dict[str, str]]:
    """
    Extract named executive officers from DEF 14A.

    Returns list of executives with their member IDs (if dimensionally tagged).
    """
    filing = get_latest_def14a_filing(ticker)
    if not filing:
        return None

    xbrl = filing.xbrl()
    facts_df = xbrl.facts.to_dataframe()

    # Extract PEO names
    peo_names = facts_df[facts_df['concept'] == 'ecd:PeoName']

    executives = []

    if 'dim_ecd_IndividualAxis' in facts_df.columns and peo_names['dim_ecd_IndividualAxis'].notna().any():
        # Dimensional tagging available
        for idx, row in peo_names.iterrows():
            if pd.notna(row['dim_ecd_IndividualAxis']):
                executives.append({
                    'name': row['value'],
                    'member_id': row['dim_ecd_IndividualAxis'],
                    'category': row.get('dim_ecd_ExecutiveCategoryAxis', 'Unknown'),
                    'period': str(row['period_end'])
                })
    else:
        # Only aggregate data available
        unique_names = peo_names['value'].unique()
        for name in unique_names:
            executives.append({
                'name': name,
                'member_id': 'Not dimensionally tagged',
                'category': 'PEO',
                'period': 'Multiple periods'
            })

    return executives


def display_named_executives(ticker: str):
    """Display named executive officers."""
    executives = extract_named_executives(ticker)

    if not executives:
        print(f"No DEF 14A filing found for {ticker}")
        return

    print("=" * 80)
    print(f"NAMED EXECUTIVE OFFICERS: {ticker}")
    print("=" * 80)

    for exec_info in executives:
        print(f"\nName: {exec_info['name']}")
        print(f"  Category: {exec_info['category']}")
        print(f"  Member ID: {exec_info['member_id']}")
        print(f"  Period: {exec_info['period']}")


# =============================================================================
# EXAMPLE 4: Comprehensive DEF 14A Data Extraction
# =============================================================================

def extract_comprehensive_def14a_data(ticker: str) -> Dict[str, Any]:
    """
    Extract all available XBRL data from a DEF 14A filing.

    This is the recommended function for a SaaS application MVP.

    Returns dictionary with:
    - Company metadata
    - Executive compensation (PEO and NEO)
    - Pay vs performance metrics
    - Named executives
    - Insider trading policy status
    """
    filing = get_latest_def14a_filing(ticker)
    if not filing:
        return None

    xbrl = filing.xbrl()
    facts_df = xbrl.facts.to_dataframe()

    # Extract all key data
    data = {
        'metadata': {
            'ticker': ticker,
            'filing_date': str(filing.filing_date),
            'accession_number': filing.accession_number,
            'cik': extract_concept_value(facts_df, 'dei:EntityCentralIndexKey'),
            'company_name': extract_concept_value(facts_df, 'dei:EntityRegistrantName')
        },
        'compensation': {
            'peo_total_comp': extract_concept_series(facts_df, 'ecd:PeoTotalCompAmt').to_dict('records'),
            'peo_actually_paid': extract_concept_series(facts_df, 'ecd:PeoActuallyPaidCompAmt').to_dict('records'),
            'neo_avg_total_comp': extract_concept_series(facts_df, 'ecd:NonPeoNeoAvgTotalCompAmt').to_dict('records'),
            'neo_avg_actually_paid': extract_concept_series(facts_df, 'ecd:NonPeoNeoAvgCompActuallyPaidAmt').to_dict('records')
        },
        'performance': {
            'tsr': extract_concept_series(facts_df, 'ecd:TotalShareholderRtnAmt').to_dict('records'),
            'peer_tsr': extract_concept_series(facts_df, 'ecd:PeerGroupTotalShareholderRtnAmt').to_dict('records'),
            'net_income': extract_concept_series(facts_df, 'us-gaap:NetIncomeLoss').to_dict('records'),
            'company_measure_name': extract_concept_value(facts_df, 'ecd:CoSelectedMeasureName'),
            'company_measure_values': extract_concept_series(facts_df, 'ecd:CoSelectedMeasureAmt').to_dict('records')
        },
        'executives': extract_named_executives(ticker),
        'governance': {
            'insider_trading_policy_adopted': extract_concept_value(facts_df, 'ecd:InsiderTrdPoliciesProcAdoptedFlag')
        },
        'statistics': {
            'total_xbrl_facts': len(facts_df),
            'unique_concepts': len(facts_df['concept'].unique())
        }
    }

    return data


def display_comprehensive_summary(ticker: str):
    """Display comprehensive DEF 14A data summary."""
    data = extract_comprehensive_def14a_data(ticker)

    if not data:
        print(f"No DEF 14A filing found for {ticker}")
        return

    print("=" * 80)
    print(f"DEF 14A COMPREHENSIVE DATA: {ticker}")
    print("=" * 80)

    # Metadata
    print("\nCOMPANY INFORMATION:")
    print(f"  Name: {data['metadata']['company_name']}")
    print(f"  CIK: {data['metadata']['cik']}")
    print(f"  Filing Date: {data['metadata']['filing_date']}")
    print(f"  Accession: {data['metadata']['accession_number']}")

    # Statistics
    print("\nXBRL DATA STATISTICS:")
    print(f"  Total Facts: {data['statistics']['total_xbrl_facts']}")
    print(f"  Unique Concepts: {data['statistics']['unique_concepts']}")

    # Compensation summary
    print("\nCOMPENSATION SUMMARY (Most Recent Year):")
    if data['compensation']['peo_actually_paid']:
        latest_peo = data['compensation']['peo_actually_paid'][-1]
        print(f"  PEO Compensation Actually Paid: ${latest_peo['value']:,.0f}")

    if data['compensation']['neo_avg_actually_paid']:
        latest_neo = data['compensation']['neo_avg_actually_paid'][-1]
        print(f"  NEO Avg Compensation Actually Paid: ${latest_neo['value']:,.0f}")

    # Performance summary
    print("\nPERFORMANCE SUMMARY (Most Recent Year):")
    if data['performance']['tsr']:
        latest_tsr = data['performance']['tsr'][-1]
        print(f"  Total Shareholder Return: {latest_tsr['value']:.1f}%")

    if data['performance']['net_income']:
        latest_ni = data['performance']['net_income'][-1]
        print(f"  Net Income: ${latest_ni['value']:,.0f}")

    print(f"  Company-Selected Measure: {data['performance']['company_measure_name']}")

    # Executives
    print(f"\nNAMED EXECUTIVE OFFICERS: {len(data['executives'])} total")
    for exec_info in data['executives'][:5]:  # Show first 5
        print(f"  - {exec_info['name']} ({exec_info['category']})")

    # Governance
    print("\nGOVERNANCE:")
    print(f"  Insider Trading Policy Adopted: {data['governance']['insider_trading_policy_adopted']}")


# =============================================================================
# EXAMPLE 5: Peer Group Comparison
# =============================================================================

def compare_peer_compensation(tickers: List[str]) -> pd.DataFrame:
    """
    Compare executive compensation across multiple companies.

    Useful for peer benchmarking analysis.
    """
    results = []

    for ticker in tickers:
        data = extract_comprehensive_def14a_data(ticker)
        if data:
            # Get most recent year data
            if data['compensation']['peo_actually_paid']:
                latest_peo = data['compensation']['peo_actually_paid'][-1]
                peo_comp = latest_peo['value']
            else:
                peo_comp = None

            if data['performance']['tsr']:
                latest_tsr = data['performance']['tsr'][-1]
                tsr = latest_tsr['value']
            else:
                tsr = None

            results.append({
                'ticker': ticker,
                'company': data['metadata']['company_name'],
                'filing_date': data['metadata']['filing_date'],
                'peo_comp_actually_paid': peo_comp,
                'tsr': tsr,
                'company_measure': data['performance']['company_measure_name']
            })

    return pd.DataFrame(results)


def display_peer_comparison(tickers: List[str]):
    """Display peer group compensation comparison."""
    comparison_df = compare_peer_compensation(tickers)

    print("=" * 80)
    print("PEER GROUP COMPENSATION COMPARISON")
    print("=" * 80)
    print(comparison_df.to_string(index=False))

    if len(comparison_df) > 0:
        print("\nSUMMARY STATISTICS:")
        print(f"  Average PEO Compensation: ${comparison_df['peo_comp_actually_paid'].mean():,.0f}")
        print(f"  Median PEO Compensation: ${comparison_df['peo_comp_actually_paid'].median():,.0f}")
        print(f"  Average TSR: {comparison_df['tsr'].mean():.1f}%")
        print(f"  Median TSR: {comparison_df['tsr'].median():.1f}%")


# =============================================================================
# MAIN DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("DEF 14A DATA EXTRACTION EXAMPLES")
    print("=" * 80)

    # Example 1: Executive Compensation
    print("\n\nEXAMPLE 1: EXECUTIVE COMPENSATION TIME SERIES")
    print("-" * 80)
    display_executive_compensation("AAPL")

    # Example 2: Pay vs Performance
    print("\n\nEXAMPLE 2: PAY VS PERFORMANCE ANALYSIS")
    print("-" * 80)
    display_pay_vs_performance("MSFT")

    # Example 3: Named Executives
    print("\n\nEXAMPLE 3: NAMED EXECUTIVE OFFICERS")
    print("-" * 80)
    display_named_executives("JPM")

    # Example 4: Comprehensive Data
    print("\n\nEXAMPLE 4: COMPREHENSIVE DEF 14A DATA")
    print("-" * 80)
    display_comprehensive_summary("XOM")

    # Example 5: Peer Comparison
    print("\n\nEXAMPLE 5: PEER GROUP COMPARISON")
    print("-" * 80)
    tech_peers = ["AAPL", "MSFT"]
    display_peer_comparison(tech_peers)

    print("\n" + "=" * 80)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 80)
