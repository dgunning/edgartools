"""
ixt-sec:exchnameen returns only dei:SecurityExchangeName enumeration values.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1726

dei:SecurityExchangeName is an enumerated token and matches exactly, case
included. The exchange table returned NYSETXSE for NYSE Texas and NYSECHX for
NYSE Chicago, neither of which is in the enumeration, and LTSE and MEMX, which
have no dei code at all.
"""
import pytest

from edgar.documents import HTMLParser
from edgar.documents.strategies.ixbrl_transforms import _EXCHANGE_CODES, TransformError, apply_transform

# dei 2026 edgarExchangeCodeItemType (https://xbrl.sec.gov/dei/2026/dei-2026.xsd),
# exchange members only; NONE is the "no exchange" value.
DEI_2026_EXCHANGE_CODES = {
    'NYSE', 'NASDAQ', 'CHX', 'BOX', 'BX', 'C2', 'CBOE', 'CboeBYX', 'CboeBZX',
    'CboeEDGA', 'CboeEDGX', 'GEMX', 'IEX', 'ISE', 'MIAX', 'MRX', 'NYSEAMER',
    'NYSEArca', 'NYSENAT', 'NYSETX', 'PEARL', 'Phlx',
}


@pytest.mark.parametrize('name,code', [
    ('NYSE Texas', 'NYSETX'),
    ('NYSE Texas, Inc.', 'NYSETX'),
    ('NYSE Chicago', 'CHX'),
    ('NYSE Chicago, Inc.', 'CHX'),
    ('NYSE Arca, Inc.', 'NYSEArca'),
])
def test_exchange_names_map_to_dei_codes(name, code):
    assert apply_transform('ixt-sec:exchnameen', name) == code


@pytest.mark.parametrize('name', ['Long-Term Stock Exchange, Inc.', 'MEMX LLC', 'Members Exchange'])
def test_exchanges_without_a_dei_code_are_rejected(name):
    with pytest.raises(TransformError):
        apply_transform('ixt-sec:exchnameen', name)


def test_every_code_in_the_table_is_a_dei_enumeration_value():
    assert set(_EXCHANGE_CODES.values()) <= DEI_2026_EXCHANGE_CODES


def test_jpmorgan_nyse_arca_cover_fact():
    """
    JPMorgan Chase 10-Q, accession 0001628280-26-054343 (jpm-20260630.htm),
    facts f-39 and f-42 write "NYSE Arca, Inc." under ixt-sec:exchnameen; the
    SEC's extracted instance has NYSEArca. The markup below is that fact's shape.
    """
    html = """<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
        xmlns:ixt-sec="http://www.sec.gov/inlineXBRL/transformation/2015-08-31"><body>
    <ix:nonNumeric contextRef="c-10" name="dei:SecurityExchangeName" format="ixt-sec:exchnameen"
        id="f-39">NYSE Arca, Inc.</ix:nonNumeric>
    </body></html>"""
    fact = HTMLParser().parse(html).metadata.xbrl_data[0]
    assert fact.value == 'NYSEArca'
