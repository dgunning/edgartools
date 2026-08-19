
import datetime

import pytest

from edgar import get_all_current_filings, Filings, iter_current_filings_pages
from edgar import get_by_accession_number
from edgar.current_filings import get_current_filings, CurrentFilings
from edgar.current_filings import parse_title, parse_summary


@pytest.mark.fast
def test_parse_title_simple():
    """Test parsing a simple title without dashes in company name"""
    title = "4 - WILKS LEWIS (0001076463) (Reporting)"
    form, company, cik, status = parse_title(title)

    assert form == "4"
    assert company == "WILKS LEWIS"
    assert cik == "0001076463"
    assert status == "Reporting"


@pytest.mark.fast
def test_parse_title_with_dash_in_company_name():
    """Test parsing title where company name contains a dash - this was the bug"""
    title = "D - Greenbird Intelligence Fund, LLC Series U - Shield Ai (0002093552) (Filer)"
    form, company, cik, status = parse_title(title)

    assert form == "D", f"Expected form 'D' but got '{form}'"
    assert company == "Greenbird Intelligence Fund, LLC Series U - Shield Ai", \
        f"Expected full company name but got '{company}'"
    assert cik == "0002093552"
    assert status == "Filer"


@pytest.mark.fast
def test_parse_title_schedule_form():
    """Test parsing a schedule form with subject status"""
    title = "SCHEDULE 13G/A - Lucent, Inc. (0001726079) (Subject)"
    form, company, cik, status = parse_title(title)

    assert form == "SCHEDULE 13G/A"
    assert company == "Lucent, Inc."
    assert cik == "0001726079"
    assert status == "Subject"


@pytest.mark.fast
def test_parse_title_multiple_dashes_in_company():
    """Test parsing title with multiple dashes in company name"""
    title = "10-K - ABC-DEF Corporation - GHI Division (0001234567) (Filer)"
    form, company, cik, status = parse_title(title)

    assert form == "10-K"
    assert company == "ABC-DEF Corporation - GHI Division"
    assert cik == "0001234567"
    assert status == "Filer"


@pytest.mark.fast
def test_parse_title_filed_by_status():
    """Test parsing with 'Filed by' status"""
    title = "D - Example Company, Inc. - Series A (0009876543) (Filed by)"
    form, company, cik, status = parse_title(title)

    assert form == "D"
    assert company == "Example Company, Inc. - Series A"
    assert cik == "0009876543"
    assert status == "Filed by"


@pytest.mark.fast
def test_parse_title_invalid_format():
    """Test that invalid title format raises ValueError"""
    invalid_title = "Invalid format without proper structure"

    with pytest.raises(ValueError, match="Could not parse title"):
        parse_title(invalid_title)


@pytest.mark.fast
def test_parse_summary_valid():
    """Test parsing a valid summary"""
    summary = "<b>Filed:</b> 2021-09-30 <b>AccNo:</b> 0001845338-21-000002 <b>Size:</b> 1 MB"
    filing_date, accession_no = parse_summary(summary)

    from datetime import date
    assert filing_date == date(2021, 9, 30)
    assert accession_no == "0001845338-21-000002"


@pytest.mark.fast
def test_parse_summary_missing_filed_date():
    """Test that missing Filed date raises ValueError"""
    summary = "<b>AccNo:</b> 0001845338-21-000002 <b>Size:</b> 1 MB"

    with pytest.raises(ValueError, match="Could not find 'Filed' date"):
        parse_summary(summary)


@pytest.mark.fast
def test_parse_summary_missing_accession_number():
    """Test that missing AccNo raises ValueError"""
    summary = "<b>Filed:</b> 2021-09-30 <b>Size:</b> 1 MB"

    with pytest.raises(ValueError, match="Could not find 'AccNo'"):
        parse_summary(summary)


@pytest.mark.fast
def test_parse_summary_invalid_date_format():
    """Test that invalid date format raises ValueError"""
    summary = "<b>Filed:</b> invalid-date <b>AccNo:</b> 0001845338-21-000002 <b>Size:</b> 1 MB"

    with pytest.raises(ValueError, match="Invalid date format"):
        parse_summary(summary)


@pytest.mark.network
def test_get_current_entries():
    filings = get_current_filings()
    # previous should be None
    assert filings.previous() is None

    next_filings = filings.next()
    assert next_filings is not None
    previous_filings = next_filings.previous()
    assert previous_filings.previous() is None

@pytest.mark.network
def test_get_current_filings_by_form():
    form='4'
    filings:CurrentFilings = get_current_filings(form=form)

    # Check that all filings are start with 4. This matches the behavior of the SEC website

    for i in range(4):
        filings = filings.next()
        if not filings:
            break
        assert all(f.startswith(form) for f in set(filings.data['form'].to_pylist()))

@pytest.mark.network
def test_current_filings_to_pandas():
    filings:CurrentFilings = get_current_filings()
    filing_pandas = filings.to_pandas()
    assert filings[0].accession_no == filing_pandas['accession_number'][0]

    # Get the next page
    filings_page2 = filings.next()
    filing_page2_pandas = filings_page2.to_pandas()
    assert filing_page2_pandas is not None


@pytest.mark.network
def test_current_filings_get_by_index_on_page1():
    filings: CurrentFilings = get_current_filings()
    filing = filings.get(20)
    assert filing
    assert filings[20]

    # Find the filing on page2
    filing_page2 = filings.next()
    assert filing_page2

@pytest.mark.network
def test_current_filings_get_by_index_on_page2():
    filings: CurrentFilings = get_current_filings()
    # Find the filing on page2
    filing_page2 = filings.next()
    # Get the first filing on page2 which should be index 40
    filing = filing_page2.get(40)
    # Get the first row of the data
    accession_number = filing_page2.data['accession_number'].to_pylist()[0]
    assert filing
    assert filing.accession_no == accession_number
    assert filing_page2[79]

    with pytest.raises(IndexError):
        # The boundary is 80 - should raise IndexError for out of bounds
        filing_page2[80]

@pytest.mark.network
def test_current_filings_get_accession_number():
    filings:CurrentFilings = get_current_filings()
    filings = filings.next()
    accession_number = filings.data['accession_number'].to_pylist()[0]
    filings = filings.previous()
    filing = filings.get(accession_number)
    assert filing
    assert filing.accession_no == accession_number

@pytest.mark.network
@pytest.mark.slow
@pytest.mark.vcr
def test_current_filings_get_accession_number_not_found():
    filings:CurrentFilings = get_current_filings().next()
    accession_number = '0000000900-24-000000'
    filings = filings.previous()
    filing = filings.get(accession_number)
    assert not filing

@pytest.mark.network
def test_parse_summary():
    summary1 = '<b>Filed:</b> 2023-09-13 <b>AccNo:</b> 0001714174-23-000114 <b>Size:</b> 668 KB'

    filing_date, accession_number = parse_summary(summary1)
    assert (filing_date, accession_number) == (datetime.date(2023, 9, 13), '0001714174-23-000114')

    summary2 = '<b>Film#:</b> 23003229  <b>Filed:</b> 2023-08-17 <b>AccNo:</b> 9999999997-23-004141 <b>Size:</b> 1 KB'
    assert parse_summary(summary2) == (datetime.date(2023, 8, 17), '9999999997-23-004141')

@pytest.mark.network
def test_current_filings_with_no_results():

    filings = get_current_filings(form='4000')
    assert filings.empty
    assert isinstance(filings, CurrentFilings)
    assert filings.start_date is None
    assert filings.end_date is None

@pytest.mark.network
def test_get_current_filing_by_accession_number():
    current_filings = get_current_filings()
    print()
    print(current_filings)
    filing = current_filings[0]
    # Now find the filing
    filing = get_by_accession_number(filing.accession_no)
    assert filing
    assert filing.accession_no == current_filings[0].accession_no

    # Now find a filing that is on the next page
    current_filings = current_filings.next()
    filing_on_next_page = current_filings[40]
    print(filing_on_next_page)

@pytest.mark.network
@pytest.mark.slow
@pytest.mark.vcr
def test_get_all_current_filings():
    all_filings = get_all_current_filings()
    assert isinstance(all_filings, Filings)
    assert len(all_filings) > 100

@pytest.mark.network
def test_iter_current_filings_pages():
    filings = next(iter_current_filings_pages())
    assert filings



@pytest.mark.network
@pytest.mark.slow
@pytest.mark.vcr
def test_get_current_filings_with_page_size_none():
    """Test that page_size=None fetches all current filings"""
    # Get all current filings
    all_filings = get_current_filings(page_size=None)

    # Should return a Filings object (not CurrentFilings)
    assert isinstance(all_filings, Filings)

    # Should have some filings
    assert len(all_filings) > 0

    # Compare with single page to verify we got more
    first_page = get_current_filings(page_size=40)

    # All filings should have at least as many as the first page
    # (could be equal if total filings < 40)
    assert len(all_filings) >= len(first_page)


@pytest.mark.network
def test_get_current_filings_page_size_none_with_form_filter():
    """Test that page_size=None works with form filtering"""
    # Get all current 8-K filings
    all_8k = get_current_filings(form="8-K", page_size=None)

    # Should return a Filings object
    assert isinstance(all_8k, Filings)

    # All filings should be 8-K or 8-K/A (validate ALL, not just some)
    if len(all_8k) > 0:
        # Count non-8-K filings
        non_8k = [f for f in all_8k if f.form not in ["8-K", "8-K/A"]]
        assert len(non_8k) == 0, f"Expected only 8-K filings, but found {len(non_8k)} other forms: {set(f.form for f in non_8k)}"


@pytest.mark.network
def test_get_current_filings_default_behavior_unchanged():
    """Test that default behavior (page_size=40) is unchanged"""
    # Default should still return first page with 40 filings
    current = get_current_filings()

    # Should return CurrentFilings (not Filings)
    from edgar.current_filings import CurrentFilings
    assert isinstance(current, CurrentFilings)

    # Should have at most 40 filings (or less if total < 40)
    assert len(current) <= 40


@pytest.mark.network
@pytest.mark.slow
@pytest.mark.vcr
def test_get_current_filings_form_4_filtering_issue_501():
    """
    Regression test for Issue #501: Form 4 filtering.

    Verifies that get_current_filings(form='4', page_size=None) returns
    ONLY Form 4 and Form 4/A filings, not unfiltered results.

    The SEC API ignores the type parameter, so we apply client-side filtering
    to ensure the form filter works as documented.
    """
    # Get all current Form 4 filings
    all_form4 = get_current_filings(form='4', page_size=None)

    # Should return a Filings object
    assert isinstance(all_form4, Filings)

    # Should have some Form 4 filings
    assert len(all_form4) > 0, "Expected at least some Form 4 filings"

    # ALL results should be Form 4 or 4/A (not other forms)
    non_form4 = [f for f in all_form4 if f.form not in ['4', '4/A']]
    assert len(non_form4) == 0, (
        f"Expected only Form 4 filings, but found {len(non_form4)} other forms "
        f"out of {len(all_form4)} total. "
        f"Other forms found: {set(f.form for f in non_form4)}"
    )


# ---------------------------------------------------------------------------
# Feed parsing (edgartools-07lk.11.3, bs4 -> lxml)
#
# SEC serves this feed as Atom, so every element carries the Atom default
# namespace and a plain `.//entry` matches nothing at all. And a page past the end
# of the feed comes back as HTTP 503 with an HTML error page, which the pagination
# in CurrentFilings relies on yielding zero entries rather than raising. Both
# behaviors came free with bs4's lenient XML parser and have to be asked for
# explicitly now, so both are pinned here.
# ---------------------------------------------------------------------------

ATOM_FEED = b"""<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Latest Filings</title>
<entry>
    <title>4 - WILKS LEWIS (0001076463) (Reporting)</title>
    <summary>&lt;b&gt;Filed:&lt;/b&gt; 2026-08-18 &lt;b&gt;AccNo:&lt;/b&gt; 0001076463-26-000012 &lt;b&gt;Size:&lt;/b&gt; 5 KB</summary>
    <updated>2026-08-18T14:09:29-04:00</updated>
</entry>
</feed>
"""

# The shape of SEC's 503, trimmed.
HTML_ERROR_PAGE = b"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <title>SEC.gov | Request Rate Threshold Exceeded</title>
</head>
<body><h1>Your Request Originates from an Undeclared Automated Tool</h1></body>
</html>
"""


class _Response:
    def __init__(self, content: bytes):
        self.content = content


@pytest.fixture
def _serve_feed(monkeypatch):
    def serve(content: bytes):
        # Imported by path: `edgar.current_filings` is rebound in edgar/__init__.py
        # to the get_current_filings function, so the attribute lookup finds that.
        import importlib
        module = importlib.import_module("edgar.current_filings")
        monkeypatch.setattr(module, "get_with_retry", lambda url: _Response(content))
    return serve


@pytest.mark.fast
def test_the_atom_namespace_does_not_hide_entries(_serve_feed):
    """A plain lxml `.//entry` matches nothing in this feed — every element is
    `{http://www.w3.org/2005/Atom}entry`. Getting this wrong returns an empty feed
    rather than an error, so it is worth an explicit test."""
    from edgar.current_filings import get_current_entries_on_page
    _serve_feed(ATOM_FEED)

    entries = get_current_entries_on_page(count=10, start=0)

    assert len(entries) == 1
    assert entries[0]["form"] == "4"
    assert entries[0]["company"] == "WILKS LEWIS"
    assert entries[0]["cik"] == 1076463
    assert entries[0]["accession_number"] == "0001076463-26-000012"
    assert entries[0]["filing_date"] == datetime.date(2026, 8, 18)


@pytest.mark.fast
def test_an_html_error_page_yields_no_entries_rather_than_raising(_serve_feed):
    """Paging past the end of the feed gets HTTP 503 and this page. Pagination stops
    because the page parses to zero entries; a strict parser would raise instead."""
    from edgar.current_filings import get_current_entries_on_page
    _serve_feed(HTML_ERROR_PAGE)

    assert get_current_entries_on_page(count=10, start=100_000) == []


@pytest.mark.fast
@pytest.mark.parametrize("content", [b"", b"   ", b"garbage, not markup at all"])
def test_an_unparseable_response_yields_no_entries(_serve_feed, content):
    from edgar.current_filings import get_current_entries_on_page
    _serve_feed(content)

    assert get_current_entries_on_page(count=10, start=0) == []
