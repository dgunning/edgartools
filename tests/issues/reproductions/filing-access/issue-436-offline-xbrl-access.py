#!/usr/bin/env python3
"""
Reproduction script for Issue #436: Offline XBRL Access - SGML Parsing Issue

User reports that even after enabling use_local_storage(True), calling filing.xbrl()
still attempts network requests and fails with ConnectTimeout when offline.

Latest user comment shows the specific stack trace:
filing.xbrl() -> XBRL.from_filing(self) -> XBRLAttachments(filing.attachments)
-> filing.attachments -> self.sgml() -> FilingSGML.from_filing(self)
-> cls.from_source(filing.text_url) -> read_content_as_string(source)
-> stream_with_retry(source) -> Network request

ROOT CAUSE: FilingSGML.from_filing() always uses filing.text_url (network URL)
instead of checking for local storage mode and using local file paths.

Expected behavior: SGML parsing should respect local storage mode and use local files.
Actual behavior: SGML parsing always makes network requests, ignoring local storage.
"""

import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from edgar import set_identity, Company, use_local_storage
from edgar.storage import is_using_local_storage, local_filing_path

def test_offline_xbrl_access():
    """Test reproducing the specific SGML parsing issue in offline mode."""

    # Set proper identity for SEC API (required)
    set_identity("GitHub Issue 436 Reproduction test@example.com")

    print("=== Issue #436 Reproduction: Offline XBRL Access - SGML Parsing Issue ===")
    print()

    # Force enable local storage mode as user did
    print("1. Enabling local storage mode (as user did)...")
    use_local_storage(True)
    using_local = is_using_local_storage()
    print(f"   ✓ Local storage enabled: {using_local}")

    if not using_local:
        print("❌ Failed to enable local storage!")
        return False

    print()
    print("2. Testing XBRL access with Microsoft (MSFT)...")
    print("   This will demonstrate that FilingSGML.from_filing() ignores local storage...")

    try:
        # Get Microsoft company
        company = Company("msft")
        print(f"   ✓ Company loaded: {company.name}")

        # Get latest 10-K filing
        filing = company.latest("10-K")
        print(f"   ✓ Latest 10-K: {filing.accession_no} from {filing.filing_date}")

        # Show the text_url that will be used (this is the network URL)
        print(f"   📁 Filing text_url: {filing.text_url}")

        # Check if local file exists for this filing
        local_path = local_filing_path(str(filing.filing_date), filing.accession_no)
        local_exists = local_path.exists()
        print(f"   📂 Local file path: {local_path}")
        print(f"   📂 Local file exists: {local_exists}")

        print()
        print("3. The problem: filing.xbrl() will call FilingSGML.from_filing()...")
        print("   which ALWAYS uses filing.text_url instead of checking local storage!")
        print()
        print("   Expected flow: Check local storage -> Use local file if exists")
        print("   Actual flow: Always use filing.text_url -> Network request")
        print()
        print("4. Attempting to access XBRL (this will make network request)...")

        # This is where the issue occurs - FilingSGML.from_filing() makes network request
        xbrl = filing.xbrl()

        if xbrl:
            print("   ✅ XBRL loaded successfully (network was available)")
            return True
        else:
            print("   ❌ XBRL is None - no XBRL data found")
            return False

    except Exception as e:
        print(f"   ❌ Error accessing XBRL: {type(e).__name__}: {e}")

        # Check if this is the expected network timeout error from user's report
        if any(error_type in str(e) for error_type in [
            "ConnectTimeout", "handshake operation timed out",
            "_ssl.c:975", "Connection refused"
        ]):
            print()
            print("🎯 ISSUE CONFIRMED - This matches the user's error!")
            print()
            print("📋 EXECUTION PATH THAT FAILED:")
            print("   1. filing.xbrl()")
            print("   2. -> XBRL.from_filing(self)")
            print("   3. -> XBRLAttachments(filing.attachments)")
            print("   4. -> filing.attachments")
            print("   5. -> self.sgml()")
            print("   6. -> FilingSGML.from_filing(self)")
            print("   7. -> cls.from_source(filing.text_url)  # ⚠️  PROBLEM: Always uses URL")
            print("   8. -> read_content_as_string(source)")
            print("   9. -> read_content(source)")
            print("   10. -> stream_with_retry(source)  # ❌ Network request fails")
            print()
            print("🔧 ROOT CAUSE:")
            print("   FilingSGML.from_filing() at line 449 in sgml/sgml_common.py:")
            print("   filing_sgml = cls.from_source(filing.text_url)")
            print()
            print("   This ALWAYS uses the network URL, never checks local storage!")
            print("   Even when use_local_storage(True) is enabled.")
            print()
            print("💡 SOLUTION:")
            print("   Modify FilingSGML.from_filing() to check local storage first:")
            print("   - If local storage enabled and local file exists -> use local file")
            print("   - Otherwise -> fall back to network URL")
            return False
        else:
            print(f"   ❌ Unexpected error (not the network timeout we expected): {e}")
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