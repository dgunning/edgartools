#!/usr/bin/env python3
"""
Test the fix for issue #429
"""

import edgar
from rich.console import Console

console = Console()

def test_period_selection():
    """Test the period selection fix"""
    console.print(f"\n[bold blue]Testing period selection fix[/bold blue]")
    
    aapl = edgar.Company("AAPL")
    filing = aapl.get_filings(form="10-K").latest()
    xbrl = filing.xbrl()
    current = xbrl.current_period
    
    console.print(f"Current period key: {current.period_key}")
    
    # Test the new method directly
    for statement_type in ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement']:
        try:
            period_for_statement = current._get_appropriate_period_for_statement(statement_type)
            console.print(f"{statement_type}: {period_for_statement}")
        except Exception as e:
            console.print(f"{statement_type}: Error - {e}")

def test_statements_with_fix():
    """Test statements with the fix"""
    console.print(f"\n[bold blue]Testing statements with fix[/bold blue]")
    
    aapl = edgar.Company("AAPL")
    filing = aapl.get_filings(form="10-K").latest()
    current = filing.xbrl().current_period
    
    # Test each statement
    statements = {
        'Balance Sheet': current.balance_sheet(),
        'Income Statement': current.income_statement(),
        'Cashflow Statement': current.cashflow_statement()
    }
    
    for name, statement in statements.items():
        print(statement)

if __name__ == "__main__":
    test_period_selection()
    test_statements_with_fix()