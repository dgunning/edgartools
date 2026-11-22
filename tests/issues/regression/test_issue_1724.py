"""
The ICFR auditor-attestation flag reads every XML Schema boolean form.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1724

``dei:IcfrAuditorAttestationFlag`` is an ``xs:boolean``, whose lexical space is
``true``/``false``/``1``/``0``. ``extract_auditor_info`` compared the value with
the word ``true`` only, so a flag filed as ``1`` read as False. It now reads the
value through the shared ``edgar.xmltools.parse_xml_boolean``.

The instance below is SYNTHETIC: no real filing that tags this flag as ``1``
was found (the SEC-rendered instances of the 10-K fixtures in this repo, e.g.
Pfizer's FY2024 10-K, tag it ``ixt-sec:boolballotbox``, which renders ``true``).
"""
import pytest

from edgar.company_reports.auditor import extract_auditor_info
from edgar.xbrl import XBRL
from edgar.xmltools import parse_xml_boolean

_INSTANCE = '''<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:dei="http://xbrl.sec.gov/dei/2025">
<context id="c"><entity><identifier scheme="http://www.sec.gov/CIK">1</identifier></entity>
<period><instant>2025-12-31</instant></period></context>
<dei:AuditorName contextRef="c">Example Auditor</dei:AuditorName>
<dei:IcfrAuditorAttestationFlag contextRef="c">{lexical}</dei:IcfrAuditorAttestationFlag></xbrl>'''


def _icfr(lexical: str) -> bool:
    xbrl = XBRL()
    xbrl.parser.parse_instance_content(_INSTANCE.format(lexical=lexical))
    return extract_auditor_info(xbrl).icfr_attestation


@pytest.mark.fast
@pytest.mark.parametrize("lexical, expected", [
    ("true", True), ("1", True), (" 1 ", True),
    ("false", False), ("0", False),
])
def test_icfr_attestation_reads_every_boolean_form(lexical, expected):
    assert _icfr(lexical) is expected


@pytest.mark.fast
@pytest.mark.parametrize("value, expected", [
    ("true", True), ("1", True), ("\n true \t", True), ("TRUE", True),
    ("false", False), ("0", False),
    ("", None), (None, None), ("yes", None), ("2", None),
])
def test_parse_xml_boolean(value, expected):
    assert parse_xml_boolean(value) is expected
