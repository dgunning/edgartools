#!/usr/bin/env python3
"""
Test revenue hierarchy mapping issue.

This demonstrates the problem where different revenue concepts 
all map to the same "Revenue" label, causing confusion when
companies report both total and component revenue items.
"""

from edgar.xbrl.standardization.core import initialize_default_mappings
from rich import print
from rich.table import Table
from rich.console import Console

def test_revenue_hierarchy_issue():
    """Test how revenue concepts currently map."""
    print("[bold red]Revenue Hierarchy Mapping Issue[/bold red]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    # Get all concepts that map to "Revenue"
    revenue_concepts = store.get_company_concepts("Revenue")
    
    print(f"[bold]Concepts currently mapping to 'Revenue' ({len(revenue_concepts)}):[/bold]")
    
    table = Table(title="Revenue Concept Mappings")
    table.add_column("Concept", style="cyan")
    table.add_column("Mapped Label", style="green")
    table.add_column("Likely Hierarchy Level", style="yellow")
    
    # Analyze each concept to understand the hierarchy issue
    concept_analysis = {
        "us-gaap_Revenue": "Total Revenue (Top Level)",
        "us-gaap_Revenues": "Total Revenue (Top Level)", 
        "us-gaap_SalesRevenueNet": "Net Sales Revenue (Total)",
        "us-gaap_OperatingRevenue": "Operating Revenue (Total)",
        "us-gaap_SalesRevenueGoodsNet": "Product Sales Revenue (Component)",
        "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax": "Contract Revenue (Component/Detail)"
    }
    
    for concept in sorted(revenue_concepts):
        standard_label = store.get_standard_concept(concept)
        hierarchy_level = concept_analysis.get(concept, "Unknown")
        
        # Color code by hierarchy level
        if "Total" in hierarchy_level:
            style = "bold green"
        elif "Component" in hierarchy_level:
            style = "bold yellow" 
        else:
            style = "white"
            
        table.add_row(concept, standard_label, hierarchy_level)
    
    console = Console()
    console.print(table)

def demonstrate_tesla_example():
    """Show how this affects Tesla's financial statements."""
    print("\n[bold blue]Tesla Example - Revenue Confusion[/bold blue]\n")
    
    print("Tesla might report:")
    print("  • Total automotive and energy revenue: us-gaap_Revenue")
    print("  • Contract-based revenue detail: us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax")
    print("  • Both get labeled as 'Revenue' → Confusion!")
    print()

def propose_solution():
    """Propose a solution for the revenue hierarchy."""
    print("[bold green]Proposed Solution[/bold green]\n")
    
    print("Create distinct labels for different revenue types:")
    print()
    
    solution = '''
"Revenue": [
  "us-gaap_Revenue",
  "us-gaap_Revenues", 
  "us-gaap_SalesRevenueNet",
  "us-gaap_OperatingRevenue"
],

"Contract Revenue": [
  "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
  "us-gaap_RevenueFromContractWithCustomerIncludingAssessedTax"
],

"Product Revenue": [
  "us-gaap_SalesRevenueGoodsNet",
  "us-gaap_ProductSales"
],

"Service Revenue": [
  "us-gaap_RevenueFromServicesRendered",
  "us-gaap_ServiceRevenue"
]'''
    
    print(solution)
    print()
    print("This creates a proper hierarchy:")
    print("  • Revenue (top level)")
    print("  • Contract Revenue (component)")
    print("  • Product Revenue (component)")  
    print("  • Service Revenue (component)")

def check_other_companies():
    """Check if this affects other companies beyond Tesla."""
    print("\n[bold yellow]Impact on Other Companies[/bold yellow]\n")
    
    print("This issue likely affects ANY company that reports:")
    print("  ✓ Total revenue AND detailed revenue breakdowns")
    print("  ✓ Contract-based revenue (common in SaaS, manufacturing)")
    print("  ✓ Multiple revenue streams (product + service)")
    print()
    print("Affected industries:")
    print("  • Technology (software + hardware)")
    print("  • Manufacturing (product sales + service contracts)")
    print("  • Healthcare (products + services)")
    print("  • Energy (different revenue types)")
    print()
    print("Companies likely affected: MSFT, AAPL, GOOG, AMZN, TSLA, and many others")

if __name__ == '__main__':
    test_revenue_hierarchy_issue()
    demonstrate_tesla_example()
    propose_solution()
    check_other_companies()