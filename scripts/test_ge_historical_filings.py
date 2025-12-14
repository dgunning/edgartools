"""
Test Cross Reference Index parser with historical GE filings.

Validate that the format is consistent across multiple years.
"""

from edgar import Company
from edgar.documents import CrossReferenceIndex


def test_ge_filing(filing):
    """Test a single GE filing."""
    print(f"\n{'=' * 80}")
    print(f"Filing: {filing.form} filed {filing.filing_date}")
    print(f"URL: {filing.document.url}")
    print('=' * 80)

    try:
        html = filing.html()
        print(f"HTML size: {len(html):,} bytes")

        # Test detection
        index = CrossReferenceIndex(html)
        has_index = index.has_index()

        print(f"\nCross Reference Index detected: {has_index}")

        if not has_index:
            print("❌ No Cross Reference Index found in this filing")
            return False

        # Parse
        entries = index.parse()
        print(f"✓ Parsed {len(entries)} entries")

        # Show sample
        print("\nSample entries:")
        for item_id in ['1', '1A', '1C', '7', '8']:
            entry = index.get_item(item_id)
            if entry:
                pages = ', '.join(str(p) for p in entry.pages)
                print(f"   Item {item_id:3s}: {entry.item_title:40s} → {pages}")

        # Test content extraction
        if '1A' in entries:
            content = index.extract_item_content('1A')
            if content:
                print(f"\n✓ Content extraction: {len(content):,} characters for Item 1A")
            else:
                print("\n⚠️  Content extraction returned empty")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Test GE filings from multiple years."""
    print("Testing Cross Reference Index with historical GE filings")

    company = Company('GE')
    filings = company.get_filings(form='10-K')

    print(f"\nTotal GE 10-K filings available: {len(filings)}")

    # Test the 5 most recent filings
    print("\nTesting 5 most recent 10-K filings:")

    results = []
    count = 0
    for filing in filings:
        if count >= 5:
            break
        result = test_ge_filing(filing)
        results.append((filing.filing_date, result))
        count += 1

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    success_count = sum(1 for _, r in results if r)
    print(f"\nSuccessfully parsed: {success_count}/{len(results)}")

    for date, result in results:
        status = "✓" if result else "❌"
        print(f"   {status} {date}")

    if success_count == len(results):
        print("\n✓ Cross Reference Index format is consistent across all tested filings")
    else:
        print("\n⚠️  Cross Reference Index format varied across filings")


if __name__ == '__main__':
    main()
