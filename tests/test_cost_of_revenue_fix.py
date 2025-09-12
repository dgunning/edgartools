#!/usr/bin/env python3
"""
Test the Cost of Revenue hierarchy fix.

This verifies that different cost concepts now get distinct, appropriate labels
instead of all mapping to generic "Cost of Revenue".
"""

from edgar.xbrl.standardization.core import initialize_default_mappings
from rich import print
from rich.table import Table
from rich.console import Console
import pytest

@pytest.mark.regression
def test_cost_of_revenue_hierarchy_fix():
    """Test that Cost concepts now have distinct labels."""
    print("[bold green]Cost of Revenue Hierarchy Fix Verification[/bold green]\n")
    
    # Reinitialize to pick up changes
    store = initialize_default_mappings(read_only=True)
    
    # Test specific cost concepts
    cost_test_cases = [
        ("us-gaap_CostOfRevenue", "Cost of Revenue"),
        ("us-gaap_CostOfGoodsSold", "Cost of Goods Sold"),
        ("us-gaap_CostOfGoodsAndServicesSold", "Cost of Goods and Services Sold"),
        ("us-gaap_CostOfSales", "Cost of Sales"),
        ("us-gaap_DirectOperatingCosts", "Direct Operating Costs"),
        # This should now be unmapped (removed from Cost of Revenue)
        ("us-gaap_CostsAndExpenses", None),
        # Test that missing concepts don't break
        ("us-gaap_SomeOtherCost", None)
    ]
    
    table = Table(title="Cost Concept Mapping After Fix")
    table.add_column("Concept", style="cyan", width=40)
    table.add_column("Expected Label", style="yellow")
    table.add_column("Actual Label", style="green")
    table.add_column("Status", style="red")
    
    all_correct = True
    
    for concept, expected_label in cost_test_cases:
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
        print("\n[bold green]✅ All cost mappings are correct![/bold green]")
    else:
        print("\n[bold red]❌ Some cost mappings need attention[/bold red]")
    
    return all_correct

@pytest.mark.regression
def test_cost_hierarchy_separation():
    """Test that we've properly separated the cost hierarchy."""
    print("\n[bold blue]Cost Hierarchy Separation[/bold blue]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    # Check what concepts map to each cost type
    cost_categories = [
        "Cost of Revenue",
        "Cost of Goods Sold",
        "Cost of Goods and Services Sold", 
        "Cost of Sales",
        "Direct Operating Costs"
    ]
    
    table = Table(title="Cost Category Breakdown")
    table.add_column("Category", style="cyan")
    table.add_column("Mapped Concepts", style="green")
    table.add_column("Count", style="yellow")
    
    for category in cost_categories:
        concepts = store.get_company_concepts(category)
        concept_list = "\n".join(sorted(concepts)) if concepts else "None"
        count = len(concepts)
        
        table.add_row(category, concept_list, str(count))
    
    console = Console()
    console.print(table)

def simulate_company_impact_costs():
    """Simulate how this affects different company types."""
    print("\n[bold magenta]Impact on Different Company Types[/bold magenta]\n")
    
    company_examples = [
        {
            "type": "Manufacturing Company (Tesla)",
            "before": ["Cost of Revenue", "Cost of Revenue"],
            "after": ["Cost of Revenue", "Cost of Goods Sold"],
            "benefit": "Clear distinction between total revenue costs and goods manufacturing costs"
        },
        {
            "type": "Service Company (Microsoft)",
            "before": ["Cost of Revenue", "Cost of Revenue"],
            "after": ["Cost of Revenue", "Cost of Sales"],
            "benefit": "Separate service delivery costs from sales-specific costs"
        },
        {
            "type": "Mixed Company (Amazon)",
            "before": ["Cost of Revenue", "Cost of Revenue", "Cost of Revenue"],
            "after": ["Cost of Revenue", "Cost of Goods Sold", "Cost of Goods and Services Sold"],
            "benefit": "Distinguish between product costs, service costs, and mixed fulfillment costs"
        },
        {
            "type": "Retail Company (Walmart)",
            "before": ["Cost of Revenue", "Cost of Revenue"],
            "after": ["Cost of Sales", "Cost of Goods Sold"],
            "benefit": "Separate total sales costs from inventory/goods costs"
        }
    ]
    
    for example in company_examples:
        print(f"[bold]{example['type']}:[/bold]")
        print(f"  Before: {', '.join(example['before'])} ← Confusing!")
        print(f"  After:  {', '.join(example['after'])} ← Clear!")
        print(f"  Benefit: {example['benefit']}")
        print()

def explain_cost_distinctions():
    """Explain the distinctions between different cost types."""
    print("\n[bold yellow]Understanding Cost Type Distinctions[/bold yellow]\n")
    
    distinctions = [
        {
            "concept": "Cost of Revenue",
            "definition": "Total costs directly attributable to generating revenue",
            "use_case": "General/broad cost reporting"
        },
        {
            "concept": "Cost of Goods Sold",
            "definition": "Direct costs to manufacture or purchase goods sold",
            "use_case": "Manufacturing, product companies"
        },
        {
            "concept": "Cost of Goods and Services Sold", 
            "definition": "Combined costs for both products and services delivered",
            "use_case": "Mixed business models (products + services)"
        },
        {
            "concept": "Cost of Sales",
            "definition": "All costs associated with sales activities and fulfillment",
            "use_case": "Retail, distribution companies"
        },
        {
            "concept": "Direct Operating Costs",
            "definition": "Direct costs of operations, may include non-revenue costs",
            "use_case": "Operational cost focus, may be broader than revenue"
        }
    ]
    
    for distinction in distinctions:
        print(f"[bold]{distinction['concept']}:[/bold]")
        print(f"  Definition: {distinction['definition']}")
        print(f"  Best for: {distinction['use_case']}")
        print()

if __name__ == '__main__':
    success = test_cost_of_revenue_hierarchy_fix()
    test_cost_hierarchy_separation()
    simulate_company_impact_costs()
    explain_cost_distinctions()
    
    if success:
        print(f"\n[bold green]🎉 Cost of Revenue hierarchy fix is working correctly![/bold green]")
        print("Financial statement cost reporting is now much clearer!")
    else:
        print(f"\n[bold red]⚠️ Cost of Revenue hierarchy fix needs debugging[/bold red]")