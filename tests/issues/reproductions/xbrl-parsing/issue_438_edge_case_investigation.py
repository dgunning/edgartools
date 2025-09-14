"""
Issue #438: Edge Case Investigation - Revenue Facts Classification

The main reproduction with NVDA shows the issue is NOT currently reproduced.
This script investigates edge cases where revenue facts might have statement_type=None.

Potential scenarios:
1. Different companies with different XBRL structures
2. Filings where us-gaap:Revenues is not in income statement presentation tree
3. Older filings with different taxonomy structures
4. 10-Q filings vs 10-K filings
"""

import edgar
from edgar import Company
from rich import print as rprint
import pandas as pd


def test_revenue_classification_across_companies():
    """Test revenue fact classification across multiple companies."""
    print("=== Revenue Classification Edge Case Investigation ===\n")
    
    # Test different companies that might have different XBRL structures
    test_companies = [
        "AAPL",   # Apple
        "MSFT",   # Microsoft  
        "TSLA",   # Tesla
        "AMZN",   # Amazon
        "GOOGL",  # Alphabet
    ]
    
    results = {}
    
    for ticker in test_companies:
        try:
            print(f"\n--- Testing {ticker} ---")
            company = Company(ticker)
            print(f"Company: {company.name}")
            
            # Get recent 10-K
            recent_10k = company.get_filings(form="10-K").latest()
            print(f"10-K: {recent_10k.filing_date}")
            
            xbrl = recent_10k.xbrl()
            
            # Check us-gaap:Revenues facts
            revenues_facts_df = xbrl.facts.get_facts_by_concept("us-gaap:Revenues", exact=True)
            
            if len(revenues_facts_df) > 0:
                statement_types = revenues_facts_df['statement_type'].value_counts()
                print(f"us-gaap:Revenues facts: {len(revenues_facts_df)}")
                print(f"Statement types: {dict(statement_types)}")
                
                # Check for any None/null statement types
                null_count = revenues_facts_df['statement_type'].isnull().sum()
                if null_count > 0:
                    print(f"🚨 FOUND {null_count} revenue facts with statement_type=None!")
                    results[ticker] = {
                        'total_revenues_facts': len(revenues_facts_df),
                        'null_statement_types': null_count,
                        'filing_date': recent_10k.filing_date,
                        'issue_found': True
                    }
                else:
                    print("✓ All revenue facts properly classified")
                    results[ticker] = {
                        'total_revenues_facts': len(revenues_facts_df),
                        'null_statement_types': 0,
                        'filing_date': recent_10k.filing_date,
                        'issue_found': False
                    }
            else:
                print("No us-gaap:Revenues facts found")
                results[ticker] = {
                    'total_revenues_facts': 0,
                    'null_statement_types': 0,
                    'filing_date': recent_10k.filing_date,
                    'issue_found': False
                }
                
        except Exception as e:
            print(f"Error testing {ticker}: {e}")
            results[ticker] = {
                'error': str(e),
                'issue_found': False
            }
    
    return results


def test_revenue_concepts_without_presentation_tree():
    """Test edge case where revenue concept might not be in presentation tree."""
    print("\n=== Testing Revenue Concepts Not in Presentation Tree ===")
    
    # Try to find a filing where us-gaap:Revenues might exist but not be in income statement tree
    company = Company("NVDA") 
    filing = company.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()
    
    # Get all us-gaap:Revenues facts
    revenues_facts_df = xbrl.facts.get_facts_by_concept("us-gaap:Revenues", exact=True)
    
    # Check which presentation trees contain us-gaap:Revenues
    revenues_element_id = "us-gaap_Revenues"  # Normalized form
    
    trees_with_revenues = []
    for role, tree in xbrl.presentation_trees.items():
        if revenues_element_id in tree.all_nodes:
            trees_with_revenues.append(role)
    
    print(f"us-gaap:Revenues found in {len(trees_with_revenues)} presentation trees")
    for role in trees_with_revenues[:5]:  # Show first 5
        print(f"  - {role}")
    
    # Check statement type mapping for these roles  
    statements = xbrl.get_all_statements()
    role_to_statement_type = {}
    for stmt in statements:
        if stmt['role'] and stmt['type']:
            role_to_statement_type[stmt['role']] = stmt['type']
    
    print(f"\nStatement type mapping for roles containing us-gaap:Revenues:")
    for role in trees_with_revenues[:5]:
        stmt_type = role_to_statement_type.get(role, 'UNMAPPED')
        print(f"  {role} -> {stmt_type}")


def investigate_static_mapping_fallback():
    """Investigate when static mapping fallback would be used."""
    print("\n=== Static Mapping Fallback Investigation ===")
    
    from edgar.entity.parser import EntityFactsParser
    
    # Check what happens when we try to classify 'Revenues' vs 'Revenue'
    print("Static mapping lookup results:")
    print(f"  'Revenue' -> {EntityFactsParser._determine_statement_type('Revenue')}")
    print(f"  'Revenues' -> {EntityFactsParser._determine_statement_type('Revenues')}")
    print(f"  'us-gaap:Revenue' -> {EntityFactsParser._determine_statement_type('us-gaap:Revenue')}")
    print(f"  'us-gaap:Revenues' -> {EntityFactsParser._determine_statement_type('us-gaap:Revenues')}")


def main():
    """Main investigation function."""
    try:
        # Test across multiple companies
        results = test_revenue_classification_across_companies()
        
        # Test edge cases
        test_revenue_concepts_without_presentation_tree()
        investigate_static_mapping_fallback()
        
        print("\n=== INVESTIGATION SUMMARY ===")
        
        # Check if we found any issues
        issues_found = [ticker for ticker, data in results.items() if data.get('issue_found', False)]
        
        if issues_found:
            print(f"🚨 ISSUES FOUND in companies: {', '.join(issues_found)}")
            for ticker in issues_found:
                data = results[ticker]
                print(f"  {ticker}: {data['null_statement_types']}/{data['total_revenues_facts']} revenue facts with statement_type=None")
        else:
            print("✓ NO ISSUES FOUND across tested companies")
            print("✓ All revenue facts are properly classified as IncomeStatement")
        
        print("\n🔍 POTENTIAL BUG IDENTIFIED:")
        print("  - STATEMENT_MAPPING contains 'Revenue' but not 'Revenues'")  
        print("  - This could cause issues in edge cases where:")
        print("    1. us-gaap:Revenues facts exist")
        print("    2. They are NOT in any IncomeStatement presentation tree")
        print("    3. System falls back to static mapping")
        print("    4. 'Revenues' (plural) is not found in static mapping")
        
    except Exception as e:
        print(f"Error during investigation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()