"""
Debug script to reproduce HTMLParser hanging issue with Frontier Masters 10-K.

This script isolates the hanging issue when parsing specific 10-K filings with HTMLParser.

Usage:
    hatch run python scripts/debug_frontier_masters_10k_hang.py
"""
import sys
import time

from edgar import Filing

print("=" * 80)
print("Frontier Masters 10-K HTMLParser Hang Reproduction")
print("=" * 80)

# The problematic filing
filing = Filing(
    form='10-K',
    filing_date='2023-04-06',
    company='Frontier Masters Fund',
    cik=1450722,
    accession_no='0001213900-23-028058'
)

print(f"\nFiling: {filing.company}")
print(f"Form: {filing.form}")
print(f"Filing Date: {filing.filing_date}")
print(f"Accession: {filing.accession_no}")

# Step 1: Download HTML
print("\n" + "-" * 80)
print("STEP 1: Downloading HTML from SEC...")
print("-" * 80)
start = time.time()
html = filing.html()
download_time = time.time() - start
print(f"✓ HTML downloaded in {download_time:.2f}s")
print(f"  HTML size: {len(html):,} bytes ({len(html) / 1024 / 1024:.2f} MB)")

# Step 2: Test with ChunkedDocument (old parser)
print("\n" + "-" * 80)
print("STEP 2: Testing with ChunkedDocument (old parser)...")
print("-" * 80)
start = time.time()
try:
    from edgar.files.htmltools import ChunkedDocument
    chunked_doc = ChunkedDocument(html, prefix_src=filing.base_dir)
    old_parser_time = time.time() - start
    print(f"✓ ChunkedDocument created in {old_parser_time:.2f}s")

    # Try to get an item
    start = time.time()
    item1 = chunked_doc['Item 1']
    item_time = time.time() - start
    if item1:
        print(f"✓ Item 1 extracted in {item_time:.2f}s ({len(item1):,} chars)")
    else:
        print("✗ Item 1 not found")
except Exception as e:
    print(f"✗ ChunkedDocument failed: {e}")
    import traceback
    traceback.print_exc()

# Step 3: Test with new HTMLParser
print("\n" + "-" * 80)
print("STEP 3: Testing with HTMLParser (new parser)...")
print("WARNING: This may hang! Press Ctrl+C to interrupt.")
print("-" * 80)

# Set a timeout warning
import signal


def timeout_handler(signum, frame):
    print("\n✗ TIMEOUT: HTMLParser is hanging!")
    print("  The parser has been running for 30+ seconds.")
    sys.exit(1)

# Register the timeout (30 seconds)
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)

start = time.time()
try:
    from edgar.documents import HTMLParser
    from edgar.documents.config import ParserConfig

    print("  Creating ParserConfig(form='10-K')...")
    config = ParserConfig(form='10-K')
    print("  ✓ Config created")

    print("  Creating HTMLParser...")
    parser = HTMLParser(config)
    print("  ✓ Parser created")

    print("  Calling parser.parse(html)...")
    print("  (This is where the hang occurs)")
    doc = parser.parse(html)

    # Cancel the alarm if we get here
    signal.alarm(0)

    new_parser_time = time.time() - start
    print(f"✓ HTMLParser completed in {new_parser_time:.2f}s")

    if doc:
        print(f"  Document type: {type(doc)}")
        print(f"  Has sections: {hasattr(doc, 'sections')}")
        if hasattr(doc, 'sections') and doc.sections:
            print(f"  Number of sections: {len(doc.sections)}")
            print(f"  Section keys: {list(doc.sections.keys())[:10]}")
    else:
        print("  ✗ Document is None")

except KeyboardInterrupt:
    elapsed = time.time() - start
    print(f"\n✗ INTERRUPTED after {elapsed:.2f}s")
    print("  HTMLParser was interrupted (likely hanging)")
    sys.exit(1)
except Exception as e:
    signal.alarm(0)  # Cancel alarm
    elapsed = time.time() - start
    print(f"✗ HTMLParser failed after {elapsed:.2f}s: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("Reproduction complete!")
print("=" * 80)
print("\nSummary:")
print(f"  Old parser (ChunkedDocument): {old_parser_time:.2f}s")
if 'new_parser_time' in locals():
    print(f"  New parser (HTMLParser):      {new_parser_time:.2f}s")
    speedup = old_parser_time / new_parser_time if new_parser_time > 0 else 0
    if speedup > 1:
        print(f"  Speedup: {speedup:.2f}x faster")
    else:
        print(f"  Slowdown: {1/speedup:.2f}x slower")
else:
    print("  New parser (HTMLParser):      HUNG/FAILED")
