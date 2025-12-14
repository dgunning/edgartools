#!/usr/bin/env python3
"""
Detailed 10-Q Filing Structure Analysis
Examines actual 10-Q filings to extract complete Part/Item structure with titles.
"""

import re

from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

from edgar import *

console = Console()

def analyze_filing_detailed(ticker, form="10-Q"):
    """Analyze a single 10-Q filing in detail."""
    try:
        company = Company(ticker)
        filing = company.get_filings(form=form).latest(1)

        console.print(f"\n[bold cyan]Analyzing: {ticker} {form}[/bold cyan]")
        console.print(f"[yellow]Filed: {filing.filing_date}[/yellow]")
        console.print(f"[yellow]Accession: {filing.accession_no}[/yellow]\n")

        # Get HTML content
        html_content = filing.html()
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all text containing "Item" and "Part"
        sections_found = []

        # Method 1: Search for patterns in text
        text = soup.get_text()
        lines = text.split('\n')

        part_pattern = re.compile(r'^(PART\s+[IVX]+)\s*[-–—]\s*(.+)$', re.IGNORECASE)
        item_pattern = re.compile(r'^(Item\s+\d+[A-Z]?\.?)\s+(.+)$', re.IGNORECASE)

        current_part = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for Part
            part_match = part_pattern.match(line)
            if part_match:
                current_part = part_match.group(1).strip()
                part_title = part_match.group(2).strip()
                sections_found.append({
                    'type': 'Part',
                    'number': current_part,
                    'title': part_title,
                    'parent': None
                })
                continue

            # Check for Item
            item_match = item_pattern.match(line)
            if item_match and len(line) < 200:  # Reasonable title length
                item_num = item_match.group(1).strip()
                item_title = item_match.group(2).strip()
                sections_found.append({
                    'type': 'Item',
                    'number': item_num,
                    'title': item_title[:100],  # Truncate long titles
                    'parent': current_part
                })

        # Display findings
        if sections_found:
            table = Table(title=f"{ticker} {form} Structure", show_header=True)
            table.add_column("Type", style="cyan", width=8)
            table.add_column("Number", style="green", width=12)
            table.add_column("Title", style="white", width=60)
            table.add_column("Parent", style="yellow", width=10)

            for section in sections_found[:30]:  # First 30 sections
                table.add_row(
                    section['type'],
                    section['number'],
                    section['title'],
                    section['parent'] or ""
                )

            console.print(table)

        return sections_found

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return []

def compare_10q_10k_structure():
    """Compare 10-Q vs 10-K structure for same company."""
    ticker = "AAPL"

    console.print("\n[bold green]Comparing 10-Q vs 10-K Structure[/bold green]\n")

    console.print("[bold]10-Q Structure:[/bold]")
    sections_10q = analyze_filing_detailed(ticker, "10-Q")

    console.print("\n[bold]10-K Structure:[/bold]")
    sections_10k = analyze_filing_detailed(ticker, "10-K")

    # Summarize differences
    console.print("\n[bold magenta]Key Differences:[/bold magenta]")

    parts_10q = [s for s in sections_10q if s['type'] == 'Part']
    parts_10k = [s for s in sections_10k if s['type'] == 'Part']

    console.print(f"\n10-Q has {len(parts_10q)} Parts")
    console.print(f"10-K has {len(parts_10k)} Parts")

    items_10q = [s for s in sections_10q if s['type'] == 'Item']
    items_10k = [s for s in sections_10k if s['type'] == 'Item']

    console.print(f"\n10-Q has {len(items_10q)} Items")
    console.print(f"10-K has {len(items_10k)} Items")

def main():
    """Main execution."""
    # Analyze multiple companies
    companies = ["AAPL", "MSFT", "JPM"]

    for ticker in companies[:1]:  # Start with one
        analyze_filing_detailed(ticker, "10-Q")

    # Compare 10-Q vs 10-K
    compare_10q_10k_structure()

if __name__ == "__main__":
    main()
