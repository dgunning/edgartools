"""
Debug Cross Reference Index detection for Henry Schein 10-K.
"""
from edgar import Company
from edgar.documents import CrossReferenceIndex

# Get Henry Schein 2024 10-K
company = Company("1000228")  # HENRY SCHEIN INC
filing = company.get_filings(form="10-K", filing_date="2024-01-01:").latest(1)

print(f"Company: {company.name}")
print(f"Filing: {filing}")
print(f"Filing date: {filing.filing_date}")

# Get HTML
html = filing.html()
print(f"\nHTML size: {len(html):,} bytes")

# Check if Cross Reference Index is detected
index = CrossReferenceIndex(html)
print(f"\nCross Reference Index detected: {index.has_index()}")

if index.has_index():
    print("Cross Reference Index IS detected")

    # Try to extract Item 1
    item1 = index.extract_item_content("1")
    print("\nItem 1 extracted via Cross Reference Index:")
    print(f"  Length: {len(item1) if item1 else 0}")
    if item1:
        print(f"  First 200 chars: {item1[:200]}")
else:
    print("Cross Reference Index NOT detected")
    print("\nSearching for 'cross reference' in HTML...")
    if 'cross reference' in html.lower():
        print("  Found 'cross reference' in HTML!")
        # Find context
        import re
        matches = re.finditer(r'.{0,100}cross reference.{0,100}', html, re.IGNORECASE)
        for i, match in enumerate(list(matches)[:3]):
            print(f"\n  Match {i+1}: {match.group()}")
    else:
        print("  'cross reference' NOT found in HTML")
