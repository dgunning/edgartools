"""
Simulate the corrupted cache file issue for GitHub issue #443

This script creates the conditions that cause the JSONDecodeError by
creating a corrupted submissions cache file.
"""

from edgar import find, set_identity
from edgar.storage import get_edgar_data_directory, use_local_storage
import json
import traceback
from pathlib import Path

def simulate_corruption():
    """Simulate a corrupted submissions cache file"""

    print("=== Issue #443 Corruption Simulation ===")

    # Enable local storage so we can manipulate cache files
    use_local_storage(True)

    # Get the filing to extract its CIK
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

    # Now try to trigger the error
    try:
        print("Attempting to trigger the JSONDecodeError...")
        related = filing.related_filings()
        print(f"❌ Expected error but got {len(related) if related else 0} related filings")
        return False
    except json.JSONDecodeError as e:
        print(f"✓ Successfully reproduced JSONDecodeError: {e}")
        return True
    except Exception as e:
        print(f"❌ Got unexpected error: {e}")
        traceback.print_exc()
        return False

def cleanup_corruption():
    """Clean up the corrupted file"""
    filing = find("0001949846-25-000489")
    cik = filing.cik

    data_dir = get_edgar_data_directory()
    submissions_dir = data_dir / "submissions"
    submissions_file = submissions_dir / f"CIK{cik:010}.json"

    if submissions_file.exists():
        submissions_file.unlink()
        print(f"Cleaned up corrupted file: {submissions_file}")

if __name__ == "__main__":
    try:
        # Simulate the corruption
        reproduced = simulate_corruption()

        print(f"\n=== Simulation Results ===")
        print(f"JSONDecodeError reproduced: {'YES' if reproduced else 'NO'}")

    finally:
        # Always clean up
        cleanup_corruption()