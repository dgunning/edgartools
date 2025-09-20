"""
Test the fix for GitHub issue #443: JSONDecodeError when fetching certain filings

This script tests the fixed load_company_submissions_from_local function
with corrupted cache files.
"""

from edgar import find, set_identity
from edgar.storage import get_edgar_data_directory, use_local_storage
from edgar.entity.submissions import load_company_submissions_from_local
import json
import traceback
from pathlib import Path

def test_corrupted_cache_fix():
    """Test that the fix handles corrupted cache files gracefully"""

    print("=== Testing Fix for Issue #443 ===")

    # Enable local storage so we can manipulate cache files
    use_local_storage(True)

    # Get a test CIK
    filing = find("0001949846-25-000489")
    cik = filing.cik
    print(f"Testing with CIK: {cik}")

    # Get the submissions directory
    data_dir = get_edgar_data_directory()
    submissions_dir = data_dir / "submissions"
    submissions_dir.mkdir(exist_ok=True)

    # Create the corrupted submissions file
    submissions_file = submissions_dir / f"CIK{cik:010}.json"
    print(f"Creating corrupted file: {submissions_file}")

    # Write empty content to simulate corruption
    submissions_file.write_text("")
    print(f"Created corrupted file with 0 bytes")

    # Test the fixed function directly
    try:
        print("Testing load_company_submissions_from_local function...")
        submissions = load_company_submissions_from_local(cik)

        if submissions:
            print(f"✓ Successfully recovered from corruption. Got submissions data with {len(submissions.get('filings', {}).get('recent', {}).get('accessionNumber', []))} recent filings")
            return True
        else:
            print(f"❌ Function returned None")
            return False

    except json.JSONDecodeError as e:
        print(f"❌ Still getting JSONDecodeError: {e}")
        return False
    except Exception as e:
        print(f"❌ Got unexpected error: {e}")
        traceback.print_exc()
        return False

def test_normal_operation():
    """Test that normal operation still works"""
    print("\n=== Testing Normal Operation ===")

    filing = find("0001949846-25-000489")
    cik = filing.cik

    try:
        # Clear any existing cache file first
        data_dir = get_edgar_data_directory()
        submissions_dir = data_dir / "submissions"
        submissions_file = submissions_dir / f"CIK{cik:010}.json"
        if submissions_file.exists():
            submissions_file.unlink()

        submissions = load_company_submissions_from_local(cik)
        if submissions:
            print(f"✓ Normal operation works. Got {len(submissions.get('filings', {}).get('recent', {}).get('accessionNumber', []))} recent filings")
            return True
        else:
            print(f"❌ Normal operation failed")
            return False
    except Exception as e:
        print(f"❌ Normal operation failed: {e}")
        traceback.print_exc()
        return False

def test_end_to_end():
    """Test the full end-to-end scenario from the original issue"""
    print("\n=== Testing End-to-End Scenario ===")

    # Create corruption
    filing = find("0001949846-25-000489")
    cik = filing.cik

    data_dir = get_edgar_data_directory()
    submissions_dir = data_dir / "submissions"
    submissions_dir.mkdir(exist_ok=True)
    submissions_file = submissions_dir / f"CIK{cik:010}.json"

    # Write corrupted content
    submissions_file.write_text("")

    try:
        # First test the individual steps from the traceback
        print("Testing company.__bool__()...")
        company_exists = bool(filing.company)
        print(f"Company boolean check: {company_exists}")

        print("Testing filing.related_filings()...")
        # This should now work without JSONDecodeError
        related = filing.related_filings()
        print(f"✓ End-to-end test passed. Got {len(related) if related else 0} related filings")
        return True
    except json.JSONDecodeError as e:
        print(f"❌ End-to-end test failed with JSONDecodeError: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ End-to-end test failed with error: {e}")
        traceback.print_exc()
        return False

def cleanup():
    """Clean up test files"""
    filing = find("0001949846-25-000489")
    cik = filing.cik

    data_dir = get_edgar_data_directory()
    submissions_dir = data_dir / "submissions"
    submissions_file = submissions_dir / f"CIK{cik:010}.json"

    if submissions_file.exists():
        submissions_file.unlink()
        print(f"Cleaned up test file: {submissions_file}")

if __name__ == "__main__":
    # Set proper identity for SEC API
    set_identity("Research Team research@edgartools.dev")

    try:
        # Test the fix
        corruption_test_passed = test_corrupted_cache_fix()
        normal_test_passed = test_normal_operation()
        end_to_end_passed = test_end_to_end()

        print(f"\n=== Test Results ===")
        print(f"Corrupted cache fix: {'PASS' if corruption_test_passed else 'FAIL'}")
        print(f"Normal operation: {'PASS' if normal_test_passed else 'FAIL'}")
        print(f"End-to-end scenario: {'PASS' if end_to_end_passed else 'FAIL'}")

        all_passed = corruption_test_passed and normal_test_passed and end_to_end_passed
        print(f"Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")

    finally:
        # Always clean up
        cleanup()