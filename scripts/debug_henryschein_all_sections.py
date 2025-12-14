"""
Show ALL detected sections for Henry Schein 10-K.
"""
from edgar import Company
from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig

# Get Henry Schein 2024 10-K
company = Company("1000228")  # HENRY SCHEIN INC
filing = company.get_filings(form="10-K", filing_date="2024-01-01:").latest(1)

# Parse with new HTMLParser
html = filing.html()
config = ParserConfig(form='10-K')
parser = HTMLParser(config)
doc = parser.parse(html)

print(f"All {len(doc.sections)} detected sections:\n")
for name, section in doc.sections.items():
    text = section.text() if hasattr(section, 'text') else str(section)
    print(f"{name:30s} {len(text):6,} chars")

print("\n\nLooking for Item 1-related sections:")
for name in doc.sections.keys():
    if 'item_1' in name or 'item1' in name.lower():
        section = doc.sections[name]
        text = section.text() if hasattr(section, 'text') else str(section)
        print(f"\n{name}:")
        print(f"  Length: {len(text):,} chars")
        print(f"  First 300 chars: {text[:300]}")
