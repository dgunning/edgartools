#!/usr/bin/env python3
"""
Extract 10-Q structure from multiple companies.
"""

import re

from rich.console import Console
from rich.table import Table

from edgar import Company

console = Console()

def extract_structure(ticker, form="10-Q"):
    """Extract structure from filing."""
    try:
        company = Company(ticker)
        filing = company.get_filings(form=form).latest(1)
        html = filing.html()

        # Find section headers
        header_pattern = r'<(?:b|strong|span[^>]*font-weight:\s*(?:bold|700)[^>]*)>([^<]*(?:PART\s+[IVX]+|Item\s+\d+[A-Z]?\.?)[^<]*)</(?:b|strong|span)>'
        headers = re.findall(header_pattern, html, re.IGNORECASE)

        # Clean and deduplicate
        cleaned = []
        seen = set()
        for header in headers:
            header_clean = re.sub(r'\s+', ' ', header.strip())
            header_clean = re.sub(r'&#\d+;', ' ', header_clean)  # Remove HTML entities
            header_clean = re.sub(r'\s+', ' ', header_clean).strip()

            if header_clean and header_clean not in seen:
                seen.add(header_clean)
                cleaned.append(header_clean)

        return {
            'ticker': ticker,
            'form': form,
            'filing_date': filing.filing_date,
            'sections': cleaned[:20]  # First 20 unique sections
        }
    except Exception as e:
        console.print(f"[red]Error processing {ticker} {form}: {e}[/red]")
        return None

def main():
    """Extract structures from multiple companies."""
    companies = ["AAPL", "MSFT", "JPM", "GOOGL", "TSLA", "JNJ"]

    console.print("[bold green]10-Q Structure Analysis Across Companies[/bold green]\n")

    for ticker in companies:
        result = extract_structure(ticker, "10-Q")
        if result:
            table = Table(title=f"{ticker} 10-Q Structure ({result['filing_date']})", show_header=True)
            table.add_column("#", style="cyan", width=4)
            table.add_column("Section", style="white", width=80)

            for i, section in enumerate(result['sections'], 1):
                table.add_row(str(i), section)

            console.print(table)
            console.print()

    # Also show one 10-K for comparison
    console.print("\n[bold yellow]10-K Structure for Comparison (AAPL):[/bold yellow]\n")
    result_10k = extract_structure("AAPL", "10-K")
    if result_10k:
        table = Table(title=f"AAPL 10-K Structure ({result_10k['filing_date']})", show_header=True)
        table.add_column("#", style="cyan", width=4)
        table.add_column("Section", style="white", width=80)

        for i, section in enumerate(result_10k['sections'], 1):
            table.add_row(str(i), section)

        console.print(table)

if __name__ == "__main__":
    main()
