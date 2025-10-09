"""
Compare section detection between old (TenK/ChunkedDocument) and new (HybridSectionDetector) parsers.

Downloads HTML fixtures for standard test companies and compares section detection results.
"""

import sys
from pathlib import Path
from typing import Dict, Set, List, Tuple
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from edgar import Company, set_identity
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig


# Test tickers - expanded to 12 companies for comprehensive testing
TEST_COMPANIES = [
    # Original 6
    ('AAPL'
     ''
     '', 'Apple Inc.'),
    ('MSFT', 'Microsoft Corp.'),
    ('NVDA', 'NVIDIA Corp.'),
    ('TSLA', 'Tesla Inc.'),
    ('JPM', 'JPMorgan Chase & Co.'),
    ('KO', 'The Coca-Cola Company'),
    ('NFLX', 'Netflix Inc.'),
    # Additional 6 for broader coverage
    ('GOOGL', 'Alphabet Inc.'),
    ('AMZN', 'Amazon.com Inc.'),
    ('META', 'Meta Platforms Inc.'),
    ('WMT', 'Walmart Inc.'),
    ('JNJ', 'Johnson & Johnson'),
    ('V', 'Visa Inc.'),
]


@dataclass
class SectionComparisonResult:
    """Results from comparing old vs new section detection."""
    ticker: str
    company_name: str
    filing_date: str
    old_sections: Set[str]
    new_sections: Dict[str, float]  # name -> confidence
    common: Set[str]
    only_old: Set[str]
    only_new: Set[str]
    avg_confidence: float
    high_confidence_count: int


def normalize_section_name(name: str) -> str:
    """Normalize section name for comparison."""
    normalized = name.lower().strip()
    normalized = normalized.replace('item_', 'item ')
    normalized = normalized.replace('_', ' ')
    normalized = normalized.replace('.', '')
    normalized = normalized.replace('  ', ' ')
    return normalized


def get_old_parser_sections(ticker: str) -> Tuple[Set[str], str]:
    """
    Get sections from old TenK parser.

    Returns:
        Tuple of (section_names, filing_date)
    """
    try:
        company = Company(ticker)
        tenk_filing = company.get_filings(form='10-K').latest()

        if not tenk_filing:
            return set(), ""

        # Get TenK object
        tenk = tenk_filing.obj()

        sections = set()

        # Try to get sections from old parser
        if hasattr(tenk, 'items'):
            # TenK has .items property that returns sections
            items = tenk.items
            if items:
                sections = set(items.keys() if hasattr(items, 'keys') else items)

        return sections, tenk_filing.filing_date

    except Exception as e:
        print(f"Error getting old parser sections for {ticker}: {e}")
        return set(), ""


def get_new_parser_sections(html_path: Path) -> Dict[str, float]:
    """
    Get sections from new hybrid parser.

    Returns:
        Dict mapping section names to confidence scores
    """
    if not html_path.exists():
        return {}

    html = html_path.read_text()
    config = ParserConfig(filing_type='10-K')
    doc = parse_html(html, config)

    sections = doc.sections

    return {name: section.confidence for name, section in sections.items()}


def download_html_if_needed(ticker: str) -> Path:
    """
    Download HTML for ticker if not already cached.

    Returns:
        Path to HTML file
    """
    base_dir = Path('tests/fixtures/html')
    ticker_dir = base_dir / ticker.lower() / '10k'

    # Check if we already have HTML
    existing = list(ticker_dir.glob('*.html'))
    if existing:
        return existing[0]

    # Download
    print(f"Downloading {ticker} 10-K HTML...")
    company = Company(ticker)
    filing = company.get_filings(form='10-K').latest()

    if not filing:
        raise ValueError(f"No 10-K found for {ticker}")

    html = filing.html()

    # Save
    ticker_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{ticker.lower()}-10-k-{filing.filing_date}.html"
    filepath = ticker_dir / filename
    filepath.write_text(html, encoding='utf-8')

    return filepath


def compare_sections(ticker: str, company_name: str) -> SectionComparisonResult:
    """
    Compare section detection for a company.

    Returns:
        SectionComparisonResult with comparison data
    """
    # Get old parser sections
    old_sections, filing_date = get_old_parser_sections(ticker)

    # Download/get HTML
    html_path = download_html_if_needed(ticker)

    # Get new parser sections
    new_sections = get_new_parser_sections(html_path)

    # Normalize for comparison
    old_normalized = {normalize_section_name(s) for s in old_sections}
    new_normalized = {normalize_section_name(s) for s in new_sections.keys()}

    # Calculate comparison metrics
    common = old_normalized & new_normalized
    only_old = old_normalized - new_normalized
    only_new = new_normalized - old_normalized

    avg_confidence = sum(new_sections.values()) / len(new_sections) if new_sections else 0
    high_confidence = sum(1 for c in new_sections.values() if c >= 0.8)

    return SectionComparisonResult(
        ticker=ticker,
        company_name=company_name,
        filing_date=filing_date,
        old_sections=old_sections,
        new_sections=new_sections,
        common=common,
        only_old=only_old,
        only_new=only_new,
        avg_confidence=avg_confidence,
        high_confidence_count=high_confidence
    )


def print_comparison_table(results: List[SectionComparisonResult], console: Console):
    """Print comparison results in a table."""
    table = Table(title="Section Detection Comparison: Old vs New Parser")

    table.add_column("Ticker", style="cyan", width=8)
    table.add_column("Old", justify="right", style="yellow", width=6)
    table.add_column("New", justify="right", style="green", width=6)
    table.add_column("Common", justify="right", style="blue", width=8)
    table.add_column("Recall", justify="right", style="magenta", width=8)
    table.add_column("Precision", justify="right", style="magenta", width=10)
    table.add_column("Avg Conf", justify="right", style="cyan", width=10)
    table.add_column("High Conf", justify="right", style="green", width=10)

    for result in results:
        old_count = len(result.old_sections)
        new_count = len(result.new_sections)
        common_count = len(result.common)

        recall = common_count / old_count if old_count > 0 else 0
        precision = common_count / new_count if new_count > 0 else 0

        table.add_row(
            result.ticker,
            str(old_count),
            str(new_count),
            str(common_count),
            f"{recall:.1%}",
            f"{precision:.1%}",
            f"{result.avg_confidence:.2f}",
            str(result.high_confidence_count)
        )

    console.print(table)


def print_detailed_results(result: SectionComparisonResult, console: Console):
    """Print detailed results for a single company."""
    console.print(f"\n[bold cyan]{result.ticker} - {result.company_name}[/bold cyan]")
    console.print(f"Filing Date: {result.filing_date}")
    console.print(f"Old Parser: {len(result.old_sections)} sections")
    console.print(f"New Parser: {len(result.new_sections)} sections")

    if result.common:
        console.print(f"\n[green]Common sections ({len(result.common)}):[/green]")
        for name in sorted(result.common):
            console.print(f"  ✓ {name}")

    if result.only_old:
        console.print(f"\n[yellow]Only in old parser ({len(result.only_old)}):[/yellow]")
        for name in sorted(result.only_old):
            console.print(f"  - {name}")

    if result.only_new:
        console.print(f"\n[cyan]Only in new parser ({len(result.only_new)}):[/cyan]")
        for name in sorted(result.only_new):
            # Find original name to show confidence
            for orig_name, conf in result.new_sections.items():
                if normalize_section_name(orig_name) == name:
                    console.print(f"  + {name} (confidence: {conf:.2f})")
                    break


def main():
    """Run comparison across all test companies."""
    console = Console()

    console.print(Panel.fit(
        "[bold]Section Detection Comparison[/bold]\n"
        "Old Parser (TenK) vs New Parser (HybridSectionDetector)",
        border_style="blue"
    ))

    # Set identity for SEC requests
    try:
        import os
        identity = os.getenv('EDGAR_IDENTITY')
        if identity:
            set_identity(identity)
        else:
            console.print("[yellow]Warning: EDGAR_IDENTITY not set, using generic identity[/yellow]")
            set_identity("Section Detection Test test@example.com")
    except:
        pass

    results = []

    console.print("\n[bold]Downloading and comparing...[/bold]\n")

    for ticker, company_name in TEST_COMPANIES:
        console.print(f"Processing {ticker}...", end=" ")
        try:
            result = compare_sections(ticker, company_name)
            results.append(result)
            console.print("[green]✓[/green]")
        except Exception as e:
            console.print(f"[red]✗ {e}[/red]")

    # Print summary table
    console.print("\n")
    print_comparison_table(results, console)

    # Print detailed results
    console.print("\n[bold]Detailed Results[/bold]")
    console.print("=" * 80)

    for result in results:
        print_detailed_results(result, console)
        console.print("\n" + "-" * 80)

    # Print overall statistics
    console.print("\n[bold]Overall Statistics[/bold]")
    console.print("=" * 80)

    avg_recall = sum(len(r.common) / len(r.old_sections) if r.old_sections else 0
                    for r in results) / len(results)
    avg_precision = sum(len(r.common) / len(r.new_sections) if r.new_sections else 0
                       for r in results) / len(results)
    avg_confidence = sum(r.avg_confidence for r in results) / len(results)

    console.print(f"Average Recall: {avg_recall:.1%}")
    console.print(f"Average Precision: {avg_precision:.1%}")
    console.print(f"Average Confidence: {avg_confidence:.2f}")
    console.print(f"Total Companies Tested: {len(results)}")


if __name__ == '__main__':
    main()
