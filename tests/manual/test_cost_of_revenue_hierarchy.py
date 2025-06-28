#!/usr/bin/env python3
"""
Analyze Cost of Revenue hierarchy for potential mapping issues.

This reviews whether different cost concepts should have distinct labels
instead of all mapping to generic "Cost of Revenue".
"""

from edgar.xbrl.standardization.core import initialize_default_mappings
from rich import print
from rich.table import Table
from rich.console import Console

def analyze_cost_of_revenue_hierarchy():
    """Analyze the Cost of Revenue mapping for hierarchy issues."""
    print("[bold yellow]Cost of Revenue Hierarchy Analysis[/bold yellow]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    # Get all concepts that map to "Cost of Revenue"
    cost_concepts = store.get_company_concepts("Cost of Revenue")
    
    print(f"[bold]Concepts currently mapping to 'Cost of Revenue' ({len(cost_concepts)}):[/bold]")
    
    table = Table(title="Cost of Revenue Concept Mappings")
    table.add_column("Concept", style="cyan", width=40)
    table.add_column("Mapped Label", style="green")
    table.add_column("Hierarchy Analysis", style="yellow", width=35)
    table.add_column("Potential Issue", style="red")
    
    # Analyze each concept to understand potential hierarchy issues
    concept_analysis = {
        "us-gaap_CostOfRevenue": {
            "hierarchy": "Total Cost of Revenue (Top Level)",
            "issue": "None - appropriate for top level"
        },
        "us-gaap_CostsAndExpenses": {
            "hierarchy": "All Costs and Expenses (Very Broad)",
            "issue": "⚠️ Too broad - includes non-revenue costs"
        },
        "us-gaap_CostOfGoodsAndServicesSold": {
            "hierarchy": "Cost of Goods and Services (Component)",
            "issue": "⚠️ Should be distinct from pure goods/services"
        },
        "us-gaap_CostOfGoodsSold": {
            "hierarchy": "Cost of Goods Only (Component)",
            "issue": "⚠️ Should distinguish from services"
        },
        "us-gaap_CostOfSales": {
            "hierarchy": "Cost of Sales (Component)",
            "issue": "⚠️ May be different from cost of revenue"
        },
        "us-gaap_DirectOperatingCosts": {
            "hierarchy": "Direct Operating Costs (Component)",
            "issue": "⚠️ Operating costs ≠ revenue costs"
        }
    }
    
    for concept in sorted(cost_concepts):
        standard_label = store.get_standard_concept(concept)
        analysis = concept_analysis.get(concept, {
            "hierarchy": "Unknown", 
            "issue": "❓ Needs analysis"
        })
        
        table.add_row(
            concept, 
            standard_label, 
            analysis["hierarchy"],
            analysis["issue"]
        )
    
    console = Console()
    console.print(table)

def identify_hierarchy_issues():
    """Identify specific hierarchy issues with Cost of Revenue."""
    print("\n[bold red]Identified Hierarchy Issues[/bold red]\n")
    
    issues = [
        {
            "concept": "us-gaap_CostsAndExpenses",
            "issue": "Too Broad Scope",
            "explanation": "This includes ALL costs and expenses, not just revenue-related costs. Could include R&D, SG&A, etc."
        },
        {
            "concept": "us-gaap_CostOfGoodsSold vs us-gaap_CostOfGoodsAndServicesSold",
            "issue": "Goods vs Goods+Services Distinction",
            "explanation": "Manufacturing companies report goods costs, service companies report service costs, mixed companies report both."
        },
        {
            "concept": "us-gaap_CostOfSales vs us-gaap_CostOfRevenue",
            "issue": "Sales vs Revenue Distinction", 
            "explanation": "Cost of Sales may be narrower than Cost of Revenue in some business models."
        },
        {
            "concept": "us-gaap_DirectOperatingCosts",
            "issue": "Operating vs Revenue Costs",
            "explanation": "Direct operating costs may include costs not directly attributable to revenue generation."
        }
    ]
    
    for i, issue in enumerate(issues, 1):
        print(f"[bold]{i}. {issue['issue']}[/bold]")
        print(f"   Concept: {issue['concept']}")
        print(f"   Problem: {issue['explanation']}")
        print()

def propose_cost_hierarchy_solution():
    """Propose a solution for Cost of Revenue hierarchy."""
    print("[bold green]Proposed Cost of Revenue Hierarchy Solution[/bold green]\n")
    
    solution = '''
"Cost of Revenue": [
  "us-gaap_CostOfRevenue"
],

"Cost of Goods Sold": [
  "us-gaap_CostOfGoodsSold"
],

"Cost of Goods and Services Sold": [
  "us-gaap_CostOfGoodsAndServicesSold"
],

"Cost of Sales": [
  "us-gaap_CostOfSales"
],

"Direct Operating Costs": [
  "us-gaap_DirectOperatingCosts"
],

# Remove this - too broad
# "us-gaap_CostsAndExpenses" should not map to Cost of Revenue'''
    
    print(solution)
    print()
    print("This creates proper hierarchy:")
    print("  • Cost of Revenue (total)")
    print("  • Cost of Goods Sold (product companies)")
    print("  • Cost of Goods and Services Sold (mixed companies)")
    print("  • Cost of Sales (may be broader)")
    print("  • Direct Operating Costs (operational focus)")
    print("  • Remove overly broad 'CostsAndExpenses'")

def check_company_impact():
    """Check which types of companies this affects."""
    print("\n[bold blue]Company Impact Analysis[/bold blue]\n")
    
    print("Companies likely affected by Cost of Revenue confusion:")
    print()
    
    company_types = [
        {
            "type": "Manufacturing Companies",
            "concepts": ["Cost of Goods Sold", "Direct Operating Costs"],
            "examples": "Tesla, Apple, General Motors",
            "issue": "May report both product costs and operational costs with same label"
        },
        {
            "type": "Service Companies", 
            "concepts": ["Cost of Revenue", "Cost of Sales"],
            "examples": "Microsoft, Google, Salesforce",
            "issue": "Service delivery costs vs sales costs may be conflated"
        },
        {
            "type": "Mixed Companies",
            "concepts": ["Cost of Goods and Services Sold", "Cost of Revenue"],
            "examples": "Amazon, IBM, Oracle",
            "issue": "Product and service costs may all show as 'Cost of Revenue'"
        },
        {
            "type": "Retail Companies",
            "concepts": ["Cost of Sales", "Cost of Goods Sold"],
            "examples": "Walmart, Target, Home Depot", 
            "issue": "Inventory costs vs total sales costs may be confused"
        }
    ]
    
    table = Table(title="Company Impact by Business Model")
    table.add_column("Company Type", style="cyan")
    table.add_column("Conflicted Concepts", style="yellow")
    table.add_column("Examples", style="green")
    table.add_column("Potential Confusion", style="red")
    
    for company_type in company_types:
        table.add_row(
            company_type["type"],
            ", ".join(company_type["concepts"]),
            company_type["examples"],
            company_type["issue"]
        )
    
    console = Console()
    console.print(table)

def severity_assessment():
    """Assess the severity of Cost of Revenue hierarchy issues."""
    print("\n[bold magenta]Severity Assessment[/bold magenta]\n")
    
    print("Severity: [bold yellow]MEDIUM-HIGH[/bold yellow]")
    print()
    print("Reasons:")
    print("  🔴 [bold]High Impact[/bold]: Cost of Revenue is a key financial metric")
    print("  🔴 [bold]Broad Scope[/bold]: Affects many company types and industries")
    print("  🟡 [bold]Moderate Confusion[/bold]: Different business models use different concepts")
    print("  🟡 [bold]Analysis Impact[/bold]: Analysts need to distinguish cost types")
    print()
    print("Priority: [bold]SHOULD FIX[/bold] - This affects financial analysis quality")

if __name__ == '__main__':
    analyze_cost_of_revenue_hierarchy()
    identify_hierarchy_issues()
    propose_cost_hierarchy_solution()
    check_company_impact()
    severity_assessment()