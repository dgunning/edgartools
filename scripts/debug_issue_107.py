"""Debug Issue #107 - Henry Schein item extraction."""
from edgar import Company

print("=" * 80)
print("Debugging Issue #107: Henry Schein 10-K Item Extraction")
print("=" * 80)

company = Company("1000228")  # HENRY SCHEIN INC
filing = company.get_filings(form="10-K", filing_date="2024-01-01:").latest(1)

print(f"\nCompany: {company.name}")
print(f"Filing: {filing.form} filed on {filing.filing_date}")

tenk = filing.obj()
print(f"\nTenK object created: {tenk is not None}")

# Check new parser
print(f"\nNew parser document: {tenk.document is not None}")
if tenk.document:
    print(f"Sections available: {len(tenk.sections)}")
    print(f"Section keys (first 10): {list(tenk.sections.keys())[:10]}")

# Check Cross Reference Index
print(f"\nCross Reference Index detected: {tenk._cross_reference_index is not None}")
if tenk._cross_reference_index:
    print(f"Has index: {tenk._cross_reference_index.has_index()}")

# Check Item 1 extraction
item1 = tenk['Item 1']
print("\nItem 1 extraction:")
print(f"  Length: {len(item1) if item1 else 0} chars")
if item1:
    print(f"  First 200 chars: {repr(item1[:200])}")
    print(f"  Last 200 chars: {repr(item1[-200:])}")

# Try alternative extraction methods
print("\nDirect section lookup:")
if 'business' in tenk.sections:
    business_text = tenk.sections['business'].text()
    print(f"  business section length: {len(business_text)}")
    print(f"  First 200 chars: {repr(business_text[:200])}")

# Try part_i_item_1 format
if 'part_i_item_1' in tenk.sections:
    part_text = tenk.sections['part_i_item_1'].text()
    print(f"  part_i_item_1 length: {len(part_text)}")
    print(f"  First 200 chars: {repr(part_text[:200])}")

# Check if sections have content
print("\nAll sections and their lengths:")
for key in list(tenk.sections.keys())[:15]:
    section = tenk.sections[key]
    text = section.text() if hasattr(section, 'text') else str(section)
    print(f"  {key}: {len(text)} chars")
