#!/usr/bin/env python3
"""
Comprehensive test of all hierarchy fixes.

This verifies that all the hierarchical concept mappings we fixed
(Revenue, SG&A, Net Income, Income Before Tax) now work correctly.
"""

from edgar.xbrl.standardization.core import initialize_default_mappings
from rich import print
from rich.table import Table
from rich.console import Console

def test_all_hierarchy_fixes():
    """Test all hierarchy fixes together."""
    print("[bold green]Comprehensive Hierarchy Fix Verification[/bold green]\n")
    
    store = initialize_default_mappings(read_only=True)
    
    # Define all the hierarchy test cases
    hierarchy_test_cases = [
        # Revenue Hierarchy
        ("us-gaap_Revenue", "Revenue"),
        ("us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax", "Contract Revenue"),
        ("us-gaap_SalesRevenueGoodsNet", "Product Revenue"),
        
        # SG&A Hierarchy  
        ("us-gaap_SellingGeneralAndAdministrativeExpense", "Selling, General and Administrative Expense"),
        ("us-gaap_GeneralAndAdministrativeExpense", "General and Administrative Expense"),
        ("us-gaap_SellingAndMarketingExpense", "Selling Expense"),
        
        # Net Income Hierarchy
        ("us-gaap_NetIncome", "Net Income"),
        ("us-gaap_IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest", "Net Income from Continuing Operations"),
        ("us-gaap_ProfitLoss", "Profit or Loss"),
        
        # Income Before Tax Hierarchy
        ("us-gaap_IncomeLossBeforeIncomeTaxes", "Income Before Tax"),
        ("us-gaap_IncomeLossFromContinuingOperationsBeforeIncomeTaxes", "Income Before Tax from Continuing Operations")
    ]
    
    table = Table(title="All Hierarchy Fixes Verification")
    table.add_column("Category", style="magenta", width=20)
    table.add_column("Concept", style="cyan", width=40)
    table.add_column("Expected Label", style="yellow", width=25)
    table.add_column("Actual Label", style="green", width=25)
    table.add_column("Status", style="red")
    
    categories = {
        "us-gaap_Revenue": "Revenue",
        "us-gaap_RevenueFromContract": "Revenue",
        "us-gaap_SalesRevenueGoodsNet": "Revenue",
        "us-gaap_SellingGeneral": "SG&A",
        "us-gaap_GeneralAnd": "SG&A", 
        "us-gaap_SellingAnd": "SG&A",
        "us-gaap_NetIncome": "Net Income",
        "us-gaap_IncomeLossFromContinuing": "Net Income",
        "us-gaap_ProfitLoss": "Net Income",
        "us-gaap_IncomeLossBeforeIncome": "Income Before Tax"
    }
    
    all_correct = True
    
    for concept, expected_label in hierarchy_test_cases:
        actual_label = store.get_standard_concept(concept)
        
        # Determine category
        category = "Other"
        for key, cat in categories.items():
            if key in concept:
                category = cat
                break
        
        status = "✅ Correct" if actual_label == expected_label else "❌ Incorrect"
        if actual_label != expected_label:
            all_correct = False
        
        table.add_row(
            category,
            concept,
            expected_label,
            actual_label or "Not Found",
            status
        )
    
    console = Console()
    console.print(table)
    
    return all_correct

def show_hierarchy_summary():
    """Show a summary of all the hierarchies we fixed."""
    print("\n[bold blue]Hierarchy Fixes Summary[/bold blue]\n")
    
    hierarchies = {
        "Revenue": {
            "Total": ["Revenue"],
            "Components": ["Contract Revenue", "Product Revenue"]
        },
        "SG&A": {
            "Total": ["Selling, General and Administrative Expense"],
            "Components": ["General and Administrative Expense", "Selling Expense"]
        },
        "Net Income": {
            "Total": ["Net Income"],
            "Components": ["Net Income from Continuing Operations", "Profit or Loss"]
        },
        "Income Before Tax": {
            "Total": ["Income Before Tax"],
            "Components": ["Income Before Tax from Continuing Operations"]
        }
    }
    
    for hierarchy_name, structure in hierarchies.items():
        print(f"[bold]{hierarchy_name} Hierarchy:[/bold]")
        print(f"  Total: {', '.join(structure['Total'])}")
        print(f"  Components: {', '.join(structure['Components'])}")
        print()

def demonstrate_overall_impact():
    """Demonstrate the overall impact of all hierarchy fixes."""
    print("[bold magenta]Overall Impact on Financial Statement Clarity[/bold magenta]\n")
    
    print("Before hierarchy fixes:")
    print("  ❌ Multiple concepts mapped to same labels")
    print("  ❌ 'Revenue', 'Revenue', 'Revenue' (confusing)")
    print("  ❌ 'Net Income', 'Net Income', 'Net Income' (confusing)")
    print("  ❌ 'SG&A Expense', 'SG&A Expense' (confusing)")
    print()
    
    print("After hierarchy fixes:")
    print("  ✅ Distinct labels for each concept level")
    print("  ✅ 'Revenue', 'Contract Revenue', 'Product Revenue' (clear)")
    print("  ✅ 'Net Income', 'Net Income from Continuing Ops', 'Profit or Loss' (clear)")
    print("  ✅ 'SG&A Expense', 'General & Admin Expense', 'Selling Expense' (clear)")
    print()
    
    print("Benefits:")
    print("  📊 Better financial statement readability")
    print("  🔍 Easier cross-company analysis")  
    print("  🤖 Improved automated processing")
    print("  📈 Enhanced investor understanding")
    print("  ⚖️ Better regulatory compliance")

if __name__ == '__main__':
    success = test_all_hierarchy_fixes()
    show_hierarchy_summary() 
    demonstrate_overall_impact()
    
    if success:
        print(f"\n[bold green]🎉 All hierarchy fixes are working correctly![/bold green]")
        print("Financial statement standardization is now significantly improved!")
    else:
        print(f"\n[bold red]⚠️ Some hierarchy fixes need debugging[/bold red]")