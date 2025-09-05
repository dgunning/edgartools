"""
Reproduction script for GitHub Issue #334
https://github.com/dgunning/edgartools/issues/334

Issue: Inconsistent sign for XBRL fact us-gaap_ResearchAndDevelopmentExpense

For some companies (like MSFT), EdgarTools reports negative values for 
ResearchAndDevelopmentExpense while the SEC filing and CompanyFacts API show 
positive values. For other companies (like AAPL), the signs are consistent.

This script reproduces the issue and verifies the current behavior.
"""

import pandas as pd
from edgar import get_by_accession_number
from decimal import Decimal


def test_msft_research_development_expense():
    """Test MSFT 10-K 2024 - should show inconsistent sign (negative in edgartools)."""
    print("=== Testing MSFT 10-K 2024 ===")
    print("Accession: 0000950170-24-087843")
    
    filing = get_by_accession_number("0000950170-24-087843")
    xbrl_data = filing.xbrl()
    
    # Get facts as DataFrame and filter for R&D
    facts_df = xbrl_data.facts.to_dataframe()
    rnd_mask = facts_df['concept'].str.contains('ResearchAndDevelopment', na=False) & \
               (facts_df['concept'] == 'us-gaap:ResearchAndDevelopmentExpense')
    rnd_facts = facts_df[rnd_mask]
    
    print(f"Found {len(rnd_facts)} R&D facts")
    
    if len(rnd_facts) > 0:
        print("\nR&D Facts:")
        for _, fact in rnd_facts.iterrows():
            print(f"  Concept: {fact['concept']}")
            print(f"  Value: {fact['value']}")
            print(f"  Numeric Value: {fact['numeric_value']}")
            print(f"  Context: {fact['context_ref']}")
            print(f"  Period: {fact.get('period_start', 'N/A')} to {fact.get('period_end', 'N/A')}")
            print()
        
        # Check for negative values
        negative_count = len(rnd_facts[rnd_facts['numeric_value'] < 0])
        print(f"Found {negative_count} facts with negative values")
        return negative_count > 0
    
    return False


def test_aapl_research_development_expense():
    """Test AAPL 10-K 2024 - should show consistent sign (positive in edgartools)."""
    print("\n=== Testing AAPL 10-K 2024 ===") 
    print("Accession: 0000320193-24-000123")
    
    filing = get_by_accession_number("0000320193-24-000123")
    xbrl_data = filing.xbrl()
    
    # Get facts as DataFrame and filter for R&D
    facts_df = xbrl_data.facts.to_dataframe()
    rnd_mask = facts_df['concept'].str.contains('ResearchAndDevelopment', na=False) & \
               (facts_df['concept'] == 'us-gaap:ResearchAndDevelopmentExpense')
    rnd_facts = facts_df[rnd_mask]
    
    print(f"Found {len(rnd_facts)} R&D facts")
    
    if len(rnd_facts) > 0:
        print("\nR&D Facts:")
        for _, fact in rnd_facts.iterrows():
            print(f"  Concept: {fact['concept']}")
            print(f"  Value: {fact['value']}")
            print(f"  Numeric Value: {fact['numeric_value']}")
            print(f"  Context: {fact['context_ref']}")
            print(f"  Period: {fact.get('period_start', 'N/A')} to {fact.get('period_end', 'N/A')}")
            print()
        
        # Check for positive values
        positive_count = len(rnd_facts[rnd_facts['numeric_value'] > 0])
        print(f"Found {positive_count} facts with positive values")
        return positive_count > 0
    
    return False


def analyze_calculation_weights():
    """Analyze calculation weights for both companies."""
    print("\n=== Analyzing Calculation Weights ===")
    
    # MSFT
    print("\n--- MSFT Calculation Trees ---")
    msft_filing = get_by_accession_number("0000950170-24-087843")
    msft_xbrl = msft_filing.xbrl()
    
    # Get calculation trees
    if hasattr(msft_xbrl, 'parser') and hasattr(msft_xbrl.parser, 'calculation_trees'):
        for role_uri, calc_tree in msft_xbrl.parser.calculation_trees.items():
            print(f"\nRole: {role_uri}")
            print(f"Definition: {calc_tree.definition}")
            
            # Look for R&D expense in calculation nodes
            for element_id, node in calc_tree.all_nodes.items():
                if "ResearchAndDevelopment" in element_id:
                    print(f"  Found R&D element: {element_id}")
                    print(f"  Weight: {node.weight}")
                    print(f"  Parent: {node.parent}")
                    print(f"  Children: {node.children}")
    
    # AAPL  
    print("\n--- AAPL Calculation Trees ---")
    aapl_filing = get_by_accession_number("0000320193-24-000123")
    aapl_xbrl = aapl_filing.xbrl()
    
    if hasattr(aapl_xbrl, 'parser') and hasattr(aapl_xbrl.parser, 'calculation_trees'):
        for role_uri, calc_tree in aapl_xbrl.parser.calculation_trees.items():
            print(f"\nRole: {role_uri}")
            print(f"Definition: {calc_tree.definition}")
            
            # Look for R&D expense in calculation nodes
            for element_id, node in calc_tree.all_nodes.items():
                if "ResearchAndDevelopment" in element_id:
                    print(f"  Found R&D element: {element_id}")
                    print(f"  Weight: {node.weight}")
                    print(f"  Parent: {node.parent}")
                    print(f"  Children: {node.children}")


def main():
    """Run the reproduction test."""
    print("Testing GitHub Issue #334: Inconsistent sign for us-gaap_ResearchAndDevelopmentExpense")
    print("=" * 80)
    
    try:
        # Test both companies
        msft_has_negative = test_msft_research_development_expense()
        aapl_has_positive = test_aapl_research_development_expense()
        
        # Analyze weights
        analyze_calculation_weights()
        
        print("\n=== SUMMARY ===")
        print(f"MSFT has negative R&D values: {msft_has_negative}")
        print(f"AAPL has positive R&D values: {aapl_has_positive}")
        
        if msft_has_negative and aapl_has_positive:
            print("✓ Issue reproduced: Inconsistent sign handling across companies")
        else:
            print("✗ Issue not reproduced or behavior has changed")
            
    except Exception as e:
        print(f"Error during reproduction: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()