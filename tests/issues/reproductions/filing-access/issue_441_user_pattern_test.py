"""
Test the exact user pattern from Issue #441 to ensure it works with the fix.

User's original code:
```python
all_current = []
current_filings = get_latest_filings(page_size=50)
while True:
    for filing in current_filings:
        print(filing.filing_date)
        all_current.append(filing)
    current_filings = current_filings.next()
    if current_filings is None:
        break
```
"""

from edgar import get_latest_filings  # This is an alias for get_current_filings
import pytest

@pytest.mark.regression
@pytest.mark.slow
def test_user_pattern_exact():
    """Test the exact pattern the user reported in Issue #441"""
    print("Testing user's exact code pattern...")

    all_current = []
    current_filings = get_latest_filings(page_size=10)  # Using smaller page size for faster test
    page_count = 0

    while True:
        print(f"Processing page {page_count + 1} with {len(current_filings)} filings...")

        for filing in current_filings:
            print(filing.filing_date)
            all_current.append(filing)

        current_filings = current_filings.next()
        if current_filings is None:
            break

        page_count += 1
        if page_count >= 3:  # Limit to 3 pages for testing
            break

    print(f"Successfully processed {len(all_current)} filings across {page_count + 1} pages")
    return all_current


if __name__ == "__main__":
    print("=" * 80)
    print("Issue #441 User Pattern Test")
    print("=" * 80)

    try:
        filings = test_user_pattern_exact()
        print(f"✅ SUCCESS: User pattern works! Processed {len(filings)} filings.")
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()