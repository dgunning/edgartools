"""
Test for Issue #523: 13F Other Managers from SummaryPage

Other Managers metadata should be parsed from summaryPage->otherManagers2Info
instead of coverPage (which returns empty list). Also adds sequenceNumber field.

Test cases:
- CIK 70858: With other managers (STATE STREET CORP)
- CIK 7195: Without other managers (ATLANTIC AMERICAN CORP)

See: https://github.com/dgunning/edgartools/issues/523
"""
import pytest

from edgar import Filing


@pytest.mark.network
def test_other_managers_parsed_from_summary_page():
    """Test that other_managers are parsed from summaryPage, not coverPage."""
    # State Street filing with multiple other managers in summaryPage
    # https://www.sec.gov/Archives/edgar/data/70858/000114371824000007/0001143718-24-000007.txt
    filing = Filing(form='13F-HR', filing_date='2024-01-29', company='STATE STREET CORP',
                    cik=70858, accession_no='0001143718-24-000007')

    thirteenf = filing.obj()

    # Verify primary form information exists
    assert thirteenf.primary_form_information is not None, "Should have primary_form_information"

    # Get other_managers from summary_page (the correct location per issue #523)
    summary_page = thirteenf.primary_form_information.summary_page
    assert summary_page is not None, "Should have summary_page"

    other_managers = summary_page.other_managers
    assert other_managers is not None, "summary_page should have other_managers"
    assert isinstance(other_managers, list), "other_managers should be a list"
    assert len(other_managers) > 0, "Should have at least one other manager"

    # Verify manager count matches
    assert summary_page.other_included_managers_count == len(other_managers), \
        "other_included_managers_count should match number of other_managers"


@pytest.mark.network
def test_other_manager_has_sequence_number():
    """Test that OtherManager model has sequenceNumber field (Issue #523)."""
    # State Street filing with multiple other managers
    filing = Filing(form='13F-HR', filing_date='2024-01-29', company='STATE STREET CORP',
                    cik=70858, accession_no='0001143718-24-000007')

    thirteenf = filing.obj()
    other_managers = thirteenf.primary_form_information.summary_page.other_managers

    assert len(other_managers) > 0, "Should have other managers for this test"

    first_manager = other_managers[0]

    # Verify OtherManager has all expected fields including sequence_number
    assert hasattr(first_manager, 'cik'), "Manager should have cik"
    assert hasattr(first_manager, 'name'), "Manager should have name"
    assert hasattr(first_manager, 'file_number'), "Manager should have file_number"
    assert hasattr(first_manager, 'sequence_number'), "Manager should have sequence_number"

    # Verify sequence_number has a value
    assert first_manager.sequence_number is not None, "sequence_number should not be None"
    assert isinstance(first_manager.sequence_number, int), "sequence_number should be an int"
    assert first_manager.sequence_number >= 1, "sequence_number should be >= 1"


# The eight managers declared on the summary page of 0001143718-24-000007,
# in filing order. Sequence numbers are the filer's own and are NOT contiguous
# -- 1,2,3,5,6,28,43,88 -- which is the detail a "not None" check cannot see and
# the one that matters: holdings reference their manager BY sequence number, so
# reading positions as sequence numbers silently reassigns them.
EXPECTED_MANAGERS = [
    (1,  '0001102113', '028-10264', 'BANK OF AMERICA NA'),
    (2,  '0000728612', '028-00962', 'MERRILL LYNCH, PIERCE, FENNER & SMITH INC.'),
    (3,  '0001675365', '028-19575', 'BOFA SECURITIES, INC.'),
    (5,  '0001143718', '028-14408', 'MERRILL LYNCH CANADA, INC.'),
    (6,  '0001062577', '028-07178', 'MERRILL LYNCH INTERNATIONAL'),
    (28, '0001185372', '028-10270', 'U.S. TRUST Co OF DELAWARE'),
    (43, '0001418660', '028-12631', 'MANAGED ACCOUNT ADVISORS LLC'),
    (88, '0001803522', '028-20099', 'BofA Securities Europe SA'),
]


@pytest.mark.network
def test_other_manager_data_correctness():
    """Every field of every manager, against the filing.

    This test is named for data correctness and asserted only non-nullity, over
    a loop that asserted nothing at all when the list came back empty -- which
    is exactly the failure #523 was about. Note also that CIK 70858 is Bank of
    America, not State Street; the accession is what pins the content.
    """
    filing = Filing(form='13F-HR', filing_date='2024-01-29', company='STATE STREET CORP',
                    cik=70858, accession_no='0001143718-24-000007')

    thirteenf = filing.obj()
    other_managers = thirteenf.primary_form_information.summary_page.other_managers

    actual = [(m.sequence_number, m.cik, m.file_number, m.name) for m in other_managers]
    assert actual == EXPECTED_MANAGERS, (
        "summary-page managers do not match the filing.\n"
        f"  expected: {EXPECTED_MANAGERS}\n"
        f"  actual:   {actual}"
    )


@pytest.mark.network
def test_filing_without_other_managers():
    """Test that filings without other managers have empty or None list."""
    # Atlantic American Corp filing - should have no other managers
    # https://www.sec.gov/Archives/edgar/data/7195/000000719525000001/0000007195-25-000001.txt
    filing = Filing(form='13F-HR', filing_date='2025-01-15', company='ATLANTIC AMERICAN CORP',
                    cik=7195, accession_no='0000007195-25-000001')

    thirteenf = filing.obj()

    summary_page = thirteenf.primary_form_information.summary_page

    # Either None or empty list is acceptable for no managers
    other_managers = summary_page.other_managers
    if other_managers is not None:
        assert len(other_managers) == 0, "Should have no other managers"

    # other_included_managers_count should be 0
    assert summary_page.other_included_managers_count == 0, \
        "other_included_managers_count should be 0 for filings without other managers"


@pytest.mark.network
def test_cover_page_other_managers_deprecated():
    """Test that cover_page.other_managers is now empty (moved to summary_page)."""
    # State Street filing with other managers
    filing = Filing(form='13F-HR', filing_date='2024-01-29', company='STATE STREET CORP',
                    cik=70858, accession_no='0001143718-24-000007')

    thirteenf = filing.obj()

    # Cover page should still exist but other_managers should be empty
    cover_page = thirteenf.primary_form_information.cover_page
    assert cover_page is not None, "Should have cover_page"

    # other_managers on cover_page is now deprecated and should be empty
    assert cover_page.other_managers == [], \
        "cover_page.other_managers should be empty (moved to summary_page)"

    # But summary_page should have the actual managers
    summary_page = thirteenf.primary_form_information.summary_page
    assert len(summary_page.other_managers) > 0, \
        "summary_page.other_managers should have the managers"
