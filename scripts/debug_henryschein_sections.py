"""
Debug section detection for Henry Schein 10-K using new HTMLParser.
"""
from edgar import Company
from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig

# Get Henry Schein 2024 10-K
company = Company("1000228")  # HENRY SCHEIN INC
filing = company.get_filings(form="10-K", filing_date="2024-01-01:").latest(1)

print(f"Company: {company.name}")
print(f"Filing: {filing}")
print(f"Filing date: {filing.filing_date}")

# Parse with new HTMLParser
html = filing.html()
print(f"\nHTML size: {len(html):,} bytes")

config = ParserConfig(form='10-K')
parser = HTMLParser(config)
doc = parser.parse(html)

print("\nDocument parsed successfully")
print(f"Sections detected: {len(doc.sections)}")

if doc.sections:
    print("\nDetected sections:")
    for name, section in list(doc.sections.items())[:10]:  # First 10
        text = section.text() if hasattr(section, 'text') else str(section)
        print(f"  {name}: {len(text)} chars - {text[:100]}")
else:
    print("\nNo sections detected by new parser")

# Check if 'business' or 'Item 1' is in sections
print("\n--- Checking specific sections ---")
for key in ['business', 'Item 1', '1', 'item_1']:
    if key in doc.sections:
        section = doc.sections[key]
        text = section.text() if hasattr(section, 'text') else str(section)
        print(f"Found '{key}': {len(text)} chars")
    else:
        print(f"NOT found: '{key}'")

# Also check what chunked_document returns
print("\n--- ChunkedDocument extraction ---")
from edgar.files.htmltools import ChunkedDocument

chunked = ChunkedDocument(html, prefix_src=filing.base_dir)
items = chunked.list_items()
print(f"ChunkedDocument items: {items}")

if 'Item 1' in items:
    item1_chunked = chunked['Item 1']
    print(f"Item 1 from ChunkedDocument: {len(item1_chunked) if item1_chunked else 0} chars")
    if item1_chunked:
        print(f"  Content: {item1_chunked[:200]}")
