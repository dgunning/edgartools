#!/usr/bin/env python3
"""
Manual 10-Q Filing Inspection
Direct examination of 10-Q HTML to understand structure.
"""

import re

from rich.console import Console

from edgar import Company

console = Console()

def inspect_toc(ticker="AAPL", form="10-Q"):
    """Manually inspect Table of Contents."""
    company = Company(ticker)
    filing = company.get_filings(form=form).latest(1)

    console.print(f"\n[bold cyan]{ticker} {form} - {filing.filing_date}[/bold cyan]")
    console.print(f"[yellow]Accession: {filing.accession_no}[/yellow]\n")

    html = filing.html()

    # Find table of contents section
    # Look for common TOC markers
    toc_patterns = [
        r'<a[^>]*name=["\']?toc["\']?[^>]*>.*?</a>',
        r'TABLE OF CONTENTS',
        r'Index to',
        r'<div[^>]*>(?:\s*TABLE OF CONTENTS\s*)</div>'
    ]

    toc_section = None
    for pattern in toc_patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            # Extract surrounding 10000 characters
            start = max(0, match.start() - 1000)
            end = min(len(html), match.end() + 15000)
            toc_section = html[start:end]
            console.print(f"[green]Found TOC using pattern: {pattern[:50]}...[/green]\n")
            break

    if toc_section:
        # Look for Part and Item references
        console.print("[bold]Part References:[/bold]")
        part_matches = re.findall(
            r'(?:<[^>]*>)*(PART\s+[IVX]+)(?:\s*[-–—]\s*)?([^<]{0,100})',
            toc_section,
            re.IGNORECASE
        )
        for i, (part, title) in enumerate(part_matches[:10], 1):
            console.print(f"  {i}. {part.strip()}: {title.strip()[:80]}")

        console.print("\n[bold]Item References:[/bold]")
        item_matches = re.findall(
            r'(?:<[^>]*>)*(Item\s+\d+[A-Z]?\.?)(?:\s*)?([^<]{0,150})',
            toc_section,
            re.IGNORECASE
        )

        # Deduplicate and limit
        seen = set()
        for i, (item, title) in enumerate(item_matches, 1):
            key = item.strip().upper()
            if key not in seen and len(seen) < 20:
                seen.add(key)
                # Clean up title
                title_clean = title.strip()
                title_clean = re.sub(r'\s+', ' ', title_clean)
                title_clean = re.sub(r'^[-–—\s.]+', '', title_clean)
                console.print(f"  {i}. {item.strip()}: {title_clean[:80]}")

    # Also try finding section headers directly in content
    console.print("\n[bold]Direct Section Headers (first 20):[/bold]")

    # Search for bold Item headers
    header_pattern = r'<(?:b|strong|span[^>]*font-weight:\s*(?:bold|700)[^>]*)>([^<]*(?:PART\s+[IVX]+|Item\s+\d+[A-Z]?\.?)[^<]*)</(?:b|strong|span)>'
    headers = re.findall(header_pattern, html, re.IGNORECASE)

    seen_headers = set()
    count = 0
    for header in headers:
        header_clean = re.sub(r'\s+', ' ', header.strip())
        if header_clean and header_clean not in seen_headers and count < 20:
            seen_headers.add(header_clean)
            console.print(f"  {count+1}. {header_clean[:100]}")
            count += 1

def compare_forms():
    """Compare 10-Q and 10-K."""
    console.print("\n" + "="*80)
    console.print("[bold green]10-Q Structure:[/bold green]")
    inspect_toc("AAPL", "10-Q")

    console.print("\n" + "="*80)
    console.print("[bold green]10-K Structure:[/bold green]")
    inspect_toc("AAPL", "10-K")

if __name__ == "__main__":
    compare_forms()
