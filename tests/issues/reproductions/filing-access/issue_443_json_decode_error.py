"""
Reproduction script for GitHub issue #443: JSONDecodeError when fetching certain filings

Issue: JSONDecodeError occurs when calling filing.related_filings() on filing 0001949846-25-000489
Error occurs in load_company_submissions_from_local when parsing cached submissions file

Expected: Should retrieve filing and related filings without error
Actual: JSONDecodeError - "Expecting value: line 1 column 1 (char 0)"

Root cause investigation needed:
- Check if submissions cache file exists and is valid JSON
- Determine why cache file might be corrupted/empty
- Implement graceful error handling for corrupted cache files
"""

from edgar import find, set_identity
import traceback
import json
from pathlib import Path

def reproduce_issue_443():
    """Reproduce the JSONDecodeError with filing 0001949846-25-000489"""

    print("=== Issue #443 Reproduction ===")
    print("Testing filing: 0001949846-25-000489")

    try:
        # This should work without error
        filing = find("0001949846-25-000489")
        print(f"✓ Successfully found filing: {filing}")

        # This is where the error occurs according to the issue
        print("Attempting to get related filings...")
        related = filing.related_filings()
        print(f"✓ Successfully retrieved {len(related) if related else 0} related filings")

    except json.JSONDecodeError as e:
        print(f"✗ JSONDecodeError occurred: {e}")
        print("Full traceback:")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        print("Full traceback:")
        traceback.print_exc()
        return False

    return True

def investigate_cache_files():
    """Investigate the state of local cache files"""
    print("\n=== Cache Investigation ===")

    try:
        from edgar.entity.submissions import load_company_submissions_from_local
        from edgar.storage import get_edgar_data_directory

        # Get the CIK from the filing accession number
        # We need to extract CIK to check its cache file
        filing = find("0001949846-25-000489")
        cik = filing.cik

        if cik:
            print(f"CIK: {cik}")

            # Get the data directory where submissions are cached
            data_dir = get_edgar_data_directory()
            print(f"Edgar data directory: {data_dir}")

            submissions_dir = data_dir / "submissions"
            print(f"Submissions directory: {submissions_dir}")
            print(f"Submissions directory exists: {submissions_dir.exists()}")

            # Check for the specific submissions file based on the code
            submissions_file = submissions_dir / f"CIK{cik:010}.json"
            print(f"Expected submissions file: {submissions_file}")
            print(f"File exists: {submissions_file.exists()}")

            if submissions_file.exists():
                file_size = submissions_file.stat().st_size
                print(f"File size: {file_size} bytes")

                if file_size < 100:  # Likely corrupted if very small
                    print(f"❌ File is suspiciously small, likely corrupted")
                    content = submissions_file.read_text()
                    print(f"Content preview: '{content[:100]}'")

                    # This is likely the issue - empty or corrupted file
                    return True  # Signal that we found the issue
                else:
                    print(f"✓ File size looks reasonable")

            # Try to load submissions directly to see what happens
            try:
                submissions = load_company_submissions_from_local(cik)
                print(f"✓ Successfully loaded submissions from cache")
            except json.JSONDecodeError as e:
                print(f"✗ JSONDecodeError loading submissions: {e}")
                return True  # Signal that we reproduced the issue

    except Exception as e:
        print(f"Error during cache investigation: {e}")
        traceback.print_exc()

    return False  # No issue found

if __name__ == "__main__":

    # Reproduce the issue
    success = reproduce_issue_443()

    # Investigate cache files regardless of success/failure
    cache_issue_found = investigate_cache_files()

    print(f"\n=== Summary ===")
    print(f"Issue reproduction: {'PASSED' if success else 'FAILED (reproduced)'}")
    print(f"Cache investigation: {'ISSUE FOUND' if cache_issue_found else 'NO ISSUES'}")