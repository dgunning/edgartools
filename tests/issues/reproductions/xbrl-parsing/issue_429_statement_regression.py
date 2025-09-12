#!/usr/bin/env python3
"""
Reproduction script for GitHub issue #429
Income statement and cashflow statement returning empty/incomplete data in v4.11.0

Issue: User upgraded to version 4.11.0 and found:
- balance_sheet() works correctly (30 rows)
- income_statement() returns empty DataFrame 
- cashflow_statement() only returns 2 rows instead of full statement

This appears to be a regression from the recent release.
"""

import edgar
import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()

def test_aapl_statements():
    """Test AAPL statements to reproduce the issue"""
    console.print(f"\n[bold blue]EdgarTools Version:[/bold blue] {edgar.__version__ if hasattr(edgar, '__version__') else 'Unknown'}")
    
    try:
        # Reproduce the exact steps from the issue
        aapl = edgar.Company("AAPL")
        filing = aapl.get_filings(form="10-K").latest()
        console.print(f"[bold green]Latest 10-K Filing:[/bold green] {filing.accession_no} ({filing.filing_date})")
        
        current = filing.xbrl().current_period
        console.print(f"[bold green]Current Period:[/bold green] {current}")
        
        # Test each statement
        balance_sheet = current.balance_sheet()
        income_statement = current.income_statement()
        cash_flow = current.cashflow_statement()
        
        # Report results
        table = Table(title="AAPL Statement Results")
        table.add_column("Statement", style="cyan")
        table.add_column("Rows", style="magenta")
        table.add_column("Columns", style="green")
        table.add_column("Status", style="yellow")
        
        table.add_row("Balance Sheet", str(len(balance_sheet)), str(len(balance_sheet.columns)), 
                     "✓ Working" if len(balance_sheet) > 20 else "✗ Issue")
        table.add_row("Income Statement", str(len(income_statement)), str(len(income_statement.columns)), 
                     "✓ Working" if len(income_statement) > 10 else "✗ Issue")
        table.add_row("Cashflow Statement", str(len(cash_flow)), str(len(cash_flow.columns)), 
                     "✓ Working" if len(cash_flow) > 10 else "✗ Issue")
        
        console.print(table)
        
        # Show details of problematic statements
        if len(income_statement) == 0:
            console.print("[bold red]Income Statement is EMPTY![/bold red]")
        else:
            console.print(f"[bold green]Income Statement sample:[/bold green]")
            console.print(income_statement.head())
            
        if len(cash_flow) < 10:
            console.print(f"[bold red]Cashflow Statement has only {len(cash_flow)} rows![/bold red]")
            console.print(cash_flow)
        else:
            console.print(f"[bold green]Cashflow Statement sample:[/bold green]")
            console.print(cash_flow.head())
            
        return {
            'balance_sheet': balance_sheet,
            'income_statement': income_statement,
            'cash_flow': cash_flow,
            'filing': filing,
            'current_period': current
        }
        
    except Exception as e:
        console.print(f"[bold red]Error occurred:[/bold red] {e}")
        raise

def debug_xbrl_structure(filing, current_period):
    """Debug the XBRL structure to understand what's happening"""
    console.print(f"\n[bold blue]Debugging XBRL Structure[/bold blue]")
    
    xbrl = filing.xbrl()
    console.print(f"XBRL periods: {len(xbrl.periods)}")
    
    for i, period in enumerate(xbrl.periods):
        console.print(f"Period {i}: {period}")
    
    # Check available statements in current period
    console.print(f"\nCurrent period: {current_period}")
    console.print(f"Available methods: {[m for m in dir(current_period) if not m.startswith('_')]}")

if __name__ == "__main__":
    results = test_aapl_statements()
    
    # If we have issues, debug further
    if len(results['income_statement']) == 0 or len(results['cash_flow']) < 10:
        console.print("\n[bold yellow]Issue reproduced! Debugging XBRL structure...[/bold yellow]")
        debug_xbrl_structure(results['filing'], results['current_period'])