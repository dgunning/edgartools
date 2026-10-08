"""
Debug section detection for Frontier Masters 10-K.
"""
from edgar import Filing

# Get Frontier Masters 10-K
filing = Filing(
    form='10-K',
    filing_date='2023-04-06',
    company='Frontier Masters Fund',
    cik=1450722,
    accession_no='0001213900-23-028058'
)

print(f"Company: {filing.company}")
print(f"Filing: {filing.form}")

# Get the TenK object
tenk = filing.obj()

print(f"\nSections detected: {len(tenk.sections)}")

if tenk.sections:
    print("\nAll sections:")
    for name, section in list(tenk.sections.items()):
        text = section.text() if hasattr(section, 'text') else str(section)
        print(f"  {name:40s} {len(text):6,} chars")
else:
    print("\nNo sections detected by new parser")

# Try to get Item 1
print("\n--- Testing Item 1 extraction ---")
item1 = tenk['Item 1']
print(f"Item 1 result: '{item1[:200] if item1 else 'EMPTY/NONE'}'")
print(f"Item 1 length: {len(item1) if item1 else 0}")
