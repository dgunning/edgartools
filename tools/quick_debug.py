#!/usr/bin/env python3
"""
Quick Debug Tool for EdgarTools
Visual inspection and debugging for maintainers

As a maintainer, you need to SEE what's happening quickly.
This tool provides instant visual inspection of any EdgarTools object.

Usage:
    # Quick look at any identifier
    python tools/quick_debug.py AAPL
    python tools/quick_debug.py 0000320193-18-000070

    # Specific investigations
    python tools/quick_debug.py --empty-periods 0000320193-18-000070
    python tools/quick_debug.py --entity-facts AAPL
    python tools/quick_debug.py --xbrl-structure 0000320193-18-000070

    # Comparisons
    python tools/quick_debug.py --compare 0000320193-18-000070 0000320193-25-000073

    # Statement inspection
    python tools/quick_debug.py --statement cashflow 0000320193-18-000070
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.visual_inspector import (
    show_statement, show_dataframe, show_xbrl, show_filing_overview,
    show_company_overview, compare_statements_visually, quick_look, peek
)
from tools.investigation_toolkit import (
    visual_debug, debug_empty_periods, debug_entity_facts, debug_xbrl_parsing,
    quick_analyze
)
from rich.console import Console
from rich.panel import Panel

console = Console()

def main():
    parser = argparse.ArgumentParser(
        description="Quick visual debugging for EdgarTools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/quick_debug.py AAPL                    # Company overview
  python tools/quick_debug.py 0000320193-18-000070    # Filing overview

  python tools/quick_debug.py --empty-periods 0000320193-18-000070
  python tools/quick_debug.py --entity-facts AAPL
  python tools/quick_debug.py --xbrl-structure 0000320193-18-000070

  python tools/quick_debug.py --statement cashflow 0000320193-18-000070
  python tools/quick_debug.py --compare 0000320193-18-000070 0000320193-25-000073
        """
    )

    # Primary identifier
    parser.add_argument("identifier", nargs="?",
                       help="Company ticker or filing accession number")

    # Visual inspection modes
    parser.add_argument("--empty-periods", metavar="ACCESSION",
                       help="Debug empty periods issue (cash flow statements)")
    parser.add_argument("--entity-facts", metavar="TICKER",
                       help="Debug entity facts access issues")
    parser.add_argument("--xbrl-structure", metavar="ACCESSION",
                       help="Debug XBRL parsing and structure issues")

    # Statement inspection
    parser.add_argument("--statement", nargs=2, metavar=("TYPE", "ACCESSION"),
                       help="Show specific statement (cashflow/income/balance)")

    # Comparisons
    parser.add_argument("--compare", nargs=2, metavar=("ACCESSION1", "ACCESSION2"),
                       help="Compare two filings side by side")

    # Options
    parser.add_argument("--max-rows", type=int, default=20,
                       help="Maximum rows to display in tables")
    parser.add_argument("--max-cols", type=int,
                       help="Maximum columns to display in tables")

    # Quick modes
    parser.add_argument("--peek", metavar="IDENTIFIER",
                       help="Quick peek at any identifier")

    args = parser.parse_args()

    # Set up identity
    try:
        from edgar import set_identity
        set_identity("Research Team research@edgartools-investigation.com")
    except:
        pass

    console.print(Panel.fit(
        "[bold blue]EdgarTools Quick Debug Tool[/bold blue]\n"
        "Visual inspection for maintainers",
        border_style="blue"
    ))

    try:
        # Handle different debug modes
        if args.empty_periods:
            console.print(f"[cyan]🔍 Debugging empty periods issue[/cyan]")
            debug_empty_periods(args.empty_periods)

        elif args.entity_facts:
            console.print(f"[cyan]🔍 Debugging entity facts issue[/cyan]")
            debug_entity_facts(args.entity_facts)

        elif args.xbrl_structure:
            console.print(f"[cyan]🔍 Debugging XBRL structure[/cyan]")
            debug_xbrl_parsing(args.xbrl_structure)

        elif args.statement:
            stmt_type, accession = args.statement
            console.print(f"[cyan]🔍 Inspecting {stmt_type} statement[/cyan]")
            show_statement(accession, stmt_type, max_rows=args.max_rows, max_cols=args.max_cols)

        elif args.compare:
            accession1, accession2 = args.compare
            console.print(f"[cyan]🔍 Comparing filings[/cyan]")
            compare_statements_visually(
                accession1, accession2, "cashflow",
                "Filing 1", "Filing 2"
            )

        elif args.peek:
            console.print(f"[cyan]🔍 Quick peek[/cyan]")
            peek(args.peek)

        elif args.identifier:
            console.print(f"[cyan]🔍 Auto-detecting what to show[/cyan]")
            quick_look(args.identifier)

        else:
            # Interactive mode
            console.print("[yellow]No arguments provided. Starting interactive mode...[/yellow]")
            interactive_debug()

    except Exception as e:
        console.print(f"[red]❌ Debug failed: {str(e)}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

def interactive_debug():
    """Interactive debugging session"""
    console.print("\n[bold green]🔍 Interactive Debug Session[/bold green]")
    console.print("Enter an identifier to inspect:")
    console.print("  • Company ticker (e.g., AAPL)")
    console.print("  • Filing accession (e.g., 0000320193-18-000070)")
    console.print("  • 'help' for more options")
    console.print("  • 'quit' to exit")

    while True:
        try:
            user_input = console.input("\n[cyan]Debug >[/cyan] ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                console.print("[green]👋 Goodbye![/green]")
                break

            elif user_input.lower() == 'help':
                show_help()

            elif user_input.lower().startswith('compare '):
                # Handle compare command
                parts = user_input.split()[1:]
                if len(parts) == 2:
                    compare_statements_visually(parts[0], parts[1], "cashflow")
                else:
                    console.print("[red]Usage: compare ACCESSION1 ACCESSION2[/red]")

            elif user_input.lower().startswith('stmt '):
                # Handle statement command
                parts = user_input.split()[1:]
                if len(parts) == 2:
                    show_statement(parts[1], parts[0])
                else:
                    console.print("[red]Usage: stmt TYPE ACCESSION (e.g., stmt cashflow 0000320193-18-000070)[/red]")

            elif user_input:
                # Auto-detect and show
                quick_look(user_input)

        except KeyboardInterrupt:
            console.print("\n[green]👋 Goodbye![/green]")
            break
        except Exception as e:
            console.print(f"[red]❌ Error: {str(e)}[/red]")

def show_help():
    """Show interactive help"""
    help_text = """
[bold]Available Commands:[/bold]

[cyan]Basic Inspection:[/cyan]
  AAPL                           → Company overview
  0000320193-18-000070          → Filing overview

[cyan]Statements:[/cyan]
  stmt cashflow ACCESSION       → Cash flow statement
  stmt income ACCESSION         → Income statement
  stmt balance ACCESSION        → Balance sheet

[cyan]Comparisons:[/cyan]
  compare ACCESSION1 ACCESSION2 → Side-by-side comparison

[cyan]Special Modes:[/cyan]
  Just enter any identifier for auto-detection

[cyan]Exit:[/cyan]
  quit, exit, q, or Ctrl+C      → Exit interactive mode

[yellow]Pro tip:[/yellow] Use command line for specific modes:
  python tools/quick_debug.py --empty-periods ACCESSION
  python tools/quick_debug.py --entity-facts TICKER
    """
    console.print(Panel(help_text, title="Help", border_style="blue"))

if __name__ == "__main__":
    main()