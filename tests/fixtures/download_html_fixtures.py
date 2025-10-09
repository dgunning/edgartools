"""
Download HTML fixtures for test companies.

This script downloads recent 10-K and 10-Q HTML filings for companies
in tests/fixtures/xbrl2/ to augment our HTML parser test corpus.
"""

import sys
from pathlib import Path
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from edgar import Company, set_identity


# Tickers from XBRL test fixtures
TICKERS = [
    'AAPL',   # Apple - Tech
    'MSFT',   # Microsoft - Tech
    'NVDA',   # NVIDIA - Semiconductors
    'TSLA',   # Tesla - Automotive
    'JPM',    # JP Morgan - Finance
    'GS',     # Goldman Sachs - Finance
    'KO',     # Coca-Cola - Consumer goods
    'PG',     # Procter & Gamble - Consumer goods
    'JNJ',    # Johnson & Johnson - Healthcare
    'XOM',    # Exxon Mobil - Energy
    'BA',     # Boeing - Aerospace
    'IBM',    # IBM - Tech
    'UNP',    # Union Pacific - Transportation
    'NFLX',   # Netflix - Media
    'HUBS',   # HubSpot - SaaS
    'GBDC',   # Golub Capital BDC - Finance
]


def download_html_fixtures(
    tickers: List[str],
    forms: List[str] = ['10-K', '10-Q'],
    max_per_form: int = 1
):
    """
    Download HTML fixtures for test companies.

    Args:
        tickers: List of ticker symbols
        forms: Form types to download
        max_per_form: Maximum filings per form type
    """
    base_dir = Path('tests/fixtures/html')
    base_dir.mkdir(exist_ok=True)

    print(f"\n{'='*80}")
    print("DOWNLOADING HTML FIXTURES")
    print(f"{'='*80}\n")
    print(f"Base directory: {base_dir}")
    print(f"Tickers: {len(tickers)}")
    print(f"Forms: {', '.join(forms)}")
    print(f"Max per form: {max_per_form}\n")

    results = {
        'success': [],
        'failed': [],
        'skipped': []
    }

    for ticker in tickers:
        print(f"\n{ticker}:")
        print("-" * 40)

        try:
            # Get company
            company = Company(ticker)
            print(f"  Company: {company.name}")

            # Create ticker directory
            ticker_dir = base_dir / ticker.lower()
            ticker_dir.mkdir(exist_ok=True)

            for form_type in forms:
                print(f"  {form_type}:")

                try:
                    # Get recent filings - use latest() which returns single filing
                    filing = company.get_filings(form=form_type).latest()

                    if not filing:
                        print(f"    ⚠️  No {form_type} filings found")
                        results['skipped'].append(f"{ticker} {form_type}")
                        continue

                    # Process the latest filing
                    filings = [filing]

                    for filing in filings:
                        # Create form directory
                        form_dir = ticker_dir / form_type.lower().replace('-', '')
                        form_dir.mkdir(exist_ok=True)

                        # Filename: {ticker}-{form}-{date}.html
                        filename = f"{ticker.lower()}-{form_type.lower()}-{filing.filing_date}.html"
                        filepath = form_dir / filename

                        # Skip if already exists
                        if filepath.exists():
                            print(f"    ✓ {filename} (cached)")
                            results['success'].append(str(filepath))
                            continue

                        # Download HTML
                        html = filing.html()

                        if not html:
                            print(f"    ✗ {filename} (no HTML)")
                            results['failed'].append(f"{ticker} {form_type} {filing.filing_date}")
                            continue

                        # Save HTML
                        filepath.write_text(html, encoding='utf-8')

                        size_mb = len(html) / (1024 * 1024)
                        print(f"    ✓ {filename} ({size_mb:.1f}MB)")
                        results['success'].append(str(filepath))

                except Exception as e:
                    print(f"    ✗ Error: {e}")
                    results['failed'].append(f"{ticker} {form_type}: {e}")

        except Exception as e:
            print(f"  ✗ Error getting company: {e}")

            results['failed'].append(f"{ticker}: {e}")

    # Print summary
    print(f"\n{'='*80}")
    print("DOWNLOAD SUMMARY")
    print(f"{'='*80}\n")
    print(f"✓ Success: {len(results['success'])} files")
    print(f"✗ Failed:  {len(results['failed'])}")
    print(f"⚠️ Skipped: {len(results['skipped'])}")

    if results['failed']:
        print(f"\nFailed downloads:")
        for item in results['failed']:
            print(f"  - {item}")

    # Print file organization
    print(f"\n{'='*80}")
    print("FILE ORGANIZATION")
    print(f"{'='*80}\n")

    for ticker in tickers:
        ticker_dir = base_dir / ticker.lower()
        if ticker_dir.exists():
            files = list(ticker_dir.rglob('*.html'))
            if files:
                print(f"{ticker}: {len(files)} files")
                for f in sorted(files):
                    rel_path = f.relative_to(base_dir)
                    size_mb = f.stat().st_size / (1024 * 1024)
                    print(f"  {rel_path} ({size_mb:.1f}MB)")

    print(f"\n{'='*80}")
    print(f"Total HTML files: {len(list(base_dir.rglob('*.html')))}")
    print(f"Total size: {sum(f.stat().st_size for f in base_dir.rglob('*.html')) / (1024 * 1024):.1f}MB")
    print(f"{'='*80}\n")


def main():
    """Run the download script."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Download HTML fixtures for test companies'
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        default=TICKERS,
        help='Ticker symbols to download (default: all XBRL fixture tickers)'
    )
    parser.add_argument(
        '--forms',
        nargs='+',
        default=['10-K', '10-Q'],
        help='Form types to download (default: 10-K 10-Q)'
    )
    parser.add_argument(
        '--max-per-form',
        type=int,
        default=1,
        help='Maximum filings per form type (default: 1)'
    )

    args = parser.parse_args()

    download_html_fixtures(
        tickers=args.tickers,
        forms=args.forms,
        max_per_form=args.max_per_form
    )


if __name__ == '__main__':
    main()
