#!/usr/bin/env python3
"""Test script to verify improved current filings display"""

from edgar.current_filings import get_current_filings

def test_current_filings_display():
    print("\n=== Testing Current Filings Display ===\n")
    
    # Get current filings
    filings = get_current_filings(page_size=10)
    
    # Display them using the rich output
    print(filings)
    
    print("\n=== Display Features ===")
    print("✓ Date portion is dimmed (usually same for recent filings)")
    print("✓ Hour is color-coded:")
    print("  - Yellow: 4-5 PM (common filing time)")
    print("  - Bright Red: After hours (6 PM+)")
    print("  - Bright Cyan: Pre-market (before 9 AM)")
    print("  - Bright Green: Regular hours")
    print("✓ Minutes and seconds are emphasized for easy comparison")
    print("✓ Accession numbers show structure with dimmed zeros")

if __name__ == "__main__":
    test_current_filings_display()