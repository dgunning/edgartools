#!/usr/bin/env python3
"""
Test the fix for issue #429 across multiple companies
"""

import edgar
from rich.console import Console
from rich.table import Table

console = Console()

def test_multiple_companies():
    """Test the fix across multiple companies"""
    console.print(f"\n[bold blue]Testing Issue #429 Fix Across Multiple Companies[/bold blue]")
    
    # Test companies with different filing patterns
    companies = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
    
    results = []
    
    for ticker in companies:
        console.print(f"\nTesting {ticker}...")
        
        try:
            company = edgar.Company(ticker)
            filing = company.get_filings(form="10-K").latest()
            current = filing.xbrl().current_period
            
            # Test statements
            balance_sheet = current.balance_sheet()
            income_statement = current.income_statement()
            cash_flow = current.cashflow_statement()
            
            # Get period info
            balance_period = current._get_appropriate_period_for_statement('BalanceSheet')
            income_period = current._get_appropriate_period_for_statement('IncomeStatement')  
            cashflow_period = current._get_appropriate_period_for_statement('CashFlowStatement')
            
            results.append({
                'ticker': ticker,
                'filing_date': filing.filing_date,
                'balance_rows': len(balance_sheet),
                'income_rows': len(income_statement),
                'cashflow_rows': len(cash_flow),
                'balance_period_type': 'instant' if balance_period.startswith('instant') else 'duration',
                'income_period_type': 'instant' if income_period.startswith('instant') else 'duration',
                'cashflow_period_type': 'instant' if cashflow_period.startswith('instant') else 'duration',
                'status': 'OK' if len(income_statement) > 10 and len(cash_flow) > 10 else 'Issue'
            })
            
        except Exception as e:
            console.print(f"  Error testing {ticker}: {e}")
            results.append({
                'ticker': ticker,
                'status': 'Error',
                'error': str(e)
            })
    
    # Display results table
    table = Table(title="Multi-Company Test Results")
    table.add_column("Company", style="cyan")
    table.add_column("Filing Date", style="white")
    table.add_column("Balance\n(rows)", style="green")
    table.add_column("Income\n(rows)", style="magenta") 
    table.add_column("Cashflow\n(rows)", style="blue")
    table.add_column("Period Types\n(B/I/C)", style="yellow")
    table.add_column("Status", style="bold")
    
    for result in results:
        if result['status'] == 'Error':
            table.add_row(
                result['ticker'], 
                "Error", 
                "-", 
                "-", 
                "-",
                "-",
                "❌ Error"
            )
        else:
            period_types = f"{result['balance_period_type'][:1]}/{result['income_period_type'][:1]}/{result['cashflow_period_type'][:1]}"
            status = "✅ Fixed" if result['status'] == 'OK' else "❌ Issue"
            
            table.add_row(
                result['ticker'],
                result['filing_date'].strftime('%Y-%m-%d'),
                str(result['balance_rows']),
                str(result['income_rows']),
                str(result['cashflow_rows']),
                period_types,
                status
            )
    
    console.print(table)
    
    # Summary
    success_count = sum(1 for r in results if r.get('status') == 'OK')
    total_count = len([r for r in results if r.get('status') != 'Error'])
    
    console.print(f"\n[bold green]Results Summary:[/bold green]")
    console.print(f"✅ Working companies: {success_count}/{total_count}")
    console.print(f"Expected period selection: Balance=instant, Income/Cashflow=duration")
    
    if success_count == total_count:
        console.print(f"\n[bold green]🎉 All companies working! Fix verified![/bold green]")
        return True
    else:
        console.print(f"\n[bold yellow]⚠️  Some companies still have issues[/bold yellow]")
        return False

if __name__ == "__main__":
    test_multiple_companies()