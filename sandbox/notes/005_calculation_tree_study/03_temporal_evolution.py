#!/usr/bin/env python3
"""
03_temporal_evolution.py - Track Calculation Tree Evolution Over Time

This script analyzes how calculation trees change over time for each company.

Research Questions:
1. Do calculation tree structures remain stable across years?
2. When do companies add/remove trees?
3. Do concept names change over time?

Usage:
    python 03_temporal_evolution.py
    python 03_temporal_evolution.py --ticker AAPL --years 5
"""

from edgar import Company, set_identity
from collections import defaultdict
import json
import argparse

set_identity("Dev Gunning developer-gunning@gmail.com")

MAG7 = ['GOOG', 'AMZN', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'META']


def get_10k_trees_for_years(ticker: str, num_years: int = 5) -> list:
    """Get calculation trees from multiple years of 10-K filings."""
    results = []
    
    try:
        c = Company(ticker)
        filings = c.get_filings(form='10-K')
        
        for i, f in enumerate(filings[:num_years]):
            try:
                xbrl = f.xbrl()
                
                trees_info = {
                    'year': f.filing_date.year if hasattr(f.filing_date, 'year') else str(f.filing_date)[:4],
                    'filing_date': str(f.filing_date),
                    'tree_count': len(xbrl.calculation_trees),
                    'trees': {}
                }
                
                for role, tree in xbrl.calculation_trees.items():
                    name = role.split('/')[-1] if '/' in role else role
                    trees_info['trees'][name] = {
                        'root': tree.root_element_id,
                        'node_count': len(tree.all_nodes),
                        'concepts': set(tree.all_nodes.keys())
                    }
                
                results.append(trees_info)
                print(f"  {f.filing_date}: {len(xbrl.calculation_trees)} trees")
                
            except Exception as e:
                print(f"  Error parsing {f.filing_date}: {e}")
                
    except Exception as e:
        print(f"Error getting filings for {ticker}: {e}")
    
    return results


def analyze_evolution(ticker: str, yearly_data: list) -> dict:
    """Analyze how trees changed over time."""
    if len(yearly_data) < 2:
        return {'error': 'Need at least 2 years of data'}
    
    analysis = {
        'ticker': ticker,
        'years_analyzed': len(yearly_data),
        'tree_count_trend': [],
        'stable_trees': [],
        'added_trees': [],
        'removed_trees': [],
        'concept_changes': {}
    }
    
    # Tree count trend
    for yd in yearly_data:
        analysis['tree_count_trend'].append({
            'year': yd['year'],
            'count': yd['tree_count']
        })
    
    # Compare first and last year
    first = yearly_data[-1]  # Oldest
    last = yearly_data[0]    # Most recent
    
    first_trees = set(first['trees'].keys())
    last_trees = set(last['trees'].keys())
    
    analysis['stable_trees'] = list(first_trees & last_trees)
    analysis['added_trees'] = list(last_trees - first_trees)
    analysis['removed_trees'] = list(first_trees - last_trees)
    
    # For stable trees, check if concepts changed
    for tree_name in analysis['stable_trees'][:5]:  # Check top 5
        if tree_name in first['trees'] and tree_name in last['trees']:
            first_concepts = first['trees'][tree_name]['concepts']
            last_concepts = last['trees'][tree_name]['concepts']
            
            added = last_concepts - first_concepts
            removed = first_concepts - last_concepts
            
            if added or removed:
                analysis['concept_changes'][tree_name] = {
                    'added': len(added),
                    'removed': len(removed)
                }
    
    return analysis


def main():
    parser = argparse.ArgumentParser(description='Analyze calculation tree evolution')
    parser.add_argument('--ticker', type=str, default=None, help='Single ticker to analyze')
    parser.add_argument('--years', type=int, default=5, help='Number of years to analyze')
    args = parser.parse_args()
    
    tickers = [args.ticker] if args.ticker else MAG7
    
    print("=" * 70)
    print("CALCULATION TREE TEMPORAL EVOLUTION")
    print("=" * 70)
    
    all_analysis = {}
    
    for ticker in tickers:
        print(f"\n{'='*50}")
        print(f"Analyzing {ticker} ({args.years} years)")
        print('='*50)
        
        yearly_data = get_10k_trees_for_years(ticker, args.years)
        
        if yearly_data:
            analysis = analyze_evolution(ticker, yearly_data)
            all_analysis[ticker] = analysis
            
            # Print summary
            print(f"\nTree count trend:")
            for tc in analysis.get('tree_count_trend', []):
                print(f"  {tc['year']}: {tc['count']} trees")
            
            print(f"\nStability:")
            print(f"  Stable trees: {len(analysis.get('stable_trees', []))}")
            print(f"  Added trees: {len(analysis.get('added_trees', []))}")
            print(f"  Removed trees: {len(analysis.get('removed_trees', []))}")
            
            if analysis.get('concept_changes'):
                print(f"\nConcept changes in stable trees:")
                for name, changes in analysis['concept_changes'].items():
                    print(f"  {name}: +{changes['added']}/-{changes['removed']}")
    
    # Save results
    output_file = "mag7_temporal_evolution.json"
    with open(output_file, 'w') as f:
        json.dump(all_analysis, f, indent=2, default=str)
    
    print(f"\n\nResults saved to {output_file}")


if __name__ == "__main__":
    main()
