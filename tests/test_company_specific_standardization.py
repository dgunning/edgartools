#!/usr/bin/env python3
"""
Test company-specific standardization system.

This demonstrates how the priority-based mapping resolution works:
1. Core mappings (priority 1) - from concept_mappings.json
2. Company mappings (priority 2) - from company_mappings/[company]_mappings.json  
3. Entity detection boost (priority 4) - when concept prefix matches company
"""

from edgar.xbrl.standardization.core import initialize_default_mappings
from rich import print
from rich.table import Table
from rich.console import Console
import pytest

@pytest.mark.fast
def test_priority_resolution():
    """Test how priority-based resolution works."""
    print("[bold blue]Company-Specific Standardization Priority System[/bold blue]\n")
    
    # Initialize the mapping store
    store = initialize_default_mappings(read_only=True)
    
    print("[bold]System Overview:[/bold]")
    print("1. Core mappings (priority 1) - Universal mappings in concept_mappings.json")
    print("2. Company mappings (priority 2) - Company-specific mappings")
    print("3. Entity detection boost (priority 4) - When concept prefix matches company")
    print()
    
    # Show loaded company mappings
    print(f"[bold]Loaded Company Mappings:[/bold]")
    for company_id, mappings in store.company_mappings.items():
        entity_info = mappings.get('entity_info', {})
        concept_count = len(mappings.get('concept_mappings', {}))
        print(f"  • {company_id}: {entity_info.get('name', 'Unknown')} ({concept_count} mappings)")
    print()
    
    # Test different concept formats
    test_concepts = [
        # Standard US-GAAP concepts
        "us-gaap:Revenue",
        "us-gaap_Revenue", 
        "us-gaap:SellingAndMarketingExpense",
        
        # Tesla-specific concepts (if they exist)
        "tsla:AutomotiveRevenue",
        "tsla:EnergyRevenue",
        
        # Microsoft-specific concepts
        "msft:ProductRevenue",
        "msft:ServiceRevenue",
        "msft:SalesAndMarketingExpense"
    ]
    
    table = Table(title="Concept Mapping Resolution")
    table.add_column("Concept", style="cyan")
    table.add_column("Detected Entity", style="yellow")
    table.add_column("Standard Label", style="green")
    table.add_column("Priority Used", style="red")
    
    for concept in test_concepts:
        # Detect entity from concept prefix
        detected_entity = store._detect_entity_from_concept(concept)
        
        # Get standardized concept
        standard_label = store.get_standard_concept(concept)
        
        # Determine priority used (simplified logic for display)
        priority_desc = "None"
        if standard_label:
            if detected_entity and detected_entity in store.company_mappings:
                # Check if this mapping came from company-specific file
                company_mappings = store.company_mappings[detected_entity].get('concept_mappings', {})
                found_in_company = any(concept in mapping_list for mapping_list in company_mappings.values())
                if found_in_company:
                    priority_desc = "4 (Company + Entity Match)"
                else:
                    priority_desc = "1 (Core)"
            else:
                priority_desc = "1 (Core)"
        
        table.add_row(
            concept,
            detected_entity or "None",
            standard_label or "Not Found", 
            priority_desc
        )
    
    console = Console()
    console.print(table)

def show_mapping_structure():
    """Show the structure of company mappings."""
    print("\n[bold blue]Company Mapping File Structure[/bold blue]\n")
    
    print("[bold]File Location:[/bold]")
    print("edgar/xbrl/standardization/company_mappings/[company_id]_mappings.json")
    print()
    
    print("[bold]Structure:[/bold]")
    structure = '''
{
  "entity_info": {
    "name": "Company Name",
    "cik": "Company CIK", 
    "ticker": "Stock Symbol",
    "description": "Purpose of mappings"
  },
  
  "concept_mappings": {
    "Standard Label": [
      "company:SpecificConcept1",
      "company:SpecificConcept2"
    ]
  },
  
  "hierarchy_rules": {
    "rule_name": {
      "parent": "Parent Concept",
      "children": ["Child1", "Child2"],
      "calculation_rule": "sum"
    }
  }
}'''
    print(structure)

@pytest.mark.fast
def test_entity_detection():
    """Test how entity detection works."""
    print("\n[bold blue]Entity Detection from Concept Names[/bold blue]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    test_cases = [
        "us-gaap:Revenue",           # No entity detected
        "tsla:AutomotiveRevenue",    # Should detect 'tsla'
        "msft:ProductRevenue",       # Should detect 'msft' 
        "aapl:ServiceRevenue",       # Should detect 'aapl'
        "InvalidConcept"             # No entity detected
    ]
    
    table = Table(title="Entity Detection Test")
    table.add_column("Concept", style="cyan")
    table.add_column("Detected Entity", style="green") 
    table.add_column("Has Company Mappings", style="yellow")
    
    for concept in test_cases:
        detected = store._detect_entity_from_concept(concept)
        has_mappings = detected in store.company_mappings if detected else False
        
        table.add_row(
            concept,
            detected or "None",
            "✅ Yes" if has_mappings else "❌ No"
        )
    
    console = Console()
    console.print(table)

if __name__ == '__main__':
    test_priority_resolution()
    show_mapping_structure()
    test_entity_detection()