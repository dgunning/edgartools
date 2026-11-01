"""ixt-sec:exchnameen accepts all 21 exchange names in SEC's transformation registry.

Registry: Arelle/EDGAR transform/transformationRegistry/registry/ixt-sec-exchnameen.xml
(21 input names); codes from the dei edgarExchangeCodeItemType enumeration
(https://xbrl.sec.gov/dei/2026/dei-2026.xsd). Ground truth: Fidelity Wise Origin
Bitcoin Fund 10-K for FY2025, accession 0001193125-26-071484, fact
F_99b587ff-9cee-4d4e-b948-17cb34ad1c45 reads "Cboe BZX Exchange, Inc." and EDGAR's
extracted instance gives CboeBZX.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1855
"""
import pytest

from edgar.documents import parse_html
from edgar.documents.strategies.ixbrl_transforms import TransformError, apply_transform

REGISTRY_NAMES = {
    'BOX Exchange LLC': 'BOX',
    'Cboe BYX Exchange, Inc.': 'CboeBYX',
    'Cboe BZX Exchange, Inc.': 'CboeBZX',
    'Cboe C2 Exchange, Inc.': 'C2',
    'Cboe EDGA Exchange, Inc.': 'CboeEDGA',
    'Cboe EDGX Exchange, Inc.': 'CboeEDGX',
    'Cboe Exchange, Inc.': 'CBOE',
    'Chicago Stock Exchange, Inc.': 'CHX',
    'Investors Exchange LLC': 'IEX',
    'Miami International Securities Exchange LLC': 'MIAX',
    'MIAX PEARL, LLC': 'PEARL',
    'Nasdaq BX, Inc.': 'BX',
    'Nasdaq GEMX, LLC': 'GEMX',
    'Nasdaq ISE, LLC': 'ISE',
    'Nasdaq MRX, LLC': 'MRX',
    'Nasdaq PHLX LLC': 'Phlx',
    'New York Stock Exchange LLC': 'NYSE',
    'NYSE American LLC': 'NYSEAMER',
    'NYSE Arca, Inc.': 'NYSEArca',
    'NYSE National, Inc.': 'NYSENAT',
    'The Nasdaq Stock Market LLC': 'NASDAQ',
}


@pytest.mark.fast
def test_registry_has_21_names():
    assert len(REGISTRY_NAMES) == 21


@pytest.mark.fast
@pytest.mark.parametrize("name,code", sorted(REGISTRY_NAMES.items()))
def test_registry_name_maps_to_dei_code(name, code):
    assert apply_transform('ixt-sec:exchnameen', name) == code


@pytest.mark.fast
@pytest.mark.parametrize("name,code", [
    ('New York Stock Exchange', 'NYSE'),
    ('new york stock exchange', 'NYSE'),
    ('Nasdaq Global Select Market', 'NASDAQ'),
    ('NASDAQ Stock Market LLC', 'NASDAQ'),
    ('Cboe BZX', 'CboeBZX'),
])
def test_previously_working_names_still_work(name, code):
    assert apply_transform('ixt-sec:exchnameen', name) == code


@pytest.mark.fast
def test_unknown_exchange_still_raises():
    with pytest.raises(TransformError):
        apply_transform('ixt-sec:exchnameen', 'Bogus Exchange, Inc.')


@pytest.mark.fast
def test_fbtc_cover_page_fact_normalizes_to_cbo_bzx():
    html = (
        '<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>'
        '<ix:header><ix:resources><xbrli:context xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'id="C_3c944ec8-d055-4cef-bac0-f4530db6e2d9"><xbrli:entity>'
        '<xbrli:identifier scheme="http://www.sec.gov/CIK">0001852317</xbrli:identifier></xbrli:entity>'
        '<xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate>'
        '</xbrli:period></xbrli:context></ix:resources></ix:header>'
        '<p><ix:nonNumeric id="F_99b587ff-9cee-4d4e-b948-17cb34ad1c45" '
        'contextRef="C_3c944ec8-d055-4cef-bac0-f4530db6e2d9" name="dei:SecurityExchangeName" '
        'format="ixt-sec:exchnameen"><span>Cboe BZX Exchange, Inc.</span></ix:nonNumeric></p>'
        '</body></html>'
    )
    facts = [f for f in parse_html(html).xbrl_facts if f.concept == 'dei:SecurityExchangeName']
    assert len(facts) == 1
    assert facts[0].value == 'CboeBZX'
    assert 'format_issue' not in (facts[0].metadata or {})
