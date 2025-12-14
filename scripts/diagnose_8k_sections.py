#!/usr/bin/env python3
"""
Diagnostic script to investigate 8-K section detection failures.

Tests the three detection strategies (TOC, heading, pattern) separately
to identify which fails and why.
"""
import logging

from rich.console import Console
from rich.panel import Panel

from edgar import Company
from edgar.documents import parse_html

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

console = Console()


def diagnose_filing(cik, accession, label="Filing"):
    """Diagnose section detection for a specific 8-K filing."""

    console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
    console.print(f"[bold cyan]Diagnosing: {label}[/bold cyan]")
    console.print(f"[bold cyan]{'='*70}[/bold cyan]")
    console.print(f"CIK: {cik}, Accession: {accession}\n")

    # Get filing
    company = Company(cik)
    filings = company.get_filings(form="8-K")
    filing = next((f for f in filings if f.accession_no == accession), None)

    if not filing:
        console.print("[red]✗ Filing not found[/red]")
        return

    console.print(f"[green]✓ Found filing: {filing.accession_no}[/green]")
    console.print(f"  Filing date: {filing.filing_date}")

    # Download and parse
    html_content = filing.document.download()
    console.print(f"[green]✓ Downloaded: {len(html_content):,} chars[/green]")

    doc = parse_html(html_content)
    console.print("[green]✓ Parsed document[/green]")

    # Extract text to verify items exist
    text = doc.text()
    console.print(f"[green]✓ Extracted text: {len(text):,} chars[/green]")

    # Find items in text
    import re
    item_pattern = re.compile(r'Item\s+(\d+\.?\s*\d*)', re.IGNORECASE)
    items_in_text = sorted(set(item_pattern.findall(text)))
    console.print(f"\n[bold]Items found in text:[/bold] {items_in_text}")

    # Show sample formatting
    samples = []
    for match in item_pattern.finditer(text):
        context_start = max(0, match.start() - 20)
        context_end = min(len(text), match.end() + 30)
        context = text[context_start:context_end].replace('\n', ' ')
        samples.append(context)
        if len(samples) >= 3:
            break

    if samples:
        console.print("\n[dim]Sample item formatting in text:[/dim]")
        for sample in samples:
            console.print(f"  [dim]...{sample.strip()}...[/dim]")

    # Test each detection strategy separately
    console.print("\n[bold yellow]Testing Detection Strategies:[/bold yellow]\n")

    # Strategy 1: TOC-based
    console.print("[bold]1. TOC-Based Detection[/bold]")
    from edgar.documents.extractors.toc_section_detector import TOCSectionDetector
    toc_detector = TOCSectionDetector(doc)
    toc_sections = toc_detector.detect() or {}
    console.print(f"  Result: [cyan]{len(toc_sections)} sections detected[/cyan]")
    if toc_sections:
        for name, section in list(toc_sections.items())[:5]:
            console.print(f"    • {name}: {section.title}")

    # Strategy 2: Heading-based
    console.print("\n[bold]2. Heading-Based Detection[/bold]")
    headings = doc.headings
    console.print(f"  Found {len(headings)} heading nodes")

    # Show headings with header_info
    heading_sections = 0
    for i, heading in enumerate(headings[:10]):
        if hasattr(heading, 'header_info') and heading.header_info:
            info = heading.header_info
            console.print(f"    • Heading {i+1}: confidence={info.confidence:.2f}, is_item={info.is_item}")
            if info.is_item and hasattr(info, 'item'):
                console.print(f"      Item: {info.item}, title={heading.text_content[:50]}")
                heading_sections += 1

    console.print(f"  Result: [cyan]{heading_sections} item headings found[/cyan]")

    # Strategy 3: Pattern-based
    console.print("\n[bold]3. Pattern-Based Detection[/bold]")
    from edgar.documents.extractors.pattern_section_extractor import SectionExtractor
    pattern_extractor = SectionExtractor('8-K')
    pattern_sections = pattern_extractor.extract(doc) or {}
    console.print(f"  Result: [cyan]{len(pattern_sections)} sections detected[/cyan]")
    if pattern_sections:
        for name, section in list(pattern_sections.items())[:5]:
            console.print(f"    • {name}: {section.title}")

    # Final result via doc.sections
    console.print("\n[bold]Final doc.sections result:[/bold]")
    sections = doc.sections
    console.print(f"  Result: [cyan]{len(sections)} sections in doc.sections[/cyan]")
    if sections:
        for name, section in list(sections.items())[:5]:
            console.print(f"    • {name}: {section.title} (method={section.detection_method}, conf={section.confidence:.2f})")

    # Summary
    console.print("\n[bold green]Summary:[/bold green]")
    console.print(f"  Items in text: {len(items_in_text)}")
    console.print(f"  TOC sections: {len(toc_sections)}")
    console.print(f"  Heading sections: {heading_sections}")
    console.print(f"  Pattern sections: {len(pattern_sections)}")
    console.print(f"  Final doc.sections: {len(sections)}")

    # Diagnosis
    if len(sections) == 0 and len(items_in_text) > 0:
        console.print("\n[bold red]⚠ FAILURE: Items exist in text but not detected by any strategy[/bold red]")
        if len(toc_sections) == 0:
            console.print("  • TOC detection failed (no TOC structure found)")
        if heading_sections == 0:
            console.print("  • Heading detection failed (no item headings found)")
        if len(pattern_sections) == 0:
            console.print("  • Pattern detection failed (regex patterns don't match)")
    elif len(sections) > 0:
        console.print("\n[bold green]✓ SUCCESS: Section detection working[/bold green]")


def main():
    """Run diagnostics on working and failing filings."""

    console.print(Panel.fit(
        "[bold cyan]8-K Section Detection Diagnostic Tool[/bold cyan]\n"
        "Testing detection strategies: TOC → Heading → Pattern",
        border_style="cyan"
    ))

    # Test 1: Working filing (2011)
    diagnose_filing(
        cik="919130",
        accession="0001144204-11-047401",
        label="WORKING Filing (2011) - Onstream Media"
    )

    # Test 2: Failing filing (2011)
    diagnose_filing(
        cik="109177",
        accession="0001144204-11-045676",
        label="FAILING Filing (2011) - Harbinger Group"
    )

    # Test 3: Modern failing filing (2025)
    diagnose_filing(
        cik="320193",
        accession="0000320193-25-000077",
        label="FAILING Filing (2025) - Apple"
    )

    console.print(f"\n[bold cyan]{'='*70}[/bold cyan]")
    console.print("[bold cyan]Diagnostic Complete[/bold cyan]")
    console.print(f"[bold cyan]{'='*70}[/bold cyan]\n")


if __name__ == "__main__":
    main()
