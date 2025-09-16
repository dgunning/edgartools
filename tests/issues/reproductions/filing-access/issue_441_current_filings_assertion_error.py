"""
Reproduction test for Issue #441: Assertion error in CurrentFilings pagination

The issue occurs when iterating through current filings with pagination.
The assertion "assert item is not None" fails in CurrentFilings.__getitem__
when get() returns None for certain index lookups during iteration.

Error trace:
- edgar/_filings.py line 717: filing: Filing = self[self.n]
- edgar/current_filings.py line 174: assert item is not None

User's code pattern that triggers the issue:
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

import pytest
from edgar.current_filings import get_current_filings


def test_current_filings_pagination_assertion_error():
    """
    Test reproduces the assertion error that occurs during CurrentFilings pagination.

    The issue happens when:
    1. Getting current filings with a specific page size
    2. Iterating through the filings (which calls __next__ -> __getitem__)
    3. The get() method returns None for certain indices
    4. The assertion in __getitem__ fails
    """
    print("Testing CurrentFilings pagination assertion error reproduction...")

    # Get current filings - using small page size to trigger pagination sooner
    current_filings = get_current_filings(page_size=10)

    # This is the user's pattern that should work but triggers assertion error
    all_current = []
    iteration_count = 0

    try:
        while current_filings is not None and iteration_count < 3:  # Limit iterations for test
            print(f"Processing page {iteration_count + 1}, found {len(current_filings)} filings")

            # This iteration should not fail with AssertionError
            for i, filing in enumerate(current_filings):
                print(f"  Filing {i}: {filing.form} - {filing.company} - {filing.filing_date}")
                all_current.append(filing)

            # Move to next page
            current_filings = current_filings.next()
            iteration_count += 1

    except AssertionError as e:
        print(f"AssertionError occurred during pagination: {e}")
        print(f"Total filings processed before error: {len(all_current)}")
        raise

    print(f"Successfully processed {len(all_current)} current filings across {iteration_count} pages")
    return all_current


def test_current_filings_individual_indexing():
    """
    Test individual indexing behavior to understand when get() returns None
    """
    print("Testing CurrentFilings individual indexing behavior...")

    current_filings = get_current_filings(page_size=5)
    print(f"Got {len(current_filings)} filings on current page")

    # Test accessing valid indices
    for i in range(len(current_filings)):
        try:
            filing = current_filings[i]
            print(f"Index {i}: {filing.form} - {filing.company}")
        except AssertionError as e:
            print(f"AssertionError at index {i}: {e}")
            raise

    # Test accessing invalid index (should trigger the bug)
    try:
        invalid_index = len(current_filings) + 10
        filing = current_filings[invalid_index]
        print(f"Unexpectedly got filing at invalid index {invalid_index}: {filing}")
    except AssertionError as e:
        print(f"Expected AssertionError for invalid index {invalid_index}: {e}")
    except IndexError as e:
        print(f"Got IndexError instead of AssertionError for invalid index {invalid_index}: {e}")


if __name__ == "__main__":
    print("=" * 80)
    print("Issue #441 Reproduction: CurrentFilings Assertion Error")
    print("=" * 80)

    try:
        test_current_filings_individual_indexing()
        print("\n" + "=" * 80)
        test_current_filings_pagination_assertion_error()
        print("Reproduction test completed successfully!")
    except Exception as e:
        print(f"Reproduction test failed with: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()