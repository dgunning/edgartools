#!/usr/bin/env python3
"""
02_compare_mag7_trees.py - Compare Calculation Trees Across MAG7 Companies

This script analyzes how calculation tree structures differ across
the 7 major tech companies (MAG7).

Research Questions:
1. How many calculation trees does each company report?
2. Do all companies have the same core statement trees?
3. What are the common vs unique tree structures?

Usage:
    python 02_compare_mag7_trees.py
"""

from edgar import Company, set_identity
from collections import defaultdict
import json
import pandas as pd

set_identity("Dev Gunning developer-gunning@gmail.com")

MAG7 = ['GOOG', 'AMZN', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'META']

# Core statement patterns we expect to find
CORE_STATEMENTS = {
    'income': ['INCOME', 'OPERATIONS', 'EARNINGS'],
    'balance': ['BALANCE', 'FINANCIAL POSITION'],
    'cashflow': ['CASHFLOW', 'CASH FLOWS']
}


def get_latest_10k_trees(ticker: str) -> dict:
    """Get calculation trees from latest 10-K for a company."""
    try:
        c = Company(ticker)
        filings = c.get_filings(form='10-K')
        if not filings:
            return None
        
        f = filings[0]
        xbrl = f.xbrl()
        
        trees_info = {
            'ticker': ticker,
            'filing_date': str(f.filing_date),
            'accession': f.accession_no,
            'tree_count': len(xbrl.calculation_trees),
            'trees': []
        }
        
        for role, tree in xbrl.calculation_trees.items():
            name = role.split('/')[-1] if '/' in role else role
            root = tree.root_element_id.replace('us-gaap_', '').replace(f'{ticker.lower()}_', '[custom] ')
            
            # Classify the tree
            name_upper = name.upper()
            statement_type = 'other'
            for stype, patterns in CORE_STATEMENTS.items():
                if any(p in name_upper for p in patterns):
                    statement_type = stype
                    break
            
            # Get all concepts in this tree
            concepts = list(tree.all_nodes.keys())
            
            trees_info['trees'].append({
                'name': name,
                'definition': tree.definition,
                'root': root,
                'node_count': len(tree.all_nodes),
                'statement_type': statement_type,
                'concepts': [c.replace('us-gaap_', '') for c in concepts]
            })
        
        return trees_info
        
    except Exception as e:
        print(f"  Error processing {ticker}: {e}")
        return None


def analyze_results(all_data: list) -> dict:
    """Analyze the collected data."""
    analysis = {
        'summary': {},
        'core_trees': {},
        'concept_frequency': defaultdict(int)
    }
    
    # Summary stats
    for company in all_data:
        ticker = company['ticker']
        analysis['summary'][ticker] = {
            'tree_count': company['tree_count'],
            'filing_date': company['filing_date'],
            'income_trees': len([t for t in company['trees'] if t['statement_type'] == 'income']),
            'balance_trees': len([t for t in company['trees'] if t['statement_type'] == 'balance']),
            'cashflow_trees': len([t for t in company['trees'] if t['statement_type'] == 'cashflow']),
        }
        
        # Count concept frequency
        for tree in company['trees']:
            for concept in tree['concepts']:
                analysis['concept_frequency'][concept] += 1
    
    return analysis


def main():
    print("=" * 70)
    print("MAG7 CALCULATION TREE COMPARISON")
    print("=" * 70)
    
    all_data = []
    
    for ticker in MAG7:
        print(f"\nProcessing {ticker}...")
        data = get_latest_10k_trees(ticker)
        if data:
            all_data.append(data)
            print(f"  Found {data['tree_count']} trees (filing: {data['filing_date']})")
    
    # Analyze
    analysis = analyze_results(all_data)
    
    # Print summary table
    print("\n" + "=" * 70)
    print("SUMMARY: Tree Counts by Company")
    print("=" * 70)
    
    df_data = []
    for ticker, stats in analysis['summary'].items():
        df_data.append({
            'Ticker': ticker,
            'Total': stats['tree_count'],
            'Income': stats['income_trees'],
            'Balance': stats['balance_trees'],
            'CashFlow': stats['cashflow_trees'],
            'Other': stats['tree_count'] - stats['income_trees'] - stats['balance_trees'] - stats['cashflow_trees'],
            'Filing': stats['filing_date']
        })
    
    df = pd.DataFrame(df_data)
    print(df.to_string(index=False))
    
    # Core concepts present in all companies
    print("\n" + "=" * 70)
    print("CONCEPTS PRESENT IN ALL 7 COMPANIES")
    print("=" * 70)
    
    universal_concepts = [c for c, count in analysis['concept_frequency'].items() if count >= 7]
    print(f"\nFound {len(universal_concepts)} universal concepts:")
    for c in sorted(universal_concepts)[:30]:
        print(f"  - {c}")
    if len(universal_concepts) > 30:
        print(f"  ... and {len(universal_concepts) - 30} more")
    
    # Save raw data
    output_file = "mag7_trees_comparison.json"
    with open(output_file, 'w') as f:
        json.dump({
            'companies': all_data,
            'analysis': {
                'summary': analysis['summary'],
                'universal_concepts': universal_concepts
            }
        }, f, indent=2, default=str)
    
    print(f"\n\nFull data saved to {output_file}")


if __name__ == "__main__":
    main()
