"""
An Inline XBRL fact and its ix:continuation chain are joined with nothing in between.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1748

XBRLExtractor._relevant_content appended a space before each continuation of
a non-escaped fact. The filer decides where the split falls, including inside
a word or a number: Cooper's 10-Q 0001628280-26-041305 splits its address line
"6101 Bollinger Canyon Road" after the "6", and the extractor returned
"6 101 Bollinger Canyon Road".
"""
from pathlib import Path

from edgar.documents import HTMLParser

FIXTURES = Path(__file__).parents[2] / 'fixtures' / 'html'

# Markup shape from Cooper Companies 10-Q 0001628280-26-041305 (coo-20260430.htm).
COOPER = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
<ix:header><ix:resources>
<xbrli:context id="c-1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000711404</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-11-01</xbrli:startDate><xbrli:endDate>2026-04-30</xbrli:endDate></xbrli:period></xbrli:context>
</ix:resources></ix:header>
<p><span><ix:nonNumeric name="dei:EntityAddressAddressLine1" contextRef="c-1" id="f-9" continuedAt="f-9-1">6</ix:nonNumeric></span><span><ix:continuation id="f-9-1">101 Bollinger Canyon Road</ix:continuation></span></p>
<p><ix:nonNumeric name="dei:EntityRegistrantName" contextRef="c-1" id="f-1" continuedAt="f-1-1">AB</ix:nonNumeric><ix:continuation id="f-1-1">CD</ix:continuation></p>
</body></html>"""


def _facts(html):
    return HTMLParser().parse(html).metadata.xbrl_data


def test_a_token_split_across_a_continuation_is_not_broken():
    facts = {f.concept: f.value for f in _facts(COOPER)}
    assert facts['dei:EntityAddressAddressLine1'] == '6101 Bollinger Canyon Road'
    assert facts['dei:EntityRegistrantName'] == 'ABCD'


def test_alphabet_trading_arrangement_name_matches_the_sec_instance():
    """
    Alphabet 10-K, accession 0001652044-25-000014: ecd:TrdArrIndName f-1691 is
    a bullet "•" continued at f-1691-1 "John Hennessy". The SEC's extracted
    instance (goog-20241231_htm.xml) has "•John Hennessy".
    """
    html = (FIXTURES / 'googl' / '10k' / 'googl-10-k-2025-02-05.html').read_text(encoding='utf-8')
    names = [f.value for f in _facts(html) if f.concept == 'ecd:TrdArrIndName']
    assert '•John Hennessy' in names
    assert '• John Hennessy' not in names


def test_talos_restriction_text_matches_the_sec_instance():
    """
    Talos Energy 10-K, accession 0001193125-26-067807: the non-escaped
    us-gaap:RestrictionToTransferFunds fact ends a paragraph with "undistributed
    earnings." and continues in the next with "The Bank Credit Facility". The
    SEC's extracted instance (talo-20251231_htm.xml) reads
    "undistributed earnings.The Bank Credit Facility".
    """
    html = (FIXTURES / 'talo' / '10k' / 'talo-10-k-2026-02-25.html').read_text(encoding='utf-8')
    fact = next(f for f in _facts(html) if f.concept == 'us-gaap:RestrictionToTransferFunds')
    assert 'undistributed earnings.The Bank Credit Facility' in fact.value
