"""
Demo: ThirteenF Holdings Comparison & History
==============================================

Shows how to use compare_holdings() and holding_history() to track
how an institutional investor's portfolio changes across quarters.

Usage:
    python -m edgar.thirteenf.demo_comparison
    python -m edgar.thirteenf.demo_comparison --ticker "BERKSHIRE HATHAWAY"
    python -m edgar.thirteenf.demo_comparison --ticker "BRIDGEWATER ASSOCIATES" --periods 6
"""

import argparse

from rich.console import Console

from edgar import Company

console = Console()


def demo_compare_holdings(thirteen_f):
    """Show quarter-over-quarter holdings diff."""
    console.rule("[bold]compare_holdings()[/bold]")

    comp = thirteen_f.compare_holdings()
    if comp is None:
        console.print("[yellow]No previous quarter available for comparison.[/yellow]")
        return

    # Rich display
    console.print(comp)
    console.print()

    # Programmatic access
    df = comp.data
    new = df[df.Status == "NEW"]
    closed = df[df.Status == "CLOSED"]
    console.print(f"[green]New positions:[/green]  {len(new)}")
    console.print(f"[red]Closed positions:[/red] {len(closed)}")
    console.print(f"Total securities compared: {len(comp)}")
    console.print()

    # Top 5 increases by value change
    increased = df[df.Status == "INCREASED"].head(5)
    if len(increased):
        console.print("[bold]Top 5 increases by value change:[/bold]")
        for row in increased.itertuples():
            console.print(f"  {row.Issuer:30s}  {row.Ticker or '':6s}  Value Chg: ${int(row.ValueChange):>+12,}")
        console.print()


def demo_holding_history(thirteen_f, periods=4):
    """Show multi-quarter share history with sparklines."""
    console.rule("[bold]holding_history()[/bold]")

    hist = thirteen_f.holding_history(periods=periods)
    if hist is None:
        console.print("[yellow]No history available.[/yellow]")
        return

    # Rich display
    console.print(hist)
    console.print()

    # Programmatic access
    df = hist.data
    console.print(f"Periods covered: {hist.periods}")
    console.print(f"Securities tracked: {len(hist)}")
    console.print()

    # Show top 5 holdings from most recent period
    most_recent = hist.periods[-1]
    top5 = df.nlargest(5, most_recent, keep="first")
    console.print(f"[bold]Top 5 holdings as of {most_recent}:[/bold]")
    for _, row in top5.iterrows():
        shares = row.get(most_recent, 0)
        if shares and shares == shares:  # not NaN
            console.print(f"  {row['Issuer']:30s}  {row.get('Ticker') or '':6s}  {int(shares):>14,} shares")
    console.print()


def main():
    parser = argparse.ArgumentParser(description="Demo: ThirteenF Holdings Comparison & History")
    parser.add_argument("--ticker", default="BRK",
                        help="Company name or ticker to look up (default: BERKSHIRE HATHAWAY)")
    parser.add_argument("--periods", type=int, default=4,
                        help="Number of quarters for holding_history (default: 4)")
    args = parser.parse_args()

    console.rule(f"[bold blue]13F Holdings Demo: {args.ticker}[/bold blue]")
    console.print()

    # Fetch the latest 13F-HR filing
    company = Company(args.ticker)
    console.print(f"Company: {company.name} (CIK: {company.cik})")

    filings = company.get_filings(form="13F-HR")
    if filings is None or len(filings) == 0:
        console.print("[red]No 13F-HR filings found.[/red]")
        return

    latest = filings.latest()
    console.print(f"Latest filing: {latest.accession_no}  filed {latest.filing_date}")
    console.print()

    thirteen_f = latest.obj()
    console.print(f"Report period: {thirteen_f.report_period}")
    console.print(f"Manager: {thirteen_f.management_company_name}")
    console.print(f"Total holdings: {thirteen_f.total_holdings}")
    console.print(f"Total value: ${thirteen_f.total_value:,.0f}K" if thirteen_f.total_value else "Total value: N/A")
    console.print()

    # Demo both features
    demo_compare_holdings(thirteen_f)
    demo_holding_history(thirteen_f, periods=args.periods)

    console.rule("[bold blue]Done[/bold blue]")


if __name__ == "__main__":
    main()
