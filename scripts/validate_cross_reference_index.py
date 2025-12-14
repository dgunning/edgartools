"""
Validate Cross Reference Index parser with multiple companies.

Tests Phase 2: Validate parser works across different companies that use
the Cross Reference Index format.
"""

from edgar import Company
from edgar.documents import CrossReferenceIndex


def test_company(ticker: str, company_name: str):
    """Test Cross Reference Index detection and parsing for a company."""
    print(f"\n{'=' * 80}")
    print(f"Testing {company_name} ({ticker})")
    print('=' * 80)

    try:
        # Get latest 10-K
        company = Company(ticker)
        filings = company.get_filings(form='10-K')
        if not filings:
            print(f"❌ No 10-K filings found for {ticker}")
            return False

        filing = filings.latest()
        print(f"\n📄 Filing: {filing.form} filed {filing.filing_date}")
        print(f"   URL: {filing.document.url}")

        # Get HTML
        html = filing.html()
        print(f"   HTML size: {len(html):,} bytes")

        # Test detection
        index = CrossReferenceIndex(html)
        has_index = index.has_index()

        print(f"\n🔍 Cross Reference Index detected: {has_index}")

        if not has_index:
            print("   ℹ️  This company uses standard Item headings, not Cross Reference Index")
            return None  # Neither success nor failure - just different format

        # Parse the index
        entries = index.parse()
        print(f"\n✓ Successfully parsed {len(entries)} index entries")

        # Show first few entries
        print("\n📋 Sample entries:")
        for i, (item_id, entry) in enumerate(list(entries.items())[:5]):
            pages_str = ', '.join(str(p) for p in entry.pages)
            print(f"   Item {item_id:3s}: {entry.item_title:40s} → Pages: {pages_str}")

        # Test specific items
        test_items = ['1', '1A', '7', '8']
        print("\n🧪 Testing specific items:")
        for item_id in test_items:
            entry = index.get_item(item_id)
            if entry:
                pages = ', '.join(str(p) for p in entry.pages)
                print(f"   ✓ Item {item_id:3s}: {entry.item_title:30s} → {pages}")
            else:
                print(f"   - Item {item_id:3s}: Not found")

        # Test page break detection
        page_breaks = index.find_page_breaks()
        print(f"\n📄 Page breaks detected: {len(page_breaks)}")
        if page_breaks:
            print(f"   First few page breaks at positions: {page_breaks[:5]}")

        # Try to extract content for Item 1A (Risk Factors)
        if '1A' in entries:
            print("\n📝 Testing content extraction for Item 1A (Risk Factors):")
            content = index.extract_item_content('1A')
            if content:
                content_preview = content[:200].replace('\n', ' ')
                print(f"   ✓ Extracted {len(content):,} characters")
                print(f"   Preview: {content_preview}...")
            else:
                print("   ⚠️  Content extraction returned empty (page breaks may be unreliable)")

        return True

    except Exception as e:
        print(f"\n❌ Error testing {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Test Cross Reference Index parser with multiple companies."""
    print("Cross Reference Index Parser Validation")
    print("Phase 2: Multi-company testing")

    # Companies to test
    test_cases = [
        # Known to use Cross Reference Index
        ('GE', 'General Electric'),
        ('C', 'Citigroup'),  # GitHub #251

        # Additional large companies that might use this format
        ('BAC', 'Bank of America'),
        ('JPM', 'JPMorgan Chase'),
        ('WFC', 'Wells Fargo'),
        ('MS', 'Morgan Stanley'),
        ('GS', 'Goldman Sachs'),
    ]

    results = {}

    for ticker, name in test_cases:
        result = test_company(ticker, name)
        results[ticker] = result

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    has_index = [t for t, r in results.items() if r is True]
    no_index = [t for t, r in results.items() if r is None]
    errors = [t for t, r in results.items() if r is False]

    print(f"\n✓ Companies with Cross Reference Index: {len(has_index)}")
    if has_index:
        print(f"   {', '.join(has_index)}")

    print(f"\nℹ️  Companies with standard format: {len(no_index)}")
    if no_index:
        print(f"   {', '.join(no_index)}")

    if errors:
        print(f"\n❌ Errors: {len(errors)}")
        print(f"   {', '.join(errors)}")

    print(f"\n📊 Total tested: {len(results)}")
    print(f"   Cross Reference Index format: {len(has_index)}")
    print(f"   Standard format: {len(no_index)}")
    print(f"   Errors: {len(errors)}")


if __name__ == '__main__':
    main()
