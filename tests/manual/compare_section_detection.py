"""
Compare section detection between old (TenK/ChunkedDocument) and new (HybridSectionDetector) parsers.

Downloads HTML fixtures for standard test companies and compares section detection results.

Usage:
    python compare_section_detection.py           # Test all companies
    python compare_section_detection.py AAPL      # Test single company
    python compare_section_detection.py AAPL MSFT # Test multiple companies
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from edgar import Company, set_identity
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig


# Test tickers - expanded to include companies with known issues
TEST_COMPANIES = [
    # Original 6
    ('AAPL', 'Apple Inc.'),
    ('MSFT', 'Microsoft Corp.'),
    ('NVDA', 'NVIDIA Corp.'),
    ('TSLA', 'Tesla Inc.'),
    ('JPM', 'JPMorgan Chase & Co.'),
    ('KO', 'The Coca-Cola Company'),
    ('NFLX', 'Netflix Inc.'),
    # Additional tech companies
    ('GOOGL', 'Alphabet Inc.'),
    ('AMZN', 'Amazon.com Inc.'),
    ('META', 'Meta Platforms Inc.'),
    ('ORCL', 'Oracle Corp.'),
    ('ADBE', 'Adobe Inc.'),
    ('CRM', 'Salesforce Inc.'),
    # Financial sector
    ('MS', 'Morgan Stanley'),  # Known issue with old parser
    ('GS', 'Goldman Sachs'),
    ('BAC', 'Bank of America Corp.'),
    ('C', 'Citigroup Inc.'),
    ('WFC', 'Wells Fargo & Co.'),
    # Healthcare & Pharma
    ('JNJ', 'Johnson & Johnson'),
    ('PFE', 'Pfizer Inc.'),
    ('UNH', 'UnitedHealth Group'),
    ('ABBV', 'AbbVie Inc.'),
    # Retail & Consumer
    ('WMT', 'Walmart Inc.'),
    ('HD', 'The Home Depot Inc.'),
    ('PG', 'Procter & Gamble Co.'),
    ('NKE', 'Nike Inc.'),
    # Industrial & Energy
    ('BA', 'Boeing Co.'),
    ('CAT', 'Caterpillar Inc.'),
    ('XOM', 'Exxon Mobil Corp.'),
    ('CVX', 'Chevron Corp.'),
    # Payment & Finance
    ('V', 'Visa Inc.'),
    ('MA', 'Mastercard Inc.'),
    ('AXP', 'American Express Co.'),
]


# Expected sections for 10-K filings (based on SEC Regulation S-K)
EXPECTED_10K_SECTIONS = {
    # Critical sections - must be present
    'critical': {
        'item 1': 'Business',
        'item 1a': 'Risk Factors',
        'item 7': "Management's Discussion and Analysis",
        'item 7a': 'Quantitative and Qualitative Disclosures About Market Risk',
        'item 8': 'Financial Statements and Supplementary Data',
    },
    # Standard sections - should be present in most filings
    'standard': {
        'item 2': 'Properties',
        'item 3': 'Legal Proceedings',
        'item 5': "Market for Registrant's Common Equity",
        'item 9a': 'Controls and Procedures',
        'item 10': 'Directors, Executive Officers and Corporate Governance',
        'item 11': 'Executive Compensation',
        'item 12': 'Security Ownership of Certain Beneficial Owners and Management',
        'item 13': 'Certain Relationships and Related Transactions',
        'item 14': 'Principal Accountant Fees and Services',
        'item 15': 'Exhibits and Financial Statement Schedules',
    },
    # Optional sections - may or may not be present
    'optional': {
        'item 1b': 'Unresolved Staff Comments',
        'item 1c': 'Cybersecurity',  # New as of 2023
        'item 4': 'Mine Safety Disclosures',
        'item 9': 'Changes in and Disagreements With Accountants',
        'item 9b': 'Other Information',
        'item 9c': 'Disclosure Regarding Foreign Jurisdictions',
        'item 16': 'Form 10-K Summary',
    }
}

# Total expected: 5 critical + 10 standard = 15 core sections
EXPECTED_CORE_COUNT = len(EXPECTED_10K_SECTIONS['critical']) + len(EXPECTED_10K_SECTIONS['standard'])


@dataclass
class SectionComparisonResult:
    """Results from comparing section detection against expected sections and old parser."""
    ticker: str
    company_name: str
    filing_date: str

    # New parser results
    new_sections: Dict[str, float]  # name -> confidence
    avg_confidence: float
    high_confidence_count: int

    # Expected sections analysis (ground truth)
    expected_core: Set[str]  # What we expect to find
    found_critical: Set[str]  # Critical sections found
    found_standard: Set[str]  # Standard sections found
    found_optional: Set[str]  # Optional sections found
    missing_critical: Set[str]  # Critical sections NOT found
    missing_standard: Set[str]  # Standard sections NOT found
    completeness_score: float  # % of core sections found
    critical_score: float  # % of critical sections found

    # Old parser comparison (secondary metric)
    old_sections: Set[str]
    common: Set[str]  # Sections both parsers found
    only_old: Set[str]  # Old found, new missed
    only_new: Set[str]  # New found, old missed
    agreement_rate: float  # % agreement with old parser

    error: Optional[str] = None  # Error message if comparison failed


def normalize_section_name(name: str) -> str:
    """Normalize section name for comparison."""
    normalized = name.lower().strip()
    normalized = normalized.replace('item_', 'item ')
    normalized = normalized.replace('_', ' ')
    normalized = normalized.replace('.', '')
    normalized = normalized.replace('  ', ' ')
    return normalized


def analyze_expected_sections(new_sections: Dict[str, float]) -> Dict:
    """
    Analyze new parser sections against expected 10-K sections.

    Returns dict with:
        - found_critical, found_standard, found_optional: Sets of found sections
        - missing_critical, missing_standard: Sets of missing sections
        - completeness_score: % of core sections found
        - critical_score: % of critical sections found
    """
    # Normalize new sections
    normalized_new = {normalize_section_name(s) for s in new_sections.keys()}

    # Check which expected sections were found
    found_critical = set()
    found_standard = set()
    found_optional = set()

    for section in EXPECTED_10K_SECTIONS['critical']:
        if section in normalized_new:
            found_critical.add(section)

    for section in EXPECTED_10K_SECTIONS['standard']:
        if section in normalized_new:
            found_standard.add(section)

    for section in EXPECTED_10K_SECTIONS['optional']:
        if section in normalized_new:
            found_optional.add(section)

    # Calculate missing sections
    missing_critical = set(EXPECTED_10K_SECTIONS['critical'].keys()) - found_critical
    missing_standard = set(EXPECTED_10K_SECTIONS['standard'].keys()) - found_standard

    # Calculate scores
    found_core = len(found_critical) + len(found_standard)
    completeness_score = found_core / EXPECTED_CORE_COUNT if EXPECTED_CORE_COUNT > 0 else 0

    critical_count = len(EXPECTED_10K_SECTIONS['critical'])
    critical_score = len(found_critical) / critical_count if critical_count > 0 else 0

    return {
        'found_critical': found_critical,
        'found_standard': found_standard,
        'found_optional': found_optional,
        'missing_critical': missing_critical,
        'missing_standard': missing_standard,
        'completeness_score': completeness_score,
        'critical_score': critical_score,
        'expected_core': set(EXPECTED_10K_SECTIONS['critical'].keys()) | set(EXPECTED_10K_SECTIONS['standard'].keys())
    }


def get_old_parser_sections(ticker: str) -> Tuple[Set[str], str]:
    """
    Get sections from old TenK parser.

    Returns:
        Tuple of (section_names, filing_date)
    """
    try:
        company = Company(ticker)
        tenk_filing = company.get_filings(form='10-K', amendments=False).latest()

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
    filing = company.get_filings(form='10-K', amendments=False).latest()

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
    Compare section detection for a company against expected sections and old parser.

    Returns:
        SectionComparisonResult with comprehensive comparison data
    """
    # Get old parser sections
    old_sections, filing_date = get_old_parser_sections(ticker)

    # Download/get HTML
    html_path = download_html_if_needed(ticker)

    # Get new parser sections
    new_sections = get_new_parser_sections(html_path)

    # Analyze against expected sections (primary metric)
    expected_analysis = analyze_expected_sections(new_sections)

    # Calculate new parser metrics
    avg_confidence = sum(new_sections.values()) / len(new_sections) if new_sections else 0
    high_confidence = sum(1 for c in new_sections.values() if c >= 0.8)

    # Normalize for old parser comparison (secondary metric)
    old_normalized = {normalize_section_name(s) for s in old_sections}
    new_normalized = {normalize_section_name(s) for s in new_sections.keys()}

    # Calculate old parser comparison metrics
    common = old_normalized & new_normalized
    only_old = old_normalized - new_normalized
    only_new = new_normalized - old_normalized

    # Agreement rate with old parser
    if old_sections or new_sections:
        union = old_normalized | new_normalized
        agreement_rate = len(common) / len(union) if union else 0
    else:
        agreement_rate = 1.0  # Both found nothing = perfect agreement

    return SectionComparisonResult(
        ticker=ticker,
        company_name=company_name,
        filing_date=filing_date,
        # New parser results
        new_sections=new_sections,
        avg_confidence=avg_confidence,
        high_confidence_count=high_confidence,
        # Expected sections analysis (primary)
        expected_core=expected_analysis['expected_core'],
        found_critical=expected_analysis['found_critical'],
        found_standard=expected_analysis['found_standard'],
        found_optional=expected_analysis['found_optional'],
        missing_critical=expected_analysis['missing_critical'],
        missing_standard=expected_analysis['missing_standard'],
        completeness_score=expected_analysis['completeness_score'],
        critical_score=expected_analysis['critical_score'],
        # Old parser comparison (secondary)
        old_sections=old_sections,
        common=common,
        only_old=only_old,
        only_new=only_new,
        agreement_rate=agreement_rate
    )


def print_comparison_table(results: List[SectionComparisonResult], console: Console):
    """Print comparison results in a table."""
    table = Table(title="Section Detection Analysis: New Parser vs Expected Sections")

    table.add_column("Ticker", style="cyan", width=8)
    table.add_column("Found", justify="right", style="green", width=6)
    table.add_column("Complete", justify="right", style="magenta", width=9)
    table.add_column("Critical", justify="right", style="yellow", width=9)
    table.add_column("Conf", justify="right", style="cyan", width=5)
    table.add_column("Old", justify="right", style="dim", width=5)
    table.add_column("Agree", justify="right", style="dim", width=6)
    table.add_column("Status", style="bold", width=10)

    for result in results:
        new_count = len(result.new_sections)
        completeness = result.completeness_score
        critical = result.critical_score
        old_count = len(result.old_sections)
        agreement = result.agreement_rate

        # Status determination
        if completeness >= 0.85 and critical >= 0.8:
            status = "[green]Excellent[/green]"
            status_emoji = "✓"
        elif completeness >= 0.70 and critical >= 0.6:
            status = "[yellow]Good[/yellow]"
            status_emoji = "⚠"
        else:
            status = "[red]Poor[/red]"
            status_emoji = "✗"

        # Color-code completeness
        if completeness >= 0.85:
            complete_str = f"[green]{completeness:.0%}[/green]"
        elif completeness >= 0.70:
            complete_str = f"[yellow]{completeness:.0%}[/yellow]"
        else:
            complete_str = f"[red]{completeness:.0%}[/red]"

        # Color-code critical
        if critical >= 0.8:
            critical_str = f"[green]{critical:.0%}[/green]"
        elif critical >= 0.6:
            critical_str = f"[yellow]{critical:.0%}[/yellow]"
        else:
            critical_str = f"[red]{critical:.0%}[/red]"

        table.add_row(
            result.ticker,
            str(new_count),
            complete_str,
            critical_str,
            f"{result.avg_confidence:.2f}",
            str(old_count),
            f"{agreement:.0%}",
            f"{status_emoji} {status}"
        )

    console.print(table)
    console.print("\n[dim]Legend: Complete=% of 15 core sections found | Critical=% of 5 critical sections | Agree=agreement with old parser[/dim]")


def print_detailed_results(result: SectionComparisonResult, console: Console):
    """Print detailed results for a single company."""
    console.print(f"\n[bold cyan]{result.ticker} - {result.company_name}[/bold cyan]")

    if result.error:
        console.print(f"[red]Error: {result.error}[/red]")
        return

    console.print(f"Filing Date: {result.filing_date}")

    # Primary metrics: Completeness against expected sections
    console.print(f"\n[bold]Expected Sections Analysis:[/bold]")
    console.print(f"Sections found: {len(result.new_sections)}")
    console.print(f"Completeness: [magenta]{result.completeness_score:.0%}[/magenta] ({len(result.found_critical) + len(result.found_standard)}/{EXPECTED_CORE_COUNT} core sections)")
    console.print(f"Critical sections: [yellow]{result.critical_score:.0%}[/yellow] ({len(result.found_critical)}/{len(EXPECTED_10K_SECTIONS['critical'])})")
    console.print(f"Average confidence: [cyan]{result.avg_confidence:.2f}[/cyan]")

    # Status
    if result.completeness_score >= 0.85 and result.critical_score >= 0.8:
        console.print(f"Status: [green]✓ EXCELLENT[/green]")
    elif result.completeness_score >= 0.70 and result.critical_score >= 0.6:
        console.print(f"Status: [yellow]⚠ GOOD[/yellow]")
    else:
        console.print(f"Status: [red]✗ NEEDS IMPROVEMENT[/red]")

    # Show found sections by category
    if result.found_critical:
        console.print(f"\n[green]✓ Critical sections found ({len(result.found_critical)}/5):[/green]")
        for section in sorted(result.found_critical):
            desc = EXPECTED_10K_SECTIONS['critical'][section]
            console.print(f"  • {section}: {desc}")

    if result.missing_critical:
        console.print(f"\n[red]✗ Critical sections MISSING ({len(result.missing_critical)}):[/red]")
        for section in sorted(result.missing_critical):
            desc = EXPECTED_10K_SECTIONS['critical'][section]
            console.print(f"  ✗ {section}: {desc}")

    if result.found_standard:
        console.print(f"\n[cyan]✓ Standard sections found ({len(result.found_standard)}/10):[/cyan]")
        for section in sorted(result.found_standard):
            desc = EXPECTED_10K_SECTIONS['standard'][section]
            console.print(f"  • {section}: {desc}")

    if result.missing_standard:
        console.print(f"\n[yellow]⚠ Standard sections missing ({len(result.missing_standard)}):[/yellow]")
        for section in sorted(result.missing_standard):
            desc = EXPECTED_10K_SECTIONS['standard'][section]
            console.print(f"  - {section}: {desc}")

    if result.found_optional:
        console.print(f"\n[dim]+ Optional sections found ({len(result.found_optional)}):[/dim]")
        for section in sorted(result.found_optional):
            desc = EXPECTED_10K_SECTIONS['optional'][section]
            console.print(f"  + {section}: {desc}")

    # Secondary: Old parser comparison
    console.print(f"\n[bold]Old Parser Comparison:[/bold]")
    console.print(f"Old parser found: {len(result.old_sections)} sections")
    console.print(f"Agreement rate: [dim]{result.agreement_rate:.0%}[/dim]")

    if result.only_old:
        console.print(f"\n[yellow]Sections old parser found but new missed ({len(result.only_old)}):[/yellow]")
        for name in sorted(result.only_old):
            console.print(f"  - {name}")

    if result.only_new:
        console.print(f"\n[green]Sections new parser found but old missed ({len(result.only_new)}):[/green]")
        for name in sorted(result.only_new):
            console.print(f"  + {name}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Compare section detection between old and new parsers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Test all companies
  %(prog)s AAPL               # Test Apple only
  %(prog)s MS                 # Test Morgan Stanley (known issue with old parser)
  %(prog)s AAPL MSFT TSLA     # Test multiple companies
  %(prog)s --verbose          # Show detailed output for all
        """
    )
    parser.add_argument(
        'tickers',
        nargs='*',
        help='Ticker symbols to test (default: all test companies)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed results for all companies'
    )
    parser.add_argument(
        '--summary-only',
        action='store_true',
        help='Show only summary table, no detailed results'
    )
    return parser.parse_args()


def get_company_name(ticker: str) -> str:
    """Get company name for ticker, either from TEST_COMPANIES or by looking it up."""
    ticker_upper = ticker.upper()
    for test_ticker, name in TEST_COMPANIES:
        if test_ticker == ticker_upper:
            return name

    # Try to get from SEC
    try:
        company = Company(ticker_upper)
        return company.name
    except:
        return f"{ticker_upper} (Unknown Company)"


def main():
    """Run comparison across specified or all test companies."""
    args = parse_args()
    console = Console()

    console.print(Panel.fit(
        "[bold]Section Detection Comparison[/bold]\n"
        "Old Parser (TenK) vs New Parser (HybridSectionDetector)",
        border_style="blue"
    ))


    # Determine which companies to test
    if args.tickers:
        # Use specified tickers
        companies_to_test = [(ticker.upper(), get_company_name(ticker)) for ticker in args.tickers]
        console.print(f"\n[cyan]Testing specified companies: {', '.join(args.tickers)}[/cyan]")
    else:
        # Use all test companies
        companies_to_test = TEST_COMPANIES
        console.print(f"\n[cyan]Testing all {len(TEST_COMPANIES)} companies[/cyan]")

    results = []

    console.print("\n[bold]Downloading and comparing...[/bold]\n")

    for ticker, company_name in companies_to_test:
        console.print(f"Processing {ticker} ({company_name})...", end=" ")
        try:
            result = compare_sections(ticker, company_name)
            results.append(result)

            # Quick status indicator based on completeness
            if result.error:
                console.print("[red]✗ Error[/red]")
            else:
                completeness = result.completeness_score
                if completeness >= 0.85 and result.critical_score >= 0.8:
                    console.print("[green]✓ Excellent[/green]")
                elif completeness >= 0.70:
                    console.print("[yellow]⚠ Good[/yellow]")
                else:
                    console.print("[red]✗ Poor[/red]")

        except Exception as e:
            console.print(f"[red]✗ {e}[/red]")
            # Create error result with empty metrics
            results.append(SectionComparisonResult(
                ticker=ticker,
                company_name=company_name,
                filing_date="",
                new_sections={},
                avg_confidence=0.0,
                high_confidence_count=0,
                expected_core=set(),
                found_critical=set(),
                found_standard=set(),
                found_optional=set(),
                missing_critical=set(),
                missing_standard=set(),
                completeness_score=0.0,
                critical_score=0.0,
                old_sections=set(),
                common=set(),
                only_old=set(),
                only_new=set(),
                agreement_rate=0.0,
                error=str(e)
            ))

    # Print summary table
    console.print("\n")
    print_comparison_table(results, console)

    # Print detailed results (unless summary-only)
    if not args.summary_only:
        console.print("\n[bold]Detailed Results[/bold]")
        console.print("=" * 80)

        for result in results:
            # Show detailed results if verbose, or if single ticker, or if poor performance
            show_detail = (
                args.verbose or
                len(results) == 1 or
                result.completeness_score < 0.80
            )

            if show_detail or result.error:
                print_detailed_results(result, console)
                console.print("\n" + "-" * 80)

    # Print overall statistics
    console.print("\n[bold]Overall Statistics[/bold]")
    console.print("=" * 80)

    valid_results = [r for r in results if not r.error]

    if not valid_results:
        console.print("[red]No valid results to analyze[/red]")
        return

    # Calculate averages based on completeness
    avg_completeness = sum(r.completeness_score for r in valid_results) / len(valid_results)
    avg_critical = sum(r.critical_score for r in valid_results) / len(valid_results)
    avg_confidence = sum(r.avg_confidence for r in valid_results) / len(valid_results)
    avg_agreement = sum(r.agreement_rate for r in valid_results) / len(valid_results)

    # Count companies meeting targets
    excellent_count = sum(1 for r in valid_results
                         if r.completeness_score >= 0.85 and r.critical_score >= 0.8)
    good_or_better = sum(1 for r in valid_results
                        if r.completeness_score >= 0.70)

    console.print(f"Average Completeness: [magenta]{avg_completeness:.0%}[/magenta] (core sections found)")
    console.print(f"Average Critical Score: [yellow]{avg_critical:.0%}[/yellow] (critical sections found)")
    console.print(f"Average Confidence: [cyan]{avg_confidence:.2f}[/cyan]")
    console.print(f"Agreement with old parser: [dim]{avg_agreement:.0%}[/dim]")
    console.print(f"\nCompanies with ≥85% completeness: [green]{excellent_count}/{len(valid_results)}[/green] ({excellent_count/len(valid_results):.0%})")
    console.print(f"Companies with ≥70% completeness: [yellow]{good_or_better}/{len(valid_results)}[/yellow] ({good_or_better/len(valid_results):.0%})")
    console.print(f"Total Companies Tested: {len(results)}")

    # Goal assessment - aligned with goals.md target
    console.print(f"\n[bold]Goal Assessment:[/bold]")
    goal_target = 0.9  # 90% of companies should have >=90% completeness
    companies_meeting_goal = sum(1 for r in valid_results if r.completeness_score >= 0.9)
    goal_percentage = companies_meeting_goal / len(valid_results) if valid_results else 0

    if goal_percentage >= goal_target:
        console.print(f"[green]✓ GOAL MET:[/green] {companies_meeting_goal}/{len(valid_results)} ({goal_percentage:.0%}) companies have ≥90% completeness")
    else:
        shortfall = int(goal_target * len(valid_results)) - companies_meeting_goal
        console.print(f"[yellow]⚠ GOAL IN PROGRESS:[/yellow] {companies_meeting_goal}/{len(valid_results)} ({goal_percentage:.0%}) at ≥90% completeness")
        console.print(f"[cyan]Need {shortfall} more companies to meet 90% target[/cyan]")


if __name__ == '__main__':
    main()
