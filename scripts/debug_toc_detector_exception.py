"""
Find the exception that's causing the infinite retry loop in TOC detection.
"""
import logging
import sys

from edgar import Filing
from edgar.documents import HTMLParser
from edgar.documents.config import ParserConfig

# Set up super verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d: %(message)s',
    stream=sys.stdout
)

# Patch Document.sections to catch exceptions
from edgar.documents.document import Document

original_sections = Document.sections.fget

def patched_sections(self):
    """Patched sections property with exception logging."""
    print("\n[PATCH] Document.sections accessed")
    print(f"[PATCH] self._sections is None: {self._sections is None}")

    try:
        result = original_sections(self)
        print(f"[PATCH] sections property returned successfully: {len(result) if result else 0} sections")
        return result
    except Exception as e:
        print(f"[PATCH] EXCEPTION in sections property: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise

Document.sections = property(patched_sections)

# Now try to parse
print("Downloading Frontier Masters 10-K...")
filing = Filing(
    form='10-K',
    filing_date='2023-04-06',
    company='Frontier Masters Fund',
    cik=1450722,
    accession_no='0001213900-23-028058'
)

html = filing.html()
print(f"HTML size: {len(html):,} bytes\n")

print("Parsing with HTMLParser...")
config = ParserConfig(form='10-K')
parser = HTMLParser(config)
doc = parser.parse(html)

print(f"\n✓ Parsing complete, document type: {type(doc)}")

print("\nAccessing doc.sections (with 20s timeout)...")

import signal


def timeout_handler(signum, frame):
    print("\n✗ TIMEOUT after 20 seconds!")
    print("The sections property is likely in an infinite loop/retry.")
    sys.exit(1)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(20)

try:
    sections = doc.sections
    signal.alarm(0)  # Cancel alarm
    print(f"✓ Got sections: {len(sections) if sections else 0}")
except KeyboardInterrupt:
    print("\n✗ Interrupted!")
    sys.exit(1)
except Exception as e:
    signal.alarm(0)  # Cancel alarm
    print(f"\n✗ Exception: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
