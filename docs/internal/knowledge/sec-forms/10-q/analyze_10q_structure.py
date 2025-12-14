#!/usr/bin/env python3
"""
Analyze 10-Q Filing Structure
Research script to examine real 10-Q filings and document their Part/Item structure.
"""

import re
from collections import defaultdict

from rich import print as rprint
from rich.console import Console
from rich.table import Table

from edgar import *

console = Console()

# Sample companies across different industries and sizes
SAMPLE_COMPANIES = [
    "AAPL",   # Technology - Large Cap
    "MSFT",   # Technology - Large Cap
    "JPM",    # Financial - Large Cap
    "JNJ",    # Healthcare - Large Cap
    "WMT",    # Retail - Large Cap
    "XOM",    # Energy - Large Cap
    "DIS",    # Entertainment - Large Cap
    "TSLA",   # Automotive - Large Cap
    "NFLX",   # Technology/Media - Large Cap
    "BA"      # Industrial - Large Cap
]

def extract_toc_sections(filing):
    """Extract table of contents sections from filing HTML."""
    try:
        html_content = filing.html()
        if not html_content:
            return None

        # Look for common TOC patterns
        sections = {
            'parts': [],
            'items': []
        }

        # Pattern 1: Look for "Part I" and "Part II" headers
        part_pattern = r'(?:href=["#].*?[">\s]*)?<[^>]*>(Part\s+[IVX]+)[^<]*</[^>]*>'
        parts = re.findall(part_pattern, html_content, re.IGNORECASE)

        # Pattern 2: Look for "Item X" entries
        item_pattern = r'(?:href=["#].*?[">\s]*)?<[^>]*>(Item\s+\d+[A-Z]?\.?)[^<]*([^<]+)</[^>]*>'
        items = re.findall(item_pattern, html_content, re.IGNORECASE)

        # Clean up findings
        sections['parts'] = list(set(parts))
        sections['items'] = [(item[0].strip(), item[1].strip()[:100]) for item in items[:20]]  # First 20 items

        return sections
    except Exception as e:
        console.print(f"[red]Error extracting TOC: {e}[/red]")
        return None

def analyze_filing_structure(ticker, max_filings=3):
    """Analyze 10-Q structure for a company."""
    try:
        company = Company(ticker)
        filings = company.get_filings(form="10-Q").latest(max_filings)

        results = []
        for filing in filings:
            console.print(f"[cyan]Analyzing {ticker} - {filing.form} filed {filing.filing_date}[/cyan]")

            sections = extract_toc_sections(filing)
            if sections:
                results.append({
                    'ticker': ticker,
                    'accession': filing.accession_no,
                    'filing_date': filing.filing_date,
                    'parts': sections['parts'],
                    'items': sections['items']
                })

        return results
    except Exception as e:
        console.print(f"[red]Error analyzing {ticker}: {e}[/red]")
        return []

def main():
    """Main research execution."""
    console.print("\n[bold green]10-Q Filing Structure Analysis[/bold green]")
    console.print("[yellow]Examining real 10-Q filings to validate official structure[/yellow]\n")

    all_results = []
    item_frequency = defaultdict(int)
    part_frequency = defaultdict(int)

    # Analyze sample of companies
    for ticker in SAMPLE_COMPANIES[:5]:  # Start with first 5
        results = analyze_filing_structure(ticker, max_filings=2)
        all_results.extend(results)

        # Track frequency of items and parts
        for result in results:
            for part in result['parts']:
                part_frequency[part] += 1
            for item, title in result['items']:
                item_key = f"{item} - {title[:50]}"
                item_frequency[item_key] += 1

    # Display Parts frequency
    console.print("\n[bold]Part Structure Frequency[/bold]")
    part_table = Table(show_header=True)
    part_table.add_column("Part", style="cyan")
    part_table.add_column("Frequency", style="green")

    for part in sorted(part_frequency.keys()):
        part_table.add_row(part, str(part_frequency[part]))
    console.print(part_table)

    # Display most common Items
    console.print("\n[bold]Most Common Items Across Filings[/bold]")
    item_table = Table(show_header=True)
    item_table.add_column("Item", style="cyan", width=60)
    item_table.add_column("Frequency", style="green")

    sorted_items = sorted(item_frequency.items(), key=lambda x: x[1], reverse=True)
    for item, freq in sorted_items[:20]:  # Top 20
        item_table.add_row(item, str(freq))
    console.print(item_table)

    # Show sample structure from one filing
    if all_results:
        console.print("\n[bold]Sample Filing Structure[/bold]")
        sample = all_results[0]
        console.print(f"[cyan]{sample['ticker']} - {sample['accession']}[/cyan]")
        console.print(f"[yellow]Filing Date: {sample['filing_date']}[/yellow]\n")

        console.print("[bold]Parts:[/bold]")
        for part in sample['parts']:
            console.print(f"  • {part}")

        console.print("\n[bold]Items (sample):[/bold]")
        for item, title in sample['items'][:10]:
            console.print(f"  • {item}: {title}")

if __name__ == "__main__":
    main()
