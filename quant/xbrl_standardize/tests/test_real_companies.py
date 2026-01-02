#!/usr/bin/env python3
"""
Test apply_mappings with real company data from Edgar.

Tests extraction quality across different sectors with actual XBRL filings.

Usage:
    python test_real_companies.py
"""

from edgar import Company
from apply_mappings import (
    extract_income_statement,
    extract_with_auto_sector,
    validate_extraction
)


# Test companies across sectors
TEST_COMPANIES = [
    # Tech
    ('AAPL', None, 'Apple - Tech'),
    ('MSFT', None, 'Microsoft - Tech'),

    # Banking
    ('JPM', 'banking', 'JP Morgan - Banking'),
    ('BAC', 'banking', 'Bank of America - Banking'),

    # Insurance
    ('PGR', 'insurance', 'Progressive - Insurance'),
    ('ALL', 'insurance', 'Allstate - Insurance'),

    # Utilities
    ('NEE', 'utilities', 'NextEra Energy - Utilities'),
    ('DUK', 'utilities', 'Duke Energy - Utilities'),
]


def extract_company_facts(ticker: str, form: str = '10-K', limit: int = 1):
    """
    Extract XBRL facts from latest filing for a company.

    Args:
        ticker: Company ticker
        form: Filing form type
        limit: Number of filings to try

    Returns:
        Dictionary of XBRL facts or None
    """
    try:
        company = Company(ticker)
        filings = company.get_filings(form=form).latest(limit)

        if not filings:
            print(f"    No {form} filings found for {ticker}")
            return None

        filing = filings[0]
        print(f"    Filing: {filing.form} filed {filing.filing_date}")

        # Get XBRL
        xbrl = filing.xbrl()
        if not xbrl:
            print(f"    No XBRL data available")
            return None

        # Get income statement facts
        facts_dict = {}

        # Try to get facts from financials
        if hasattr(xbrl, 'financials'):
            financials = xbrl.financials
            if hasattr(financials, 'income_statement'):
                income_stmt = financials.income_statement
                if income_stmt is not None:
                    # Extract facts from income statement
                    for fact in income_stmt.facts:
                        concept = fact.concept
                        # Get latest value
                        if hasattr(fact, 'value') and fact.value is not None:
                            facts_dict[concept] = fact.value

        # Alternative: use facts directly
        if not facts_dict and hasattr(xbrl, 'facts'):
            # Get all facts and filter for income statement related
            income_concepts = [
                'Revenues', 'Revenue', 'CostOfRevenue', 'GrossProfit',
                'OperatingIncome', 'NetIncome', 'EarningsPerShare'
            ]

            for fact in xbrl.facts:
                concept = fact.concept
                # Check if it's an income statement concept
                if any(ic in concept for ic in income_concepts):
                    if hasattr(fact, 'value') and fact.value is not None:
                        facts_dict[concept] = fact.value

        if not facts_dict:
            print(f"    No income statement facts extracted")
            return None

        print(f"    Extracted {len(facts_dict)} facts from XBRL")
        return facts_dict

    except Exception as e:
        print(f"    Error extracting facts: {e}")
        return None


def test_company(ticker: str, sector: str, description: str):
    """
    Test mapping extraction for a single company.

    Args:
        ticker: Company ticker
        sector: Expected sector or None
        description: Test description
    """
    print(f"\n{'='*70}")
    print(f"Testing: {description}")
    print(f"{'='*70}")

    # Extract facts from latest 10-K
    facts = extract_company_facts(ticker)

    if not facts:
        print(f"  ⚠️  Could not extract facts from {ticker}")
        return None

    # Test extraction with specified sector
    result = extract_income_statement(facts, sector=sector)

    print(f"\nExtraction Results:")
    print(f"  Sector: {result['sector'] or 'core'}")
    print(f"  Fields extracted: {result['fields_extracted']}/{result['fields_total']}")

    # Validate
    validation = validate_extraction(result, required_fields=['revenue', 'netIncome'])
    print(f"  Validation: {'✓ PASS' if validation['valid'] else '✗ FAIL'}")
    print(f"  Extraction rate: {validation['extraction_rate']:.1%}")

    if validation['missing_required']:
        print(f"  Missing required: {', '.join(validation['missing_required'])}")

    if validation['low_confidence_fields']:
        print(f"  Low confidence: {', '.join(validation['low_confidence_fields'])}")

    # Show sample extracted fields
    print(f"\nSample Extracted Fields:")
    sample_fields = ['revenue', 'netIncome', 'operatingIncome', 'earningsPerShareBasic']
    for field in sample_fields:
        if field in result['data']:
            value = result['data'][field]
            concept = result['metadata'][field]['concept']
            confidence = result['metadata'][field]['confidence']
            print(f"  {field}: {value:,.2f} (from {concept}, {confidence})")

    return {
        'ticker': ticker,
        'description': description,
        'extracted': result['fields_extracted'],
        'total': result['fields_total'],
        'rate': validation['extraction_rate'],
        'valid': validation['valid']
    }


def test_auto_sector_detection():
    """Test automatic sector detection with real companies."""
    print(f"\n{'='*70}")
    print("Testing: Auto Sector Detection")
    print(f"{'='*70}")

    test_cases = [
        ('JPM', 'banking'),
        ('PGR', 'insurance'),
        ('NEE', 'utilities')
    ]

    results = []

    for ticker, expected_sector in test_cases:
        print(f"\n  Testing {ticker} (expected: {expected_sector})...")

        # Get company SIC
        try:
            company = Company(ticker)
            sic = company.sic_code if hasattr(company, 'sic_code') else None
            print(f"    SIC: {sic}")

            # Extract facts
            facts = extract_company_facts(ticker)
            if not facts:
                continue

            # Extract with auto-detection
            result = extract_with_auto_sector(facts, sic=sic)
            detected_sector = result.get('sector')
            auto_detected = result.get('sector_auto_detected', False)

            match = detected_sector == expected_sector
            print(f"    Detected: {detected_sector} ({'✓' if match else '✗'})")
            print(f"    Auto-detected: {auto_detected}")

            results.append(match)

        except Exception as e:
            print(f"    Error: {e}")
            results.append(False)

    success_rate = sum(results) / len(results) if results else 0
    print(f"\nAuto-detection accuracy: {success_rate:.1%}")
    return success_rate >= 0.5


def run_real_company_tests():
    """Run tests with real company data."""
    print("\n" + "="*70)
    print("REAL COMPANY VALIDATION TESTS")
    print("="*70)
    print("\nNote: These tests require network access to Edgar.")
    print("Tests may be slow due to SEC rate limiting.")

    results = []

    # Test each company
    for ticker, sector, description in TEST_COMPANIES:
        try:
            result = test_company(ticker, sector, description)
            if result:
                results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")

    # Test auto-detection
    print("\n")
    auto_detect_passed = test_auto_sector_detection()

    # Summary
    print("\n" + "="*70)
    print("REAL COMPANY TEST SUMMARY")
    print("="*70)

    if not results:
        print("\n⚠️  No results - tests may have failed to fetch data")
        return 1

    print(f"\n{'Company':<30} {'Extracted':<15} {'Rate':<12} {'Valid':<12}")
    print("-" * 70)

    for result in results:
        print(f"{result['description']:<30} "
              f"{result['extracted']}/{result['total']:<13} "
              f"{result['rate']:<11.1%} "
              f"{'✓' if result['valid'] else '✗':<12}")

    # Overall metrics
    avg_rate = sum(r['rate'] for r in results) / len(results)
    valid_count = sum(1 for r in results if r['valid'])

    print(f"\n{'='*70}")
    print(f"Average extraction rate: {avg_rate:.1%}")
    print(f"Validations passed: {valid_count}/{len(results)}")
    print(f"Auto-detection test: {'PASS' if auto_detect_passed else 'FAIL'}")
    print(f"{'='*70}")

    # Success criteria
    success = (
        avg_rate >= 0.30 and  # At least 30% average extraction
        valid_count >= len(results) * 0.75 and  # At least 75% valid
        auto_detect_passed  # Auto-detection works
    )

    if success:
        print("\n✅ Real company validation PASSED!")
        print("   Mappings work correctly with production Edgar data.")
        return 0
    else:
        print("\n⚠️  Some tests did not meet success criteria.")
        print("   Review results above for details.")
        return 1


if __name__ == '__main__':
    import sys

    print("\n⚠️  WARNING: This test requires network access and may be slow.")
    print("It will fetch real filings from SEC Edgar (rate limited).")
    print("\nPress Ctrl+C to cancel, or wait to continue...")

    import time
    time.sleep(3)

    sys.exit(run_real_company_tests())
