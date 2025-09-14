"""
Investigation of duplicate revenue entries in Issue #438

This script reproduces and analyzes the duplicate revenue issue reported:
- "Total Revenue: 10918000000.0" 
- "Revenues: 10918000000.0"

These are the same value appearing twice with different labels in NVDA's income statement.
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

# Set up logging to see what's happening
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def investigate_duplicate_revenue_issue():
    """
    Investigate the duplicate revenue entries issue in NVDA.
    """
    print("🔍 Investigating duplicate revenue entries in NVDA...")
    
    try:
        # Get NVDA company
        nvda = Company("NVDA")
        print(f"✓ Found company: {nvda.name}")
        
        # Get the latest 10-K filing
        filings = nvda.get_filings(form="10-K")
        filing = filings[0]  # Get the most recent
        print(f"✓ Found latest 10-K: {filing.accession_number}")
        
        # Get XBRL data and income statement
        financials = filing.obj()
        if financials is None:
            print("❌ Could not get financials from filing")
            return
            
        income_statement = financials.income_statement
        if income_statement is None:
            print("❌ Could not get income statement")
            return
            
        # Get raw data from income statement  
        raw_data = income_statement.get_raw_data()
        print(f"✓ Got income statement with {len(raw_data)} line items")
        
        # Look for revenue-related entries
        print("\n📊 Revenue-related entries in income statement:")
        revenue_entries = []
        for item in raw_data:
            # Check all names for revenue-related terms
            all_names = item.get('all_names', [])
            has_revenue = any(any(term in name.lower() for term in ['revenue', 'sales']) for name in all_names)
            
            if has_revenue:
                revenue_entries.append(item)
                label = item.get('label', all_names[0] if all_names else 'Unknown')
                values = item.get('values', {})
                print(f"  {all_names[0] if all_names else 'Unknown'}: {label}")
                for period, value in values.items():
                    print(f"    {period}: {value}")
        
        # Check for potential duplicates by value
        print("\n🔍 Checking for duplicate values in revenue entries:")
        value_groups = defaultdict(list)
        
        for entry in revenue_entries:
            values = entry.get('values', {})
            all_names = entry.get('all_names', [])
            label = entry.get('label', all_names[0] if all_names else 'Unknown')
            
            for period, value in values.items():
                if value is not None:
                    value_groups[(period, value)].append({
                        'concept': all_names[0] if all_names else 'Unknown',
                        'label': label,
                        'value': value
                    })
        
        # Report potential duplicates
        duplicates_found = False
        for (period, value), entries in value_groups.items():
            if len(entries) > 1:
                duplicates_found = True
                print(f"\n⚠️  DUPLICATE FOUND in {period}: {value}")
                for entry in entries:
                    print(f"    - {entry['concept']}: {entry['label']}")
        
        if not duplicates_found:
            print("✓ No duplicate values found in current income statement")
        
        # Now let's investigate at the raw facts level
        print("\n🔍 Investigating raw facts for revenue concepts...")
        
        # Get entity facts for deeper analysis
        entity_facts = nvda.get_entity_facts()
        if entity_facts:
            print(f"✓ Found {len(entity_facts.facts)} total facts")
            
            # Filter revenue-related facts
            revenue_facts = []
            for fact in entity_facts.facts:
                if fact.concept and any(term in fact.concept.lower() for term in ['revenue', 'sales']):
                    revenue_facts.append(fact)
            
            print(f"✓ Found {len(revenue_facts)} revenue-related facts")
            
            # Group by fiscal year and value to find duplicates
            print("\n📊 Revenue facts by fiscal year:")
            fy_value_groups = defaultdict(list)
            
            for fact in revenue_facts:
                if fact.fiscal_year and fact.numeric_value is not None:
                    key = (fact.fiscal_year, fact.numeric_value)
                    fy_value_groups[key].append({
                        'concept': fact.concept,
                        'label': fact.label,
                        'value': fact.numeric_value,
                        'fiscal_year': fact.fiscal_year,
                        'fiscal_period': fact.fiscal_period,
                        'statement_type': fact.statement_type
                    })
            
            # Report duplicate analysis at facts level
            facts_duplicates_found = False
            for (fy, value), facts in fy_value_groups.items():
                if len(facts) > 1:
                    facts_duplicates_found = True
                    print(f"\n⚠️  Duplicate value in FY {fy}: {value}")
                    for fact in facts:
                        print(f"    - {fact['concept']}: {fact['label']} (period: {fact['fiscal_period']}, statement: {fact['statement_type']})")
            
            if not facts_duplicates_found:
                print("✓ No duplicate values found at facts level")
            
            # Check specific revenue concepts that might cause issues
            print("\n🔍 Checking specific revenue concept mappings:")
            test_concepts = [
                'us-gaap:Revenues',
                'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                'us-gaap:Revenue',
                'us-gaap:SalesRevenueNet'
            ]
            
            for concept in test_concepts:
                statement_type = EntityFactsParser._determine_statement_type(concept)
                print(f"  {concept} -> {statement_type}")
                
                # Count facts with this concept
                matching_facts = [f for f in revenue_facts if f.concept == concept]
                print(f"    Found {len(matching_facts)} facts with this concept")
                
                # Show recent years data
                for fact in matching_facts:
                    if fact.fiscal_year >= 2020:
                        print(f"      FY {fact.fiscal_year} {fact.fiscal_period}: {fact.numeric_value} ({fact.label})")
        
        else:
            print("❌ Could not get entity facts")
            
    except Exception as e:
        print(f"❌ Error during investigation: {e}")
        import traceback
        traceback.print_exc()


def test_statement_mapping_duplicates():
    """
    Test if the STATEMENT_MAPPING changes create logical duplicates.
    """
    print("\n🧪 Testing STATEMENT_MAPPING for potential duplicate issues...")
    
    # Check the current mapping
    mapping = EntityFactsParser.STATEMENT_MAPPING
    
    # Look for revenue-related concepts
    revenue_concepts = []
    for concept, statement_type in mapping.items():
        if 'revenue' in concept.lower() and statement_type == 'IncomeStatement':
            revenue_concepts.append(concept)
    
    print(f"✓ Found {len(revenue_concepts)} revenue concepts in STATEMENT_MAPPING:")
    for concept in revenue_concepts:
        print(f"  - {concept}")
    
    # The issue is that multiple concepts might map to the same underlying data
    # but with different labels, creating apparent duplicates in the UI
    print("\n💡 Analysis: Multiple revenue concepts mapping to IncomeStatement could")
    print("   create duplicates if they represent the same underlying value but")
    print("   have different labels in the presentation.")


if __name__ == "__main__":
    print("🔍 Issue #438 Duplicate Revenue Investigation")
    print("=" * 50)
    
    investigate_duplicate_revenue_issue()
    test_statement_mapping_duplicates()
    
    print("\n" + "=" * 50)
    print("Investigation complete. Check output above for duplicate analysis.")