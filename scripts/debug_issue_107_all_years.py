"""Debug Issue #107 for all affected years."""
from edgar import Company

company = Company("1000228")  # HENRY SCHEIN INC

years = [
    ("2021-01-01:", "2021"),
    ("2023-01-01:", "2023"),
    ("2024-01-01:", "2024"),
]

print("=" * 80)
print("Testing Henry Schein 10-K Item Extraction Across Multiple Years")
print("=" * 80)

for date_filter, year_label in years:
    print(f"\n{'=' * 80}")
    print(f"Year: {year_label}")
    print(f"Date filter: {date_filter}")
    print("=" * 80)

    filing = company.get_filings(form="10-K", filing_date=date_filter).latest(1)

    if not filing:
        print(f"  ❌ No filing found for {year_label}")
        continue

    print(f"  Filing date: {filing.filing_date}")

    tenk = filing.obj()

    # Check sections
    print(f"  Sections: {len(tenk.sections)}")
    print(f"  Cross Ref Index: {tenk._cross_reference_index is not None}")

    # Test Item 1
    item1 = tenk['Item 1']
    if item1:
        print(f"  ✅ Item 1 length: {len(item1)} chars")
        if len(item1) < 100:
            print(f"     WARNING: Very short! Content: {repr(item1)}")
        else:
            print(f"     First 100 chars: {repr(item1[:100])}")
    else:
        print("  ❌ Item 1 is None!")

    # Test Item 1A
    item1a = tenk['Item 1A']
    if item1a:
        print(f"  ✅ Item 1A length: {len(item1a)} chars")
    else:
        print("  ❌ Item 1A is None!")

    # Test Item 7
    item7 = tenk['Item 7']
    if item7:
        print(f"  ✅ Item 7 length: {len(item7)} chars")
    else:
        print("  ❌ Item 7 is None!")
