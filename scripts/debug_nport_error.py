"""Debug script to trace the exact error location."""

import traceback

from edgar import Filing
from edgar.documents import HTMLParser, ParserConfig

# Create the filing
filing = Filing(
    form='NPORT-P',
    filing_date='2025-08-27',
    company='PRUDENTIAL SERIES FUND',
    cik=711175,
    accession_no='0001752724-25-208163'
)

print("Getting HTML...")
html = filing.html()
print(f"HTML size: {len(html)} bytes")

print("\nCreating parser...")
config = ParserConfig(form='NPORT-P')
parser = HTMLParser(config)

print(f"Parser strategies: {list(parser.strategies.keys())}")

if 'header_detection' in parser.strategies:
    detector = parser.strategies['header_detection']
    print(f"Header detection strategy type: {type(detector)}")
    print(f"Has is_section_header: {hasattr(detector, 'is_section_header')}")
    print(f"Methods: {[m for m in dir(detector) if not m.startswith('_')]}")

print("\nAttempting to parse...")
try:
    document = parser.parse(html)
    print("✓ SUCCESS!")
except Exception as e:
    print(f"✗ FAILED: {type(e).__name__}: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
