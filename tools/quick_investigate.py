"""
Quick investigation launcher for common EdgarTools issue patterns

Usage Examples:
    # Quick empty periods analysis
    python tools/quick_investigate.py --issue 408 --pattern empty-periods --filing 0000320193-18-000070

    # Comparative analysis
    python tools/quick_investigate.py --issue 408 --pattern empty-periods --compare

    # Entity facts investigation
    python tools/quick_investigate.py --issue 412 --pattern entity-facts --ticker AAPL

    # Full investigation workflow
    python tools/quick_investigate.py --issue 408 --pattern empty-periods --full-analysis
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.investigation_toolkit import (
    IssueAnalyzer, quick_analyze, compare_filings,
    STANDARD_TEST_COMPANIES, get_test_company_info
)
from rich.console import Console
from rich.panel import Panel

console = Console()

def investigate_empty_periods(issue_number: int, **kwargs):
    """Quick investigation for empty period issues (Issue #408 pattern)"""
    console.print(Panel.fit(
        f"[bold blue]Empty Periods Investigation - Issue #{issue_number}[/bold blue]",
        border_style="blue"
    ))

    if kwargs.get('full_analysis'):
        # Full systematic analysis
        analyzer = IssueAnalyzer(issue_number)
        analyzer.add_standard_test_cases("empty_periods")
        analyzer.run_comparative_analysis()
        analyzer.generate_report()

    elif kwargs.get('compare'):
        # Compare working vs broken filings
        console.print("[cyan]Comparing working vs problematic filings...[/cyan]")
        result = compare_filings(
            "0000320193-25-000073",  # Recent working
            "0000320193-18-000070",  # Older problematic
            "Recent Apple Q2 2025 (Working)",
            "Apple Q1 2018 (Problematic)"
        )

    elif kwargs.get('filing'):
        # Single filing analysis
        filing = kwargs['filing']
        console.print(f"[cyan]Analyzing single filing: {filing}[/cyan]")
        result = quick_analyze("empty_periods", filing)

        if result['success']:
            console.print(f"✅ Analysis complete")
            console.print(f"   Total periods: {result['total_periods']}")
            console.print(f"   Empty periods: {len(result['empty_periods'])}")
            console.print(f"   Has issue: {result['has_empty_string_issue']}")
        else:
            console.print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")

    elif kwargs.get('ticker'):
        # Company-based analysis
        ticker = kwargs['ticker']
        console.print(f"[cyan]Analyzing company: {ticker}[/cyan]")
        result = quick_analyze("empty_periods", ticker)

    else:
        # Default: Standard test cases
        console.print("[cyan]Running standard empty periods test cases...[/cyan]")
        test_cases = [
            ("0000320193-25-000073", "Recent Apple Q2 2025 (Working)"),
            ("0000320193-18-000070", "Apple Q1 2018 (Problematic)"),
            ("0000320193-17-000009", "Apple Q3 2017 (Problematic)")
        ]

        for accession, description in test_cases:
            console.print(f"\n[yellow]Testing: {description}[/yellow]")
            result = quick_analyze("empty_periods", accession)

            if result['success']:
                status = "❌ HAS ISSUE" if result['has_empty_string_issue'] else "✅ NO ISSUE"
                console.print(f"   {status} - {result['total_periods']} periods, {len(result['empty_periods'])} empty")
            else:
                console.print(f"   ❌ FAILED - {result.get('error', 'Unknown error')}")

def investigate_xbrl_parsing(issue_number: int, **kwargs):
    """Quick investigation for XBRL parsing issues"""
    console.print(Panel.fit(
        f"[bold blue]XBRL Parsing Investigation - Issue #{issue_number}[/bold blue]",
        border_style="blue"
    ))

    if kwargs.get('filing'):
        filing = kwargs['filing']
        console.print(f"[cyan]Analyzing XBRL parsing for: {filing}[/cyan]")
        result = quick_analyze("xbrl_parsing", filing)

        if result['success']:
            console.print(f"✅ XBRL parsing successful")
            console.print(f"   Form: {result.get('form', 'Unknown')}")
            console.print(f"   Company: {result.get('company', 'Unknown')}")
            console.print(f"   Has statements: {result.get('has_statements', False)}")
        else:
            console.print(f"❌ XBRL parsing failed: {result.get('error', 'Unknown error')}")

    else:
        # Standard XBRL test cases
        console.print("[cyan]Running standard XBRL parsing test cases...[/cyan]")
        test_cases = [
            ("0000320193-25-000073", "Apple Q2 2025"),
            ("0001628280-17-004790", "Tesla 2017 Q4"),
        ]

        for accession, description in test_cases:
            console.print(f"\n[yellow]Testing: {description}[/yellow]")
            result = quick_analyze("xbrl_parsing", accession)

            if result['success']:
                console.print(f"   ✅ SUCCESS - {result.get('form', 'Unknown form')}")
            else:
                console.print(f"   ❌ FAILED - {result.get('error', 'Unknown error')}")

def investigate_entity_facts(issue_number: int, **kwargs):
    """Quick investigation for entity facts issues"""
    console.print(Panel.fit(
        f"[bold blue]Entity Facts Investigation - Issue #{issue_number}[/bold blue]",
        border_style="blue"
    ))

    if kwargs.get('ticker'):
        ticker = kwargs['ticker']
        console.print(f"[cyan]Analyzing entity facts for: {ticker}[/cyan]")
        result = quick_analyze("entity_facts", ticker)

        if result['success']:
            console.print(f"✅ Entity facts loaded successfully")
            console.print(f"   CIK: {result.get('cik', 'Unknown')}")
            console.print(f"   Company: {result.get('name', 'Unknown')}")
            console.print(f"   Has income statement: {result.get('has_income_statement', False)}")
            console.print(f"   Has balance sheet: {result.get('has_balance_sheet', False)}")
            console.print(f"   Has cash flow: {result.get('has_cash_flow_statement', False)}")
        else:
            console.print(f"❌ Entity facts failed: {result.get('error', 'Unknown error')}")

    else:
        # Standard entity facts test cases
        console.print("[cyan]Running standard entity facts test cases...[/cyan]")
        test_companies = ['AAPL', 'MSFT', 'TSLA']

        for ticker in test_companies:
            console.print(f"\n[yellow]Testing: {ticker}[/yellow]")
            result = quick_analyze("entity_facts", ticker)

            if result['success']:
                console.print(f"   ✅ SUCCESS - {result.get('name', 'Unknown')}")
            else:
                console.print(f"   ❌ FAILED - {result.get('error', 'Unknown error')}")

def investigate_custom_pattern(issue_number: int, **kwargs):
    """Custom investigation for specific issue requirements"""
    console.print(Panel.fit(
        f"[bold blue]Custom Investigation - Issue #{issue_number}[/bold blue]",
        border_style="blue"
    ))

    console.print("[yellow]Setting up custom investigation...[/yellow]")

    analyzer = IssueAnalyzer(issue_number)

    if kwargs.get('filing'):
        analyzer.add_test_case(
            "custom_filing",
            description=f"Custom filing analysis for issue #{issue_number}",
            accession=kwargs['filing']
        )

    if kwargs.get('ticker'):
        analyzer.add_test_case(
            "custom_company",
            description=f"Custom company analysis for issue #{issue_number}",
            ticker=kwargs['ticker']
        )

    if not analyzer.test_cases:
        console.print("[red]No test cases specified for custom investigation[/red]")
        console.print("Use --filing or --ticker to specify what to analyze")
        return

    analyzer.run_comparative_analysis()
    analyzer.generate_report()

# Pattern mapping
INVESTIGATION_PATTERNS = {
    'empty-periods': investigate_empty_periods,
    'xbrl-parsing': investigate_xbrl_parsing,
    'entity-facts': investigate_entity_facts,
    'custom': investigate_custom_pattern
}

def main():
    parser = argparse.ArgumentParser(description="Quick EdgarTools issue investigation")

    # Required arguments
    parser.add_argument("--issue", type=int, required=True,
                       help="GitHub issue number")
    parser.add_argument("--pattern", choices=INVESTIGATION_PATTERNS.keys(), required=True,
                       help="Investigation pattern to use")

    # Optional analysis parameters
    parser.add_argument("--filing", type=str,
                       help="Specific filing accession number to analyze")
    parser.add_argument("--ticker", type=str,
                       help="Company ticker symbol to analyze")

    # Analysis modes
    parser.add_argument("--compare", action="store_true",
                       help="Compare working vs broken filings")
    parser.add_argument("--full-analysis", action="store_true",
                       help="Run comprehensive analysis with all test cases")

    # Utility options
    parser.add_argument("--list-companies", action="store_true",
                       help="List standard test companies")

    args = parser.parse_args()

    if args.list_companies:
        console.print("[bold blue]Standard Test Companies[/bold blue]")
        for ticker, info in STANDARD_TEST_COMPANIES.items():
            console.print(f"\n[cyan]{ticker}[/cyan]")
            console.print(f"  CIK: {info.get('cik', 'Unknown')}")
            console.print(f"  Fiscal Year End: {info.get('fiscal_year_end', 'Unknown')}")
            if 'known_issues' in info:
                console.print(f"  Known Issues: {', '.join(info['known_issues'])}")
            if 'notes' in info:
                console.print(f"  Notes: {info['notes']}")
        return

    # Run investigation
    console.print(f"[bold green]🔍 Starting Investigation for Issue #{args.issue}[/bold green]")
    console.print(f"Pattern: {args.pattern}")

    investigation_func = INVESTIGATION_PATTERNS[args.pattern]

    # Prepare kwargs
    kwargs = {
        'filing': args.filing,
        'ticker': args.ticker,
        'compare': args.compare,
        'full_analysis': args.full_analysis
    }

    try:
        investigation_func(args.issue, **kwargs)
        console.print(f"\n[bold green]✅ Investigation complete for Issue #{args.issue}[/bold green]")

    except Exception as e:
        console.print(f"\n[bold red]❌ Investigation failed: {str(e)}[/bold red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

if __name__ == "__main__":
    main()