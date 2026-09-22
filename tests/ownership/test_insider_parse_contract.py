"""What the Form 3/4/5 parse entry point owes its callers, with no network.

`edgar/ownership/` moved from BeautifulSoup to lxml under edgartools-07lk.11.3.
These are the regressions that move would introduce silently — a root check that
stops recognising its own document, a namespace that hides every element, a
footnote truncated at the first tag inside it. None of them raises; each returns
a plausible, wrong answer, so they belong in a job that runs on every commit
rather than in the sequential network suite where `tests/test_ownership.py` sits.

Everything here reads a checked-in fixture or an inline string. Verified with
outbound sockets blocked (`pytest -p tests._offline_harness`) before being
registered in `FAST_PATTERNS`.
"""
from pathlib import Path

import pytest

import edgar.ownership.owners as owners_module
from edgar.ownership import Ownership
from edgar.ownership.models import Footnotes
from edgar.xmltools import parse_xml

FORM4 = Path('data/form4.snow.xml')
FORM_D = Path('data/D.1685REIT.xml')


@pytest.fixture
def offline_owners(monkeypatch):
    """Stub the only thing in this path that reaches the SEC.

    `ReportingOwners` resolves each owner's CIK to decide whether to reverse the
    name. That lookup is untouched by the lxml port, and stubbing it is what lets
    the rest of `parse_xml` be asserted in the fast job. The offline harness, not
    this fixture, is what proves nothing else here fetches.
    """
    class StubEntity:
        def __init__(self, cik):
            self.data = type("Data", (), {"is_company": True})()

    monkeypatch.setattr(owners_module, "Entity", StubEntity)


def test_parse_xml_rejects_a_document_that_is_not_an_ownership_form(offline_owners):
    """`soup.find("ownershipDocument")` searched the whole document and returned
    None when it was absent; the lxml parse starts at the root, so the same guard
    is now a name comparison. It must still refuse a Form D rather than returning
    an ownership document full of `None`."""
    with pytest.raises(ValueError, match="ownershipDocument"):
        Ownership.parse_xml(FORM_D.read_text())


def test_parse_xml_reads_a_namespaced_root_by_local_name(offline_owners):
    """SEC does not namespace Form 3/4/5 today, but the root check must not be the
    thing that breaks if it starts to — a plain `.tag` comparison would, and a
    plain lxml `.//` search would then find nothing at all, silently."""
    plain = Ownership.parse_xml(FORM4.read_text())
    namespaced = Ownership.parse_xml(FORM4.read_text().replace(
        '<ownershipDocument>',
        '<ownershipDocument xmlns="http://www.sec.gov/edgar/ownership">', 1))

    assert namespaced['issuer'].name == plain['issuer'].name
    assert len(namespaced['footnotes']) == len(plain['footnotes'])
    assert namespaced['reporting_period'] == plain['reporting_period']
    assert (namespaced['non_derivative_table'].transactions.data.to_dict()
            == plain['non_derivative_table'].transactions.data.to_dict())


def test_footnotes_survive_markup_inside_a_footnote():
    """lxml's `.text` stops at the first CHILD ELEMENT, so a footnote containing
    any markup would lose everything from that tag onward — returning a shorter,
    entirely plausible sentence. `element_text` walks the subtree instead."""
    root = parse_xml(
        "<ownershipDocument><footnotes>"
        "<footnote id='F1'>Shares held by the <b>Smith Family</b> Trust.</footnote>"
        "<footnote id='F2'>Plain footnote.</footnote>"
        "</footnotes></ownershipDocument>")

    footnotes = Footnotes.extract(root)
    assert footnotes['F1'] == "Shares held by the Smith Family Trust."
    assert footnotes['F2'] == "Plain footnote."


def test_a_transaction_footnote_id_is_read_from_an_empty_element():
    """The truthiness trap, at the one call site where it decides a value.

    `<footnoteId id="F1"/>` has an attribute and no children, which lxml considers
    false. A `if tag:` guard would drop every footnote reference on a Form 4.
    """
    from edgar.ownership.core import get_footnotes, transaction_footnote_id
    from edgar.xmltools import find_element

    root = parse_xml("<transaction><securityTitle><footnoteId id='F1'/></securityTitle>"
                     "<transactionAmounts><footnoteId id='F2'/><footnoteId id='F1'/>"
                     "</transactionAmounts></transaction>")

    assert transaction_footnote_id(find_element(root, "footnoteId")) == ('footnote', 'F1')
    # Deduped, first-seen order preserved, collected from the whole transaction.
    assert get_footnotes(root) == "F1\nF2"


def test_malformed_ownership_xml_still_parses():
    """SEC's own Forms 4 are not always well-formed, and bs4 recovered from that.

    AAR CORP's 2004-02-04 Form 4 (0000001750-04-000011) carries a mangled attribute
    — `<nonDerivativeTable ativeTable>`, reproduced here — which a strict parser
    rejects outright. bs4 built its XML parser with `recover=True` and read the
    filing fine for years, so `xmltools.parse_xml` does too.

    This is pinned at the ownership layer as well as in the adapter contract
    because of how it failed: `edgar/sgml/text_extraction.ownership_xml_to_html`
    catches every exception and returns None, so a raising parse did not surface as
    an error — `filing.sgml().text()` quietly went back to dumping raw markup, and
    only the network regression lane noticed (edgartools-07lk.11.3).
    """
    root = parse_xml(
        "<ownershipDocument><schemaVersion>X0201</schemaVersion>"
        "<documentType>4</documentType><periodOfReport>2004-01-07</periodOfReport>"
        "<issuer><issuerCik>0000001750</issuerCik><issuerName>AAR CORP</issuerName>"
        "<issuerTradingSymbol>AIR</issuerTradingSymbol></issuer>"
        "<nonDerivativeTable ativeTable>"
        "<nonDerivativeTransaction><securityTitle><value>Common Stock</value>"
        "</securityTitle></nonDerivativeTransaction>"
        "</nonDerivativeTable></ownershipDocument>")

    from edgar.xmltools import child_text, local_name

    assert local_name(root) == "ownershipDocument"
    assert child_text(root, "documentType") == "4"
    assert child_text(root, "issuerTradingSymbol") == "AIR"
    # The content *after* the malformed attribute survives recovery too, which is
    # the part that decides whether the rendered form has any rows in it.
    assert child_text(root, "value") == "Common Stock"
