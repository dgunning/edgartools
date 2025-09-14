"""
Test to reproduce the specific NVDA FY 2020 duplicate revenue issue.

User reported seeing:
- "Total Revenue: 10918000000.0" 
- "Revenues: 10918000000.0"

These are the same value appearing twice with different labels.
"""

import sys
import os

# Add the project root to the path to ensure we import from source
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, project_root)

from edgar import Company
from edgar.entity.parser import EntityFactsParser
from collections import defaultdict
import logging

# Reduce log noise
logging.basicConfig(level=logging.WARNING)


def test_nvda_2020_duplicate_issue():
    """
    Test for the specific NVDA FY 2020 duplicate revenue issue.
    """
    print("🔍 Testing NVDA FY 2020 duplicate revenue issue...")
    
    try:
        # Get NVDA company
        nvda = Company("NVDA")
        print(f"✓ Found company: {nvda.name}")
        
        # Get a filing from around 2020/2021 that might show the issue
        filings_10k = nvda.get_filings(form="10-K", before="2022-01-01")
        if len(filings_10k) == 0:
            print("❌ No 10-K filings found before 2022")
            return
            
        # Get the 2021 10-K which covers FY 2020
        filing = filings_10k[0]  # Most recent before 2022
        print(f"✓ Found filing: {filing.accession_number} filed {filing.filing_date}")
        
        # Get XBRL data
        financials = filing.obj()
        if financials is None:
            print("❌ Could not get financials from filing")
            return
            
        income_statement = financials.income_statement
        if income_statement is None:
            print("❌ Could not get income statement")
            return
        
        # Get raw data to look for duplicates
        raw_data = income_statement.get_raw_data()
        print(f"✓ Got income statement with {len(raw_data)} line items")
        
        # Look specifically for revenue concepts that could create duplicates
        revenue_items = []
        target_value = 10918000000.0  # The value mentioned in the bug report
        
        for item in raw_data:
            all_names = item.get('all_names', [])
            values = item.get('values', {})
            label = item.get('label', all_names[0] if all_names else 'Unknown')
            
            # Look for revenue-related items
            has_revenue = any(any(term in name.lower() for term in ['revenue']) for name in all_names)
            
            if has_revenue:
                revenue_items.append({
                    'concept': all_names[0] if all_names else 'Unknown',
                    'all_names': all_names,
                    'label': label,
                    'values': values
                })
                
                # Check if this matches the target value
                for period, value in values.items():
                    if value == target_value:
                        print(f"🎯 FOUND TARGET VALUE {target_value} in:")
                        print(f"   Concept: {all_names[0] if all_names else 'Unknown'}")
                        print(f"   Label: {label}")
                        print(f"   Period: {period}")
        
        print(f"\n📊 Found {len(revenue_items)} revenue-related items:")
        
        # Group by value to find potential duplicates
        value_groups = defaultdict(list)
        for item in revenue_items:
            for period, value in item['values'].items():
                if value is not None and value != 0:
                    value_groups[(period, value)].append({
                        'concept': item['concept'],
                        'label': item['label'],
                        'value': value
                    })
        
        # Check for duplicates
        duplicates_found = False
        for (period, value), items in value_groups.items():
            if len(items) > 1:
                duplicates_found = True
                print(f"\n⚠️  DUPLICATE VALUE in {period}: ${value:,.0f}")
                for item in items:
                    print(f"    - {item['concept']}: {item['label']}")
                    
                # Look for the specific issue: different concepts with same value
                concepts = [item['concept'] for item in items]
                if len(set(concepts)) > 1:
                    print(f"    🚨 Different concepts with same value!")
                    
                    # Look for the specific scenario from the bug report
                    labels = [item['label'] for item in items]
                    if any('Total Revenue' in label for label in labels) and any('Revenues' in label for label in labels):
                        print(f"    🎯 FOUND THE EXACT BUG: 'Total Revenue' and 'Revenues' with same value!")
        
        if not duplicates_found:
            print("✓ No duplicate values found in this filing")
            
        # Also test the parser logic directly with the concepts we found
        print(f"\n🧪 Testing parser logic for revenue concepts found:")
        revenue_concepts = set()
        for item in revenue_items:
            for name in item['all_names']:
                revenue_concepts.add(name)
        
        for concept in revenue_concepts:
            statement_type = EntityFactsParser._determine_statement_type(concept)
            print(f"  {concept} -> {statement_type}")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()


def investigate_multiple_revenue_concepts():
    """
    Investigate how multiple revenue concepts might create duplicates.
    """
    print("\n🔍 Investigating potential duplicate scenarios...")
    
    # These are the revenue concepts in STATEMENT_MAPPING
    revenue_concepts = [
        'us-gaap:Revenue',
        'us-gaap:Revenues', 
        'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
        'us-gaap:SalesRevenueNet'
    ]
    
    print("Revenue concepts that map to IncomeStatement:")
    for concept in revenue_concepts:
        statement_type = EntityFactsParser._determine_statement_type(concept)
        print(f"  {concept} -> {statement_type}")
    
    print("\n💡 POTENTIAL ISSUE:")
    print("If a company has facts for both 'us-gaap:Revenues' and")
    print("'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'")
    print("with the same value, they could appear as duplicate lines:")
    print("  - 'Revenues: $10.9B'")
    print("  - 'Revenue From Contract With Customer...: $10.9B'")
    print("\nThe STATEMENT_MAPPING fix ensures both get classified correctly,")
    print("but we need deduplication logic to prevent showing both when")
    print("they represent the same underlying revenue.")


if __name__ == "__main__":
    print("🔍 NVDA FY 2020 Duplicate Revenue Issue Test")
    print("=" * 50)
    
    test_nvda_2020_duplicate_issue()
    investigate_multiple_revenue_concepts()
    
    print("\n" + "=" * 50)
    print("Test complete. Check output above for duplicate analysis.")