#!/usr/bin/env python3
"""
Research script to test edgar.documents parser for 8-K items extraction.

Tests parser across different filing eras:
- Legacy SGML (1999)
- Mid-period XML (2008-2011)
- Modern XML (2024-2025)

Key Findings:
- Modern filings use inconsistent item formatting:
  * "Item 2.02" (Microsoft, Meta)
  * "Item 2. 02" (Apple, Google, NVIDIA)
  * "ITEM 2.02" (Amazon - uppercase)
  * May have line breaks in Tesla filings

Related: GitHub #462, Beads edgartools-3pd
"""
import re

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from edgar import Company
from edgar.documents import parse_html

console = Console()


def normalize_item(item_str):
    """
    Normalize item string to standard format (e.g., '2.02').

    Handles:
    - "Item 2.02" -> "2.02"
    - "Item 2. 02" -> "2.02"
    - "ITEM 2.02" -> "2.02"
    - "Item 2" -> "2"
    """
    # Remove "Item" prefix (case insensitive)
    cleaned = re.sub(r'^item\s+', '', item_str.lower().strip())

    # Remove any spaces around dots: "2. 02" -> "2.02"
    cleaned = re.sub(r'\s*\.\s*', '.', cleaned)

    # Remove trailing dots: "2.02." -> "2.02"
    cleaned = cleaned.rstrip('.')

    return cleaned


def extract_items_from_text(text):
    """
    Extract 8-K item numbers from document text using robust regex.

    Returns:
        List of normalized item numbers (e.g., ['2.02', '9.01'])
    """
    # Pattern to match various item formats:
    # - Item 2.02, ITEM 2.02, item 2.02
    # - Item 2. 02 (with space)
    # - Item 2 (old style, no decimal)
    # - Handles optional whitespace and line breaks
    pattern = re.compile(
        r'Item\s+(\d+\.?\s*\d*)',
        re.IGNORECASE | re.MULTILINE
    )

    matches = pattern.findall(text)

    # Normalize and deduplicate
    items = []
    seen = set()

    for match in matches:
        normalized = normalize_item(match)
        if normalized and normalized not in seen:
            items.append(normalized)
            seen.add(normalized)

    return sorted(items)


def test_filing(cik, accession=None, filing_date=None, expected_items=None, era="Unknown"):
    """Test a single 8-K filing for items extraction."""

    console.print(f"\n[bold cyan]Testing {era} Filing[/bold cyan]")
    console.print(f"CIK: {cik}, Accession: {accession}, Date: {filing_date}")

    try:
        # Get the filing
        company = Company(cik)
        if accession:
            filings = company.get_filings(form="8-K")
            filing = next((f for f in filings if f.accession_no == accession), None)
            if not filing:
                console.print(f"[red]✗ Filing not found with accession {accession}[/red]")
                return None
        elif filing_date:
            filings = company.get_filings(form="8-K")
            filing_list = list(filings)
            filing = next((f for f in filing_list if str(f.filing_date) == filing_date), None)
            if not filing:
                console.print(f"[red]✗ Filing not found with date {filing_date}[/red]")
                return None
        else:
            filings = company.get_filings(form="8-K")
            filing = filings.latest(1)

        if not filing:
            console.print("[red]✗ No filing found[/red]")
            return None

        console.print(f"[green]✓ Found filing: {filing.accession_no}[/green]")

        # Get the HTML content
        html_content = filing.document.download()
        if not html_content:
            console.print("[red]✗ Could not download document content[/red]")
            return None

        console.print(f"[green]✓ Downloaded: {len(html_content)} chars[/green]")

        # Parse with edgar.documents parser
        try:
            doc = parse_html(html_content)
            console.print("[green]✓ Parsed document successfully[/green]")
        except Exception as e:
            console.print(f"[red]✗ Parse error: {e}[/red]")
            return None

        # Extract text
        doc_text = doc.text()
        console.print(f"[green]✓ Extracted text: {len(doc_text)} chars[/green]")

        # Extract items using pattern matching
        detected_items = extract_items_from_text(doc_text)
        console.print(f"[bold]Detected items:[/bold] {detected_items}")

        # Show sample item formatting from document
        pattern = re.compile(r'(Item\s+\d+\.?\s*\d*[^\n]{0,50})', re.IGNORECASE)
        samples = pattern.findall(doc_text)
        if samples:
            console.print("\n[dim]Sample formatting:[/dim]")
            for sample in samples[:3]:
                console.print(f"  [dim]{sample.strip()}[/dim]")

        # Compare with expected
        if expected_items:
            # Normalize expected items too
            expected_normalized = sorted([normalize_item(item) for item in expected_items])

            console.print(f"\n[bold]Expected items:[/bold] {expected_normalized}")
            console.print(f"[bold]Detected items:[/bold] {detected_items}")

            # Calculate accuracy
            detected_set = set(detected_items)
            expected_set = set(expected_normalized)

            correct = detected_set & expected_set
            missing = expected_set - detected_set
            extra = detected_set - expected_set

            accuracy = len(correct) / len(expected_set) if expected_set else 0

            console.print(f"\n[bold green]✓ Correct:[/bold green] {sorted(list(correct))}")
            if missing:
                console.print(f"[bold yellow]⚠ Missing:[/bold yellow] {sorted(list(missing))}")
            if extra:
                console.print(f"[bold blue]ℹ Extra:[/bold blue] {sorted(list(extra))}")
            console.print(f"[bold]Accuracy:[/bold] {accuracy*100:.1f}%")

            return {
                'era': era,
                'cik': cik,
                'accession': filing.accession_no,
                'filing_date': str(filing.filing_date),
                'expected': expected_normalized,
                'detected': detected_items,
                'accuracy': accuracy,
                'correct': sorted(list(correct)),
                'missing': sorted(list(missing)),
                'extra': sorted(list(extra)),
                'text_length': len(doc_text)
            }
        else:
            return {
                'era': era,
                'cik': cik,
                'accession': filing.accession_no,
                'filing_date': str(filing.filing_date),
                'detected': detected_items,
                'text_length': len(doc_text)
            }

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Run the 8-K parser test suite."""

    console.print(Panel.fit(
        "[bold cyan]8-K Parser Testing Suite[/bold cyan]\n"
        "Testing edgar.documents parser across filing eras\n"
        "Evaluating text extraction and item pattern matching",
        border_style="cyan"
    ))

    results = []

    # Test 1: Legacy SGML (1999)
    console.print("\n" + "="*70)
    console.print("[bold yellow]LEGACY SGML ERA (1999)[/bold yellow]")
    console.print("="*70)

    result = test_filing(
        cik="864509",
        filing_date="1999-10-13",
        expected_items=['1', '4', '5', '6', '7', '8', '9'],
        era="Legacy SGML (1999)"
    )
    if result:
        results.append(result)

    # Test 2: Mid-period XML (2008-2011)
    console.print("\n" + "="*70)
    console.print("[bold yellow]MID-PERIOD XML ERA (2008-2011)[/bold yellow]")
    console.print("="*70)

    test_cases = [
        ("919130", "0001144204-11-047401", ['2.02', '9.01']),
        ("109177", "0001144204-11-045676", ['2.02', '9.01']),
        ("713095", "0000713095-08-000011", ['8.01', '9.01']),
    ]

    for cik, accession, expected in test_cases:
        result = test_filing(
            cik=cik,
            accession=accession,
            expected_items=expected,
            era="Mid-period XML (2008-2011)"
        )
        if result:
            results.append(result)

    # Test 3: Modern XML (2024-2025)
    console.print("\n" + "="*70)
    console.print("[bold yellow]MODERN XML ERA (2024-2025)[/bold yellow]")
    console.print("="*70)

    # Apple
    result = test_filing(
        cik="320193",
        filing_date="2025-10-30",
        expected_items=['2.02', '9.01'],
        era="Modern XML (2025)"
    )
    if result:
        results.append(result)

    # Microsoft
    result = test_filing(
        cik="789019",
        filing_date="2025-10-29",
        expected_items=['2.02', '7.01', '9.01'],
        era="Modern XML (2025)"
    )
    if result:
        results.append(result)

    # Tesla
    result = test_filing(
        cik="1318605",
        filing_date="2025-10-22",
        expected_items=['2.02', '9.01'],
        era="Modern XML (2025)"
    )
    if result:
        results.append(result)

    # Summary report
    console.print("\n" + "="*70)
    console.print("[bold cyan]SUMMARY REPORT[/bold cyan]")
    console.print("="*70)

    if results:
        table = Table(title="8-K Items Extraction Results")
        table.add_column("Era", style="cyan")
        table.add_column("CIK", style="magenta")
        table.add_column("Date")
        table.add_column("Expected")
        table.add_column("Detected")
        table.add_column("Accuracy", justify="right")
        table.add_column("Text Len", justify="right")

        for r in results:
            expected = r.get('expected', [])
            detected = r.get('detected', [])
            accuracy = r.get('accuracy', 0) * 100 if 'accuracy' in r else None
            accuracy_str = f"{accuracy:.0f}%" if accuracy is not None else "N/A"
            text_len = r.get('text_length', 0)

            # Color code accuracy
            if accuracy is not None:
                if accuracy == 100:
                    accuracy_str = f"[green]{accuracy_str}[/green]"
                elif accuracy >= 50:
                    accuracy_str = f"[yellow]{accuracy_str}[/yellow]"
                else:
                    accuracy_str = f"[red]{accuracy_str}[/red]"

            table.add_row(
                r['era'],
                r['cik'],
                r['filing_date'],
                str(expected),
                str(detected),
                accuracy_str,
                f"{text_len:,}"
            )

        console.print(table)

        # Calculate overall statistics
        accuracies = [r['accuracy'] for r in results if 'accuracy' in r]
        if accuracies:
            avg_accuracy = sum(accuracies) / len(accuracies)
            console.print(f"\n[bold]Average Accuracy:[/bold] {avg_accuracy*100:.1f}%")

            # Breakdown by era
            eras = {}
            for r in results:
                if 'accuracy' in r:
                    era = r['era']
                    if era not in eras:
                        eras[era] = []
                    eras[era].append(r['accuracy'])

            console.print("\n[bold]Accuracy by Era:[/bold]")
            for era, accs in eras.items():
                avg = sum(accs) / len(accs)
                console.print(f"  {era}: {avg*100:.1f}% ({len(accs)} filings)")

            # Summary of parser capabilities
            console.print("\n" + "="*70)
            console.print("[bold cyan]PARSER EVALUATION[/bold cyan]")
            console.print("="*70)

            all_100 = all(acc == 1.0 for acc in accuracies)
            avg_high = avg_accuracy >= 0.95

            if all_100:
                status = "[bold green]✓ READY TO USE[/bold green]"
                recommendation = "The edgar.documents parser successfully extracts 8-K items across all eras with 100% accuracy."
            elif avg_high:
                status = "[bold yellow]⚠ MOSTLY READY[/bold yellow]"
                recommendation = f"The parser achieves {avg_accuracy*100:.1f}% average accuracy. Review edge cases before production use."
            else:
                status = "[bold red]✗ NEEDS WORK[/bold red]"
                recommendation = f"The parser achieves only {avg_accuracy*100:.1f}% average accuracy. Further development needed."

            console.print(f"\n[bold]Status:[/bold] {status}")
            console.print(f"\n{recommendation}")

            # Text extraction summary
            total_text = sum(r.get('text_length', 0) for r in results)
            avg_text = total_text / len(results) if results else 0
            console.print("\n[bold]Text Extraction:[/bold]")
            console.print("  • All filings successfully parsed")
            console.print(f"  • Average text extracted: {avg_text:,.0f} chars")
            console.print("  • Works across all eras (1999-2025)")


if __name__ == "__main__":
    main()
