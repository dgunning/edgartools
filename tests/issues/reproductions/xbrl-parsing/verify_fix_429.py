#!/usr/bin/env python3
"""
Verification script for GitHub issue #429 fix
"""

import edgar
from rich.console import Console
from rich.table import Table

console = Console()

def verify_fix():
    """Verify the fix is working correctly"""
    console.print(f"\n[bold blue]Verifying GitHub Issue #429 Fix[/bold blue]")
    console.print("Testing AAPL 10-K statements...")
    
    # Get AAPL data exactly as described in the issue
    aapl = edgar.Company("AAPL")
    filing = aapl.get_filings(form="10-K").latest()
    current = filing.xbrl().current_period
    
    console.print(f"Filing: {filing.accession_no} ({filing.filing_date})")
    console.print(f"Current Period: {current.period_label}")
    
    # Test the statements
    balance_sheet = current.balance_sheet()
    income_statement = current.income_statement()
    cash_flow = current.cashflow_statement()
    
    # Create results table
    table = Table(title="Statement Fix Verification")
    table.add_column("Statement", style="cyan")
    table.add_column("Rows", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Sample Data", style="yellow")
    
    # Balance Sheet
    balance_status = "✅ Working" if len(balance_sheet) > 20 else "❌ Issue"
    balance_sample = f"Cash: ${balance_sheet[balance_sheet['label'].str.contains('Cash', case=False, na=False)]['value'].iloc[0]/1e9:.1f}B" if len(balance_sheet) > 0 else "No data"
    table.add_row("Balance Sheet", str(len(balance_sheet)), balance_status, balance_sample)
    
    # Income Statement  
    income_status = "✅ FIXED!" if len(income_statement) > 30 else "❌ Still broken"
    income_sample = ""
    if len(income_statement) > 0:
        revenue_rows = income_statement[income_statement['label'].str.contains('Revenue|Contract', case=False, na=False)]
        if len(revenue_rows) > 0:
            income_sample = f"Revenue: ${revenue_rows['value'].iloc[0]/1e9:.1f}B"
        else:
            income_sample = f"{len(income_statement)} line items found"
    else:
        income_sample = "No data"
    table.add_row("Income Statement", str(len(income_statement)), income_status, income_sample)
    
    # Cash Flow
    cashflow_status = "✅ FIXED!" if len(cash_flow) > 20 else "❌ Still broken" 
    cashflow_sample = ""
    if len(cash_flow) > 0:
        net_income_rows = cash_flow[cash_flow['label'].str.contains('Net Income', case=False, na=False)]
        if len(net_income_rows) > 0:
            cashflow_sample = f"Net Income: ${net_income_rows['value'].iloc[0]/1e9:.1f}B"
        else:
            cashflow_sample = f"{len(cash_flow)} line items found"
    else:
        cashflow_sample = "No data"
    table.add_row("Cash Flow", str(len(cash_flow)), cashflow_status, cashflow_sample)
    
    console.print(table)
    
    # Show period selection details
    console.print(f"\n[bold green]Period Selection Details:[/bold green]")
    console.print(f"  Balance Sheet uses: {current._get_appropriate_period_for_statement('BalanceSheet')}")
    console.print(f"  Income Statement uses: {current._get_appropriate_period_for_statement('IncomeStatement')}")  
    console.print(f"  Cash Flow uses: {current._get_appropriate_period_for_statement('CashFlowStatement')}")
    
    # Summary
    if len(income_statement) > 30 and len(cash_flow) > 20:
        console.print(f"\n[bold green]🎉 SUCCESS! Issue #429 has been FIXED![/bold green]")
        console.print("✅ Income statement now returns full data")
        console.print("✅ Cash flow statement now returns full data") 
        console.print("✅ Balance sheet continues to work correctly")
        return True
    else:
        console.print(f"\n[bold red]❌ Issue #429 still needs work[/bold red]")
        return False

if __name__ == "__main__":
    verify_fix()