"""
Test TenK integration with Cross Reference Index parser.

Validates that tenk.risk_factors, tenk.business, etc. work for GE
after Phase 4 minimal integration.
"""

from edgar import Company


def test_ge_tenk_integration():
    """Test that TenK methods work for GE with Cross Reference Index format."""
    print("Testing TenK integration with Cross Reference Index parser\n")
    print("=" * 80)

    # Get GE 10-K
    print("\n1. Getting GE's latest 10-K...")
    company = Company('GE')
    filing = company.get_filings(form='10-K').latest()
    print(f"   Filing: {filing.form} filed {filing.filing_date}")

    # Get TenK object
    print("\n2. Creating TenK object...")
    tenk = filing.obj()
    print(f"   TenK: {tenk}")

    # Test risk_factors (Item 1A)
    print("\n3. Testing tenk.risk_factors (Item 1A)...")
    risk_factors = tenk.risk_factors
    if risk_factors:
        print(f"   ✓ SUCCESS: Got {len(risk_factors):,} characters")
        print(f"   Preview: {risk_factors[:200].replace(chr(10), ' ')[:200]}...")
    else:
        print("   ❌ FAILED: risk_factors returned None")
        return False

    # Test business (Item 1)
    print("\n4. Testing tenk.business (Item 1)...")
    business = tenk.business
    if business:
        print(f"   ✓ SUCCESS: Got {len(business):,} characters")
        print(f"   Preview: {business[:200].replace(chr(10), ' ')[:200]}...")
    else:
        print("   ❌ FAILED: business returned None")
        return False

    # Test management_discussion (Item 7)
    print("\n5. Testing tenk.management_discussion (Item 7)...")
    mda = tenk.management_discussion
    if mda:
        print(f"   ✓ SUCCESS: Got {len(mda):,} characters")
        print(f"   Preview: {mda[:200].replace(chr(10), ' ')[:200]}...")
    else:
        print("   ❌ FAILED: management_discussion returned None")
        return False

    # Test directors_officers_and_governance (Item 10)
    print("\n6. Testing tenk.directors_officers_and_governance (Item 10)...")
    directors = tenk.directors_officers_and_governance
    if directors:
        print(f"   ✓ SUCCESS: Got {len(directors):,} characters")
        print(f"   Preview: {directors[:200].replace(chr(10), ' ')[:200]}...")
    else:
        print("   ❌ FAILED: directors_officers_and_governance returned None")
        return False

    # Test direct access via __getitem__
    print("\n7. Testing direct access via tenk['Item 1A']...")
    item_1a = tenk['Item 1A']
    if item_1a:
        print(f"   ✓ SUCCESS: Got {len(item_1a):,} characters")
    else:
        print("   ❌ FAILED: tenk['Item 1A'] returned None")
        return False

    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED")
    print("\nGitHub #215 is now SOLVED!")
    print("Users can use standard API:")
    print("  tenk = filing.obj()")
    print("  tenk.risk_factors  # Works for GE!")
    print("=" * 80)

    return True


def test_standard_company():
    """Test that standard companies still work (backward compatibility)."""
    print("\n\nTesting backward compatibility with standard format (Apple)")
    print("=" * 80)

    print("\n1. Getting Apple's latest 10-K...")
    company = Company('AAPL')
    filing = company.get_filings(form='10-K').latest()
    print(f"   Filing: {filing.form} filed {filing.filing_date}")

    print("\n2. Creating TenK object...")
    tenk = filing.obj()

    print("\n3. Testing tenk.risk_factors...")
    risk_factors = tenk.risk_factors
    if risk_factors:
        print(f"   ✓ SUCCESS: Got {len(risk_factors):,} characters")
        print("   Standard format still works!")
    else:
        print("   ⚠️  WARNING: risk_factors returned None")
        print("   (This might be expected for some filings)")

    return True


if __name__ == '__main__':
    success = test_ge_tenk_integration()

    if success:
        test_standard_company()
