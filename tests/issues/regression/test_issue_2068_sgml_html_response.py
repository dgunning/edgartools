"""An HTML page instead of the submission text falls back to the filing homepage again.

GitHub Issue: https://github.com/dgunning/edgartools/issues/2068

SEC can list a filing a few minutes before it serves the full submission text,
and until then the .txt URL answers with an HTML page. Filing.sgml() raises
SECHTMLResponseError for that page, and 5.x then built the SGML from the filing
homepage. In 6.x the error propagated instead: SECHTMLResponseError is a
TransportError without a status, so is_unreachable() treated it as a network
failure.

Filing: Philip J. Metheny's Form 4 for Commercial Bancgroup (CBK),
0000898432-26-000808, filed 2026-11-24. Its .txt answered with an HTML page for
about five minutes after it was listed. The values asserted are from its
form4.xml on SEC.
"""

import pytest

from edgar import Filing
from edgar.ownership import Form4
from edgar.sgml import sgml_common

pytestmark = pytest.mark.regression

SEC_HTML_PAGE = "<html><head><title>SEC.gov</title></head><body><p>Please try again later.</p></body></html>"


@pytest.mark.vcr
def test_form4_reads_from_homepage_while_submission_text_is_an_html_page(monkeypatch):
    # Exercise the network-source path regardless of the developer's storage settings.
    monkeypatch.setattr("edgar._filings.is_using_local_storage", lambda: False)
    monkeypatch.setattr("edgar.storage.datamule.is_using_datamule_storage", lambda: False)
    filing = Filing(
        form="4",
        company="Metheny Philip J.",
        cik=2087401,
        filing_date="2026-11-24",
        accession_no="0000898432-26-000808",
    )
    read_content_as_string = sgml_common.read_content_as_string

    def read(source, *args, **kwargs):
        if source == filing.text_url:
            return SEC_HTML_PAGE
        return read_content_as_string(source, *args, **kwargs)

    monkeypatch.setattr(sgml_common, "read_content_as_string", read)

    form4 = filing.obj()

    assert isinstance(form4, Form4)
    assert form4.issuer.name == "Commercial Bancgroup, Inc."
    trade = form4.market_trades.iloc[0]
    assert trade["Shares"] == 350
    assert trade["Price"] == 32.155
