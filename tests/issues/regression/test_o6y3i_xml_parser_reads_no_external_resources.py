"""Every lxml XML parse reads only the bytes it is given.

Bead: edgartools-o6y3i (attack-surface audit, 2026-10-22).

lxml's defaults block network access and external general entities, but lxml
6.1.0-6.1.2 (and every earlier release) still load an external parameter entity
named in a document's internal DTD subset from the local filesystem, in strict and
recovering mode alike; lxml 6.1.3 fixed that upstream (LP#2165901). Filing XML is
written by the filer, so the lxml floor is now 6.1.3 and, independently of the
installed lxml, every parse goes through ``edgar.xmltools.xml_parser``
(and ``add_safe_resolver`` for iterparse), whose resolver answers each external
lookup with an empty document. Entities the document defines itself, and the
predefined and character entities, still expand, so ordinary output is unchanged.
"""
import io
import re
from pathlib import Path

import pytest
from lxml import etree

from edgar.xmltools import add_safe_resolver, parse_xml, xml_parser

MARKER = "LOCAL-FILE-CONTENTS-o6y3i"
EDGAR = Path(__file__).parents[3] / "edgar"


@pytest.fixture
def hostile(tmp_path):
    """A Form 4 shaped document whose DOCTYPE pulls entity definitions from a local file."""
    dtd = tmp_path / "local.dtd"
    dtd.write_text(f'<!ENTITY secret "{MARKER}">\n')

    def build(root_xml: str) -> str:
        return (f'<?xml version="1.0"?>\n<!DOCTYPE r [ <!ENTITY % p SYSTEM "{dtd.as_uri()}"> %p; ]>\n'
                + root_xml)
    return build


def test_lxml_floor_has_the_upstream_fix():
    """lxml 6.1.3 stopped loading external parameter entities by default; the floor must not fall below it."""
    pyproject = (EDGAR.parent / "pyproject.toml").read_text(encoding="utf-8")
    floor = re.search(r'"lxml>=([0-9.]+)"', pyproject).group(1)
    assert tuple(int(part) for part in floor.split(".")) >= (6, 1, 3)


def test_parse_xml_does_not(hostile):
    doc = hostile("<ownershipDocument><issuerName>&secret;</issuerName></ownershipDocument>")
    for source in (doc, doc.encode()):
        root = parse_xml(source)
        assert MARKER not in etree.tostring(root, encoding="unicode")


def test_strict_xml_parser_rejects_instead_of_reading(hostile):
    doc = hostile("<ownershipDocument><issuerName>&secret;</issuerName></ownershipDocument>")
    with pytest.raises(etree.XMLSyntaxError) as raised:
        etree.fromstring(doc.encode(), parser=xml_parser())
    assert MARKER not in str(raised.value)


def test_iterparse_with_the_resolver_does_not(hostile):
    doc = hostile("<proxyVoteTable><issuerName>&secret;</issuerName></proxyVoteTable>")
    context = add_safe_resolver(etree.iterparse(io.BytesIO(doc.encode()), events=("end",), recover=True))
    assert all(MARKER not in (element.text or "") for _, element in context)


def test_xbrl_instance_does_not(hostile):
    from edgar.xbrl.parsers.coordinator import XBRLParser
    doc = hostile(
        '<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:dei="http://xbrl.sec.gov/dei/2024">'
        '<context id="c"><entity><identifier scheme="http://www.sec.gov/CIK">1</identifier></entity>'
        '<period><instant>2024-12-31</instant></period></context>'
        '<dei:EntityRegistrantName contextRef="c">&secret;</dei:EntityRegistrantName></xbrl>')
    parser = XBRLParser()
    parser.parse_instance_content(doc)
    assert all(MARKER not in str(fact.value) for fact in parser.facts.values())
    assert MARKER not in str(parser.entity_info)


def test_fund_census_does_not(hostile):
    from edgar.funds.ncen import FundCensus
    doc = hostile('<edgarSubmission xmlns="http://www.sec.gov/edgar/ncen"><headerData>'
                  '<filerInfo><filer><issuerCredentials><cik>&secret;</cik></issuerCredentials></filer></filerInfo>'
                  '</headerData></edgarSubmission>')
    try:
        result = FundCensus._parse_xml(doc)
    except Exception as error:  # a malformed census may be rejected; it must not carry the file
        assert MARKER not in str(error)
    else:
        assert MARKER not in repr(result)


def test_entities_the_document_defines_still_expand():
    doc = (b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY co "Acme &amp; Co">]>'
           b'<r><n>&co;</n><m>&amp;&#169;&lt;</m></r>')
    root = etree.fromstring(doc, parser=xml_parser(recover=True))
    assert root.findtext("n") == "Acme & Co"
    assert root.findtext("m") == "&©<"


def test_a_real_form4_parses_as_before():
    """Snowflake Form 4 (tests' tracked fixture data/form4.snow.xml): issuer, CIK, owner, period."""
    root = parse_xml(Path("data/form4.snow.xml").read_text())
    assert root.findtext(".//issuerName") == "Snowflake Inc."
    assert root.findtext(".//issuerCik") == "0001640147"
    assert root.findtext(".//rptOwnerName") == "Scarpelli Michael"
    assert root.findtext(".//periodOfReport") == "2022-12-13"


# Every lxml XML parse in edgar/ must go through xml_parser / add_safe_resolver.
_RAW_PARSER = re.compile(r"\b(?:etree|ET)\.XMLParser\(")
_PARSE_CALL = re.compile(r"\b(?:etree|ET)\.(?:fromstring|XML|fromstringlist|parse)\((?P<args>[^\n]*)")
_ITERPARSE = re.compile(r"\b(?:etree|ET)\.iterparse\(")


def _lxml_modules():
    for path in sorted(EDGAR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*(?:from lxml import etree|import lxml\.etree)", text, re.M):
            yield path, text


def test_no_module_builds_its_own_xml_parser():
    offenders = [f"{p.relative_to(EDGAR)}:{text[:m.start()].count(chr(10)) + 1}"
                 for p, text in _lxml_modules() if p.name != "xmltools.py"
                 for m in _RAW_PARSER.finditer(text)]
    assert offenders == []


def test_every_lxml_parse_names_a_parser():
    """A fromstring()/XML() with no parser argument uses lxml's default parser, which has no resolver."""
    offenders = []
    for path, text in _lxml_modules():
        for m in _PARSE_CALL.finditer(text):
            line_no = text[:m.start()].count("\n") + 1
            call = text[m.start():m.start() + 400]
            if "parser" not in call.split(")\n")[0] and "HTMLParser" not in call:
                offenders.append(f"{path.relative_to(EDGAR)}:{line_no}")
    assert offenders == []


def test_every_iterparse_gets_the_resolver():
    offenders = [f"{p.relative_to(EDGAR)}:{text[:m.start()].count(chr(10)) + 1}"
                 for p, text in _lxml_modules() for m in _ITERPARSE.finditer(text)
                 if "add_safe_resolver(" not in text[max(0, m.start() - 40):m.start()]]
    assert offenders == []
