#!/usr/bin/env python3
"""
Reproduction script for Issue #436: Offline XBRL Access

User reports that after downloading Edgar data with download_edgar_data(),
calling filing.xbrl() still attempts network requests and fails when offline.

Expected behavior: XBRL should be accessible from locally downloaded data without network requests.
Actual behavior: Network requests are made, causing ConnectTimeout errors when offline.

Root cause investigation:
- XBRL.from_filing() → XBRLAttachments(filing.attachments) → attachment.content
- The attachment.content property triggers downloads even when data exists locally
"""

import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from edgar import set_identity, Company
from edgar.storage import is_using_local_storage

def test_offline_xbrl_access():
    """Test accessing XBRL data when local storage is available."""

    # Set proper identity for SEC API (required)
    set_identity("EdgarTools Test Suite test@edgartools.dev")

    print("=== Issue #436 Reproduction: Offline XBRL Access ===")
    print()

    # Check if we're using local storage
    using_local = is_using_local_storage()
    print(f"Using local storage: {using_local}")

    if not using_local:
        print("⚠️  No local storage detected. This test requires downloaded Edgar data.")
        print("   Run `from edgar import download_edgar_data; download_edgar_data()` first.")
        return False

    print()
    print("📊 Testing XBRL access with Microsoft (MSFT)...")

    try:
        # Get Microsoft company
        company = Company("msft")
        print(f"✓ Company loaded: {company.name}")

        # Get latest 10-K filing
        filing = company.latest("10-K")
        print(f"✓ Latest 10-K: {filing.accession_no} ({filing.filing_date})")

        # Try to access XBRL - this should work offline but currently fails
        print("🔍 Attempting to access XBRL data...")

        # This is where the issue occurs - network requests are made
        xbrl = filing.xbrl()

        if xbrl:
            print(f"✓ XBRL loaded successfully!")
            print(f"  - Facts: {len(xbrl._facts)}")
            print(f"  - Contexts: {len(xbrl.contexts)}")
            print(f"  - Presentation trees: {len(xbrl.presentation_trees)}")

            # Try to get an income statement
            income_stmt = xbrl.get_statement_by_type("IncomeStatement")
            if income_stmt:
                print(f"  - Income statement data: {len(income_stmt.get('data', []))} line items")
            else:
                print("  - No income statement found")

            return True
        else:
            print("❌ XBRL is None - no XBRL data found in filing")
            return False

    except Exception as e:
        print(f"❌ Error accessing XBRL: {type(e).__name__}: {e}")

        # Check if this is the expected network timeout error
        if "ConnectTimeout" in str(e) or "handshake operation timed out" in str(e):
            print()
            print("🎯 ROOT CAUSE IDENTIFIED:")
            print("   - XBRL.from_filing() triggers network requests via attachment.content")
            print("   - This happens even when data should be available locally")
            print("   - XBRLAttachments.__init__ calls attachment.content to check for XBRL data")
            print("   - attachment.content property downloads content even in offline mode")
            return False
        else:
            print(f"❌ Unexpected error: {e}")
            return False

def simulate_offline_mode():
    """Simulate offline mode by temporarily blocking network access."""
    print()
    print("🌐 Testing in simulated offline mode...")
    print("   (This would require network mocking - for now, disconnect network manually)")

if __name__ == "__main__":
    success = test_offline_xbrl_access()

    if not success:
        print()
        print("📝 ISSUE SUMMARY:")
        print("   - User downloads Edgar data with download_edgar_data()")
        print("   - Later tries to access XBRL offline: filing.xbrl()")
        print("   - Network requests are still made, causing timeouts")
        print("   - Expected: Use locally cached XBRL data")
        print("   - Actual: Attempts to download XBRL attachments")

        print()
        print("🔧 SOLUTION NEEDED:")
        print("   - Modify XBRLAttachments to check for local content first")
        print("   - Only trigger downloads if local content is not available")
        print("   - Respect offline/local storage mode consistently")

        sys.exit(1)
    else:
        print()
        print("✅ XBRL access working correctly!")
        sys.exit(0)