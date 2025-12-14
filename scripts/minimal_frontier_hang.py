"""
Minimal reproduction of HTMLParser hanging on Frontier Masters 10-K.

This is the simplest possible script to reproduce the hang.
Press Ctrl+C to interrupt if it hangs.

Usage:
    hatch run python scripts/minimal_frontier_hang.py
"""
from edgar import Filing
from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig

print("Downloading Frontier Masters 10-K...")
filing = Filing(
    form='10-K',
    filing_date='2023-04-06',
    company='Frontier Masters Fund',
    cik=1450722,
    accession_no='0001213900-23-028058'
)

html = filing.html()
print(f"HTML size: {len(html):,} bytes")

print("\nParsing with HTMLParser (may hang)...")
config = ParserConfig(form='10-K')
parser = HTMLParser(config)

# This is where it hangs
doc = parser.parse(html)

print("✓ Parsing complete!")
print(f"Document: {type(doc)}")
if doc and hasattr(doc, 'sections'):
    print(f"Sections: {len(doc.sections)}")
