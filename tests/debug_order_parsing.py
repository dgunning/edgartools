"""
Debug script to investigate what attributes are actually in XBRL arc elements
"""

import logging
from edgar import find, Filing

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def debug_order_parsing():
    print("=== Debug Order Parsing ===")

    # Get the AAPL filing
    filing: Filing = find('000032019324000123')
    print(f"Found filing: {filing.form} for {filing.company}")

    # Get XBRL data - this should trigger our debug logging
    print("Loading XBRL data...")
    xbrl = filing.xbrl()
    print("XBRL loaded - check debug logs above for order attribute information")

if __name__ == "__main__":
    debug_order_parsing()