"""
Trace HTMLParser execution to identify where it hangs.

This script adds detailed logging to identify the exact step where parsing hangs.

Usage:
    hatch run python scripts/trace_htmlparser_hang.py
"""
import logging
import sys
import time

from edgar import Filing
from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)

# Also enable logging for edgar.documents
logging.getLogger('edgar.documents').setLevel(logging.DEBUG)

print("=" * 80)
print("HTMLParser Execution Trace")
print("=" * 80)

# Create filing
filing = Filing(
    form='10-K',
    filing_date='2023-04-06',
    company='Frontier Masters Fund',
    cik=1450722,
    accession_no='0001213900-23-028058'
)

print(f"\nFiling: {filing.company}")
print("Downloading HTML...")
start = time.time()
html = filing.html()
print(f"HTML downloaded in {time.time() - start:.2f}s ({len(html):,} bytes)\n")

# Monkey-patch to add tracing
original_parse = HTMLParser.parse

def traced_parse(self, html_content):
    """Traced version of HTMLParser.parse()"""
    print("\n[TRACE] Entering HTMLParser.parse()")
    print(f"[TRACE]   HTML size: {len(html_content):,} bytes")
    print(f"[TRACE]   Config form: {self.config.form if hasattr(self, 'config') else 'None'}")

    start = time.time()
    try:
        result = original_parse(self, html_content)
        elapsed = time.time() - start
        print(f"[TRACE] HTMLParser.parse() completed in {elapsed:.2f}s")
        return result
    except Exception as e:
        elapsed = time.time() - start
        print(f"[TRACE] HTMLParser.parse() FAILED after {elapsed:.2f}s: {e}")
        raise

HTMLParser.parse = traced_parse

# Now try parsing
print("Creating parser...")
config = ParserConfig(form='10-K')
parser = HTMLParser(config)

print("\nCalling parser.parse() with tracing enabled...")
print("(Watch for the last trace message before hang)\n")

# Set timeout
import signal


def timeout_handler(signum, frame):
    print("\n" + "=" * 80)
    print("TIMEOUT after 30 seconds!")
    print("=" * 80)
    print("\nThe last trace message above shows where the parser hung.")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)

try:
    start_parse = time.time()
    doc = parser.parse(html)
    signal.alarm(0)

    print(f"\n✓ Parsing complete in {time.time() - start_parse:.2f}s")
    if doc:
        print(f"  Document type: {type(doc)}")
        if hasattr(doc, 'sections'):
            print(f"  Sections: {len(doc.sections)}")
except KeyboardInterrupt:
    print(f"\n✗ Interrupted after {time.time() - start_parse:.2f}s")
    sys.exit(1)
except Exception as e:
    signal.alarm(0)
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
