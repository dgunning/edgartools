"""Regression test for issue #912.

GitHub Issue: https://github.com/dgunning/edgartools/issues/912

The Ocean Park High Income ETF 497K (accession 0001580642-24-004234) declares
one class, C000250992, in its SGML header with no
``<CLASS-CONTRACT-TICKER-SYMBOL>``, so ``Prospectus497K.tickers`` came back
``[]``. The ticker, DUKH, is printed only on the cover, as a centred bold
paragraph above "Primary Listing Exchange for the Fund". The fee-table half of
this issue was fixed in 5.43.1 and #1160; this covers the remaining ticker.

The cover is read only when the header names exactly one class and gives it
no ticker, and only a cover with exactly one ticker candidate answers.
"""

import pytest

from edgar.funds._497k_tables import extract_cover_ticker

# The cover of 0001580642-24-004234, as filed.
OCEAN_PARK_COVER = """<HTML><BODY>
<P STYLE="font: 16pt Arial; text-align: center"><FONT><I>Ocean Park
High Income ETF</I></FONT></P>
<P STYLE="font: bold 11pt Arial; text-align: center">DUKH</P>
<P STYLE="font: bold 11pt Arial; text-align: center">&nbsp;</P>
<P STYLE="font: 12pt Arial; text-align: center"><B>Primary Listing Exchange for the Fund: The
NASDAQ Stock Market LLC</B></P>
<P STYLE="font: 12pt Arial; text-align: center"><B>Summary Prospectus</B></P>
<P STYLE="font: 12pt Arial; text-align: center"><B>July 1, 2024</B></P>
<P><B>Investment Objective</B></P>
<P>The Fund seeks to provide total return. Its NAV is published daily by the SEC.</P>
</BODY></HTML>"""


def test_the_cover_ticker_is_read():
    assert extract_cover_ticker(OCEAN_PARK_COVER) == 'DUKH'


def test_a_labelled_ticker_is_read():
    html = '<html><body><p>Example Fund</p><p><b>Ticker Symbol:</b> EXMPX</p><p>Fees and Expenses</p></body></html>'
    assert extract_cover_ticker(html) == 'EXMPX'


def test_the_ticker_after_the_listing_exchange_is_read():
    # Innovator U.S. Equity Accelerated ETF - Quarterly, 0001213900-24-057514: the header
    # names the class without a ticker and the cover prints it after the exchange.
    html = ('<html><body><p>Summary Prospectus</p>'
            '<p>Innovator U.S. Equity Accelerated ETF\u2122 \u2014 Quarterly</p>'
            '<p>(Cboe BZX \u2014 XDSQ)</p><p>July 1, 2024</p>'
            '<p>Primary Listing Exchange for the Fund: The NASDAQ Stock Market LLC</p></body></html>')
    assert extract_cover_ticker(html) == 'XDSQ'


@pytest.mark.parametrize('html', [
    # two tickers on the cover: which class owns which is not knowable here
    '<html><body><p>Class A: AAAAX</p><p>Ticker: AAAAX</p><p>Ticker: IIIIX</p></body></html>',
    # capitals after the cover are body text, not a ticker
    '<html><body><p>Example ETF</p><p>Investment Objective</p><p>NAV</p><p>ABCD</p></body></html>',
    # a label with nothing usable after it
    '<html><body><p>Example Fund</p><p>Ticker: N/A</p></body></html>',
    '',
])
def test_no_single_cover_ticker_is_none(html):
    assert extract_cover_ticker(html) is None


@pytest.mark.network
def test_ocean_park_497k_has_its_ticker():
    from edgar import find

    prospectus = find('0001580642-24-004234').obj()
    assert prospectus.tickers == ['DUKH']
    assert prospectus.num_share_classes == 1
    share_class = prospectus.share_classes[0]
    assert share_class.class_id == 'C000250992'
    assert share_class.ticker == 'DUKH'
    assert share_class.expense_1yr == 109 and share_class.expense_3yr == 381
    assert str(prospectus) == 'Prospectus497K(Ocean Park High Income ETF, 1 classes, DUKH)'
