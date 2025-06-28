#!/usr/bin/env python3
"""
Test the revenue hierarchy fix.

This verifies that revenue concepts now get distinct, appropriate labels
instead of all mapping to generic "Revenue".
"""

from edgar.xbrl.standardization.core import initialize_default_mappings
from rich import print
from rich.table import Table
from rich.console import Console

def test_revenue_hierarchy_fix():
    """Test that revenue concepts now have distinct labels."""
    print("[bold green]Revenue Hierarchy Fix Verification[/bold green]\n")
    
    # Reinitialize to pick up changes
    store = initialize_default_mappings(read_only=True)
    
    # Test specific revenue concepts
    revenue_test_cases = [
        ("us-gaap_Revenue", "Revenue"),
        ("us-gaap_Revenues", "Revenue"), 
        ("us-gaap_SalesRevenueNet", "Revenue"),
        ("us-gaap_OperatingRevenue", "Revenue"),
        ("us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", "Contract Revenue"),
        ("us-gaap_SalesRevenueGoodsNet", "Product Revenue"),
        # Test that missing concepts don't break
        ("us-gaap_SomeOtherRevenue", None)
    ]
    
    table = Table(title="Revenue Concept Mapping After Fix")
    table.add_column("Concept", style="cyan", width=40)
    table.add_column("Expected Label", style="yellow")
    table.add_column("Actual Label", style="green")
    table.add_column("Status", style="red")
    
    all_correct = True
    
    for concept, expected_label in revenue_test_cases:
        actual_label = store.get_standard_concept(concept)
        
        if expected_label is None:
            status = "✅ Correct (Not Mapped)" if actual_label is None else "❌ Unexpected Mapping"
            if actual_label is not None:
                all_correct = False
        else:
            status = "✅ Correct" if actual_label == expected_label else "❌ Incorrect"
            if actual_label != expected_label:
                all_correct = False
        
        table.add_row(
            concept,
            expected_label or "Not Mapped",
            actual_label or "Not Found",
            status
        )
    
    console = Console()
    console.print(table)
    
    if all_correct:
        print("\n[bold green]✅ All revenue mappings are correct![/bold green]")
    else:
        print("\n[bold red]❌ Some revenue mappings need attention[/bold red]")
    
    return all_correct

def test_hierarchy_separation():
    """Test that we've properly separated the hierarchy."""
    print("\n[bold blue]Revenue Hierarchy Separation[/bold blue]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    # Check what concepts map to each revenue type
    revenue_categories = [
        "Revenue",
        "Contract Revenue", 
        "Product Revenue"
    ]
    
    table = Table(title="Revenue Category Breakdown")
    table.add_column("Category", style="cyan")
    table.add_column("Mapped Concepts", style="green")
    table.add_column("Count", style="yellow")
    
    for category in revenue_categories:
        concepts = store.get_company_concepts(category)
        concept_list = "\n".join(sorted(concepts)) if concepts else "None"
        count = len(concepts)
        
        table.add_row(category, concept_list, str(count))
    
    console = Console()
    console.print(table)

def simulate_company_impact():
    """Simulate how this affects company financial statements."""
    print("\n[bold magenta]Impact on Company Financial Statements[/bold magenta]\n")
    
    print("Before the fix:")
    print("  Tesla Revenue Line 1: 'Revenue' (us-gaap_Revenue)")
    print("  Tesla Revenue Line 2: 'Revenue' (us-gaap_RevenueFromContract...) ← CONFUSING!")
    print()
    
    print("After the fix:")
    print("  Tesla Revenue Line 1: 'Revenue' (us-gaap_Revenue)")
    print("  Tesla Revenue Line 2: 'Contract Revenue' (us-gaap_RevenueFromContract...) ← CLEAR!")
    print()
    
    print("This provides better clarity for:")
    print("  ✓ Investors reading financial statements")
    print("  ✓ Analysts comparing across companies")
    print("  ✓ Automated financial analysis tools")
    print("  ✓ Regulatory compliance and standardization")

if __name__ == '__main__':
    success = test_revenue_hierarchy_fix()
    test_hierarchy_separation()
    simulate_company_impact()
    
    if success:
        print(f"\n[bold green]🎉 Revenue hierarchy fix is working correctly![/bold green]")
    else:
        print(f"\n[bold red]⚠️ Revenue hierarchy fix needs debugging[/bold red]")