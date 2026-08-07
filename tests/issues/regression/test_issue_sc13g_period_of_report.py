"""
Regression test for Schedule 13D/G multi-filer crash.

FilingHomepage.get_filing_dates used to pick the "Period of Report" block
by position (grouping_divs[1]). On multi-filer Schedule 13D/G filings, the
Filer(s) block can appear at index 1 and its .text.strip() concatenates
each filer's name with no delimiter. Downstream callers (e.g.
sec-edgar-mcp) then blow up with "Invalid isoformat string: ...". The fix
is to pick the block by matching its <div class="infoHead"> label instead
of by position.
"""

import pytest
from bs4 import BeautifulSoup

from edgar.attachments import Attachments, FilingHomepage

pytestmark = pytest.mark.fast


def _homepage_from_html(html: str) -> FilingHomepage:
    soup = BeautifulSoup(html, "html.parser")
    # Attachments is irrelevant for these tests; pass an empty instance.
    attachments = Attachments(document_files=[], data_files=[], primary_documents=[])
    return FilingHomepage(url="http://example/index.html", soup=soup, attachments=attachments)


_FILING_AND_ACCEPTED = """
<div class="formGrouping">
    <div class="infoHead">Filing Date</div>
    <div class="info">2024-05-01</div>
    <div class="infoHead">Accepted</div>
    <div class="info">2024-05-01 16:30:00</div>
</div>
"""


def test_multi_filer_does_not_return_concatenated_filer_names():
    """When the Filer(s) block sits at grouping_divs[1], period should be None."""
    html = f"""
    <html><body>
    {_FILING_AND_ACCEPTED}
    <div class="formGrouping">
        <div class="infoHead">Filer(s)</div>
        <div class="info">FILER ONE</div>
        <div class="info">FILER TWO, LLC</div>
        <div class="info">FILER THREE</div>
        <div class="info">FILER FOUR, INC.</div>
    </div>
    </body></html>
    """
    homepage = _homepage_from_html(html)
    filing_date, accepted_date, period = homepage.get_filing_dates()

    assert filing_date == "2024-05-01"
    assert accepted_date == "2024-05-01 16:30:00"
    assert period is None, f"Expected None, got {period!r}"


def test_period_block_found_by_label_when_at_index_1():
    """Traditional layout: grouping_divs[1] is Period of Report."""
    html = f"""
    <html><body>
    {_FILING_AND_ACCEPTED}
    <div class="formGrouping">
        <div class="infoHead">Period of Report</div>
        <div class="info">2024-03-31</div>
    </div>
    </body></html>
    """
    homepage = _homepage_from_html(html)
    filing_date, accepted_date, period = homepage.get_filing_dates()

    assert filing_date == "2024-05-01"
    assert accepted_date == "2024-05-01 16:30:00"
    assert period == "2024-03-31"


def test_period_block_found_even_when_not_at_index_1():
    """Label-based lookup should work regardless of position."""
    html = f"""
    <html><body>
    {_FILING_AND_ACCEPTED}
    <div class="formGrouping">
        <div class="infoHead">Filer(s)</div>
        <div class="info">FILER ONE</div>
        <div class="info">FILER TWO, LLC</div>
    </div>
    <div class="formGrouping">
        <div class="infoHead">Period of Report</div>
        <div class="info">2024-03-31</div>
    </div>
    </body></html>
    """
    homepage = _homepage_from_html(html)
    filing_date, accepted_date, period = homepage.get_filing_dates()

    assert filing_date == "2024-05-01"
    assert accepted_date == "2024-05-01 16:30:00"
    assert period == "2024-03-31"


def test_no_period_block_returns_none_for_period():
    """No Period of Report block at all -> period is None."""
    html = f"""
    <html><body>
    {_FILING_AND_ACCEPTED}
    </body></html>
    """
    homepage = _homepage_from_html(html)
    filing_date, accepted_date, period = homepage.get_filing_dates()

    assert filing_date == "2024-05-01"
    assert accepted_date == "2024-05-01 16:30:00"
    assert period is None
