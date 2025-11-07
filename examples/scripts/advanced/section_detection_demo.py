"""
Section Detection Demo

Demonstrates the hybrid section detection system with confidence scoring.
"""
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig, DetectionThresholds


def demo_basic_detection():
    """Demo 1: Basic section detection with default settings."""
    console = Console()

    console.print("\n[bold cyan]Demo 1: Basic Section Detection[/bold cyan]\n")

    # Use a real 10-K filing
    html_path = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html')
    if not html_path.exists():
        console.print("[yellow]Apple 10-K fixture not found, skipping demo[/yellow]")
        return

    html = html_path.read_text()

    # Parse with default config
    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    # Get sections (triggers hybrid detection)
    sections = doc.sections

    console.print(f"[green]Found {len(sections)} sections[/green]\n")

    # Display sections in a table
    table = Table(title="Detected Sections", show_header=True)
    table.add_column("Section", style="cyan", width=30)
    table.add_column("Confidence", justify="right", style="magenta", width=12)
    table.add_column("Method", style="yellow", width=15)
    table.add_column("Validated", justify="center", style="green", width=10)

    for name, section in list(sections.items())[:10]:  # Show first 10
        confidence_str = f"{section.confidence:.2f}"
        validated_str = "✓" if section.validated else "✗"

        table.add_row(
            section.title,
            confidence_str,
            section.detection_method,
            validated_str
        )

    console.print(table)

    if len(sections) > 10:
        console.print(f"\n[dim]... and {len(sections) - 10} more sections[/dim]")


def demo_custom_thresholds():
    """Demo 2: Custom confidence thresholds."""
    console = Console()

    console.print("\n[bold cyan]Demo 2: Custom Confidence Thresholds[/bold cyan]\n")

    html_path = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html')
    if not html_path.exists():
        console.print("[yellow]Apple 10-K fixture not found, skipping demo[/yellow]")
        return

    html = html_path.read_text()

    # Try different thresholds
    thresholds = [
        ("Low (0.5)", DetectionThresholds(min_confidence=0.5)),
        ("Default (0.6)", DetectionThresholds(min_confidence=0.6)),
        ("High (0.8)", DetectionThresholds(min_confidence=0.8)),
        ("Very High (0.9)", DetectionThresholds(min_confidence=0.9)),
    ]

    table = Table(title="Impact of Confidence Thresholds")
    table.add_column("Threshold", style="cyan")
    table.add_column("Sections Found", justify="right", style="green")
    table.add_column("Avg Confidence", justify="right", style="magenta")

    for name, threshold in thresholds:
        config = ParserConfig(filing_type='10-K', detection_thresholds=threshold)
        doc = parse_html(html, config)
        sections = doc.sections

        avg_confidence = sum(s.confidence for s in sections.values()) / len(sections) if sections else 0

        table.add_row(
            name,
            str(len(sections)),
            f"{avg_confidence:.3f}"
        )

    console.print(table)


def demo_cross_validation():
    """Demo 3: Cross-validation impact."""
    console = Console()

    console.print("\n[bold cyan]Demo 3: Cross-Validation Impact[/bold cyan]\n")

    html_path = Path('tests/fixtures/html/aapl/10k/aapl-10-k-2024-11-01.html')
    if not html_path.exists():
        console.print("[yellow]Apple 10-K fixture not found, skipping demo[/yellow]")
        return

    html = html_path.read_text()

    # Without cross-validation (default)
    config_no_val = ParserConfig(
        filing_type='10-K',
        detection_thresholds=DetectionThresholds(enable_cross_validation=False)
    )
    doc_no_val = parse_html(html, config_no_val)
    sections_no_val = doc_no_val.sections

    # With cross-validation
    config_with_val = ParserConfig(
        filing_type='10-K',
        detection_thresholds=DetectionThresholds(enable_cross_validation=True)
    )
    doc_with_val = parse_html(html, config_with_val)
    sections_with_val = doc_with_val.sections

    # Compare
    console.print(f"Without cross-validation: {len(sections_no_val)} sections")
    console.print(f"With cross-validation: {len(sections_with_val)} sections\n")

    # Show validated sections
    validated_count = sum(1 for s in sections_with_val.values() if s.validated)
    console.print(f"[green]Validated sections: {validated_count}[/green]")


def demo_confidence_filtering():
    """Demo 4: Filtering by confidence."""
    console = Console()

    console.print("\n[bold cyan]Demo 4: Confidence Filtering Example[/bold cyan]\n")

    # Create synthetic HTML with mixed-quality section markers
    html = """<html><body>
        <div id="toc">
            <a href="#item1">Item 1. Business</a>
            <a href="#item2">Item 2. Properties</a>
        </div>

        <h1 id="item1">Item 1. Business</h1>
        <p>Our company operates in the technology sector...</p>

        <h1 id="item2">Item 2. Properties</h1>
        <p>We own and lease various properties...</p>

        <p><b>Item 3. Legal Proceedings</b></p>
        <p>There are no material legal proceedings...</p>
    </body></html>"""

    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)
    sections = doc.sections

    if sections:
        table = Table(title="Section Confidence Scores")
        table.add_column("Section", style="cyan")
        table.add_column("Confidence", justify="right", style="magenta")
        table.add_column("Method", style="yellow")
        table.add_column("Status", style="green")

        for name, section in sections.items():
            status = "✓ High" if section.confidence >= 0.8 else \
                    "~ Medium" if section.confidence >= 0.6 else \
                    "✗ Low"

            table.add_row(
                section.title,
                f"{section.confidence:.2f}",
                section.detection_method,
                status
            )

        console.print(table)
    else:
        console.print("[yellow]No sections detected in synthetic example[/yellow]")


def main():
    """Run all demos."""
    console = Console()

    console.print(Panel.fit(
        "[bold]EdgarTools Section Detection Demo[/bold]\n"
        "Demonstrating hybrid multi-strategy section detection with confidence scoring",
        border_style="blue"
    ))

    demo_basic_detection()
    demo_custom_thresholds()
    demo_cross_validation()
    demo_confidence_filtering()

    console.print("\n[bold green]✓ Demo complete![/bold green]\n")


if __name__ == '__main__':
    main()
