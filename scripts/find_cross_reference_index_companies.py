"""
Find companies that use Cross Reference Index format.

Test a broader set of companies to identify which ones use the
Cross Reference Index format vs standard Item headings.
"""

from edgar import Company
from edgar.documents import detect_cross_reference_index


def test_company_format(ticker: str):
    """Quick test if company uses Cross Reference Index format."""
    try:
        company = Company(ticker)
        filings = company.get_filings(form='10-K')
        if not filings:
            return None, "No 10-K filings"

        filing = filings.latest()
        html = filing.html()
        has_index = detect_cross_reference_index(html)

        return has_index, filing.filing_date

    except Exception as e:
        return None, f"Error: {str(e)[:50]}"


def main():
    """Test a large sample of companies."""
    print("Finding companies with Cross Reference Index format\n")

    # Broader sample including:
    # - Large industrials
    # - Large banks
    # - Tech companies
    # - Retail
    # - Healthcare
    # - Energy
    companies = [
        # Industrials (GE is industrial)
        ('GE', 'General Electric'),
        ('BA', 'Boeing'),
        ('HON', 'Honeywell'),
        ('MMM', '3M'),
        ('CAT', 'Caterpillar'),
        ('DE', 'Deere'),
        ('LMT', 'Lockheed Martin'),
        ('RTX', 'Raytheon'),
        ('UNP', 'Union Pacific'),

        # Banks
        ('C', 'Citigroup'),
        ('BAC', 'Bank of America'),
        ('JPM', 'JPMorgan'),
        ('WFC', 'Wells Fargo'),
        ('MS', 'Morgan Stanley'),
        ('GS', 'Goldman Sachs'),

        # Tech
        ('AAPL', 'Apple'),
        ('MSFT', 'Microsoft'),
        ('GOOGL', 'Google'),
        ('META', 'Meta'),
        ('AMZN', 'Amazon'),

        # Retail
        ('WMT', 'Walmart'),
        ('HD', 'Home Depot'),
        ('TGT', 'Target'),
        ('COST', 'Costco'),

        # Healthcare
        ('JNJ', 'Johnson & Johnson'),
        ('PFE', 'Pfizer'),
        ('UNH', 'UnitedHealth'),
        ('CVS', 'CVS Health'),

        # Energy
        ('XOM', 'Exxon'),
        ('CVX', 'Chevron'),
        ('COP', 'ConocoPhillips'),
    ]

    cross_reference_companies = []
    standard_companies = []
    errors = []

    for ticker, name in companies:
        has_index, info = test_company_format(ticker)

        if has_index is True:
            cross_reference_companies.append((ticker, name, info))
            print(f"✓ {ticker:6s} {name:25s} - Cross Reference Index (filed {info})")
        elif has_index is False:
            standard_companies.append((ticker, name, info))
            print(f"  {ticker:6s} {name:25s} - Standard format (filed {info})")
        else:
            errors.append((ticker, name, info))
            print(f"❌ {ticker:6s} {name:25s} - {info}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\n✓ Companies using Cross Reference Index format: {len(cross_reference_companies)}")
    for ticker, name, date in cross_reference_companies:
        print(f"   {ticker:6s} - {name}")

    print(f"\n  Companies using standard format: {len(standard_companies)}")

    if errors:
        print(f"\n❌ Errors: {len(errors)}")
        for ticker, name, error in errors:
            print(f"   {ticker:6s} - {error}")

    print(f"\n📊 Total: {len(companies)} companies tested")
    print(f"   Cross Reference Index: {len(cross_reference_companies)} ({len(cross_reference_companies)/len(companies)*100:.1f}%)")
    print(f"   Standard format: {len(standard_companies)} ({len(standard_companies)/len(companies)*100:.1f}%)")


if __name__ == '__main__':
    main()
