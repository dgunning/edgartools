"""The one contract `edgar.xmltools` owes its callers, asserted on both backends.

`edgar/xmltools.py` is the shared XML helper layer for 12 parsers (Form D, Form 144,
Form 3/4/5 ownership, 13F, Schedule 13D/G, muni advisors, EFFECT, filing summaries),
and roughly 350 call sites reach it. Bead edgartools-07lk.11.2 made it dual-backend so
those dependents can move from BeautifulSoup to lxml one at a time
(edgartools-07lk.11.3) rather than in a single commit.

Every test below runs against BOTH backends, via the `parse` fixture. That is the
point: the two halves of the adapter are held to one contract instead of drifting
apart during the migration, and a value that only survives on one backend is a
failure rather than a surprise three weeks later.

The four differences the adapter exists to absorb — each verified against the bs4 and
lxml versions installed here, and each one silent, returning `None` or `""` where a
value used to be:

    truthiness  bs4 `bool(Tag)` is True even for a childless `<c/>`; lxml
                `bool(Element)` is False even for `<b>text</b>` (and warns). Guards
                test `is not None`.

    find depth  bs4 `.find()` searches all descendants; lxml `.find()` searches
                direct children only. The adapter uses `.//name`.

    .text       bs4 `.text` concatenates all descendant text; lxml `.text` stops at
                the first child element. The adapter walks the subtree.

    whitespace  bs4's XML treebuilder collapses a whitespace-ONLY text node to a
                single character. The adapter reproduces that exactly; it is the one
                place the port is more than a translation.

When the bs4 half is deleted in the 6.0 window, drop the "bs4" param from `parse` —
what remains is still the full contract.
"""
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup, Tag
from lxml import etree

from edgar.xmltools import (
    child_text,
    child_texts,
    child_value,
    element_text,
    extract_child_text,
    extract_child_value,
    find_all_elements,
    find_element,
    get_footnote_ids,
    local_name,
    optional_decimal,
    parse_xml,
    value_or_footnote,
    value_with_footnotes,
)

# A Form D <primaryIssuer> block, the shape edgar/_party.py:86-111 documents.
ISSUER_XML = """<?xml version="1.0"?>
<edgarSubmission>
    <primaryIssuer>
        <cik>0001961089</cik>
        <entityName>1685 38th REIT, L.L.C.</entityName>
        <issuerAddress>
            <street1>2029 CENTURY PARK EAST</street1>
            <street2>SUITE 1370</street2>
            <city>LOS ANGELES</city>
            <stateOrCountry>CA</stateOrCountry>
            <zipCode>90067</zipCode>
        </issuerAddress>
        <issuerPhoneNumber>424-313-1550</issuerPhoneNumber>
        <edgarPreviousNameList>
            <value>None</value>
        </edgarPreviousNameList>
        <entityType/>
        <yearOfInc>
            <withinFiveYears>true</withinFiveYears>
            <value>2022</value>
        </yearOfInc>
    </primaryIssuer>
</edgarSubmission>
"""


def _text_of(el):
    """Backend-neutral text read, for assertions about elements themselves."""
    return el.text if isinstance(el, Tag) else "".join(el.itertext())


@pytest.fixture(params=["bs4", "lxml"])
def parse(request):
    """Parse `xml` and return the element named `name`, on each backend in turn.

    This is what makes the dual-backend adapter honest: every assertion below runs
    against BOTH a BeautifulSoup tree and an lxml tree, so the two halves of
    `edgar/xmltools.py` are held to one contract rather than drifting apart while
    the twelve dependents migrate one at a time (edgartools-07lk.11.3).

    When the bs4 half is deleted in the 6.0 window, drop the "bs4" param.
    """
    def _parse(xml: str, name: str):
        if request.param == "bs4":
            return BeautifulSoup(xml, features="xml").find(name)
        # Resolved by hand rather than through `find_element`, so that the tests do
        # not obtain their starting node from the code they are checking. `iter()`
        # yields the root first, and the local-name compare is what lets a
        # namespaced root be addressed by its bare name.
        for element in etree.fromstring(xml.encode()).iter():
            if isinstance(element.tag, str) and element.tag.rpartition("}")[2] == name:
                return element
        return None

    return _parse


@pytest.fixture
def issuer(parse):
    return parse(ISSUER_XML, "primaryIssuer")


def test_the_fixture_really_produces_both_backends(parse, request):
    """Guard against the suite quietly running bs4 twice and calling it agreement."""
    node = parse(ISSUER_XML, "primaryIssuer")
    if request.node.callspec.params["parse"] == "bs4":
        assert isinstance(node, Tag)
    else:
        assert isinstance(node, etree._Element)
        assert not isinstance(node, Tag)


# ---------------------------------------------------------------- child_text


def test_child_text_reads_an_element_that_has_no_element_children(issuer):
    """The truthiness trap, in the single most-called helper.

    `<cik>` holds text and nothing else, so it has zero *element* children. lxml
    considers such an element false, and `child_text`'s `if el` guard would drop it.
    """
    assert child_text(issuer, "cik") == "0001961089"
    assert child_text(issuer, "issuerPhoneNumber") == "424-313-1550"


def test_child_text_searches_descendants_not_only_direct_children(issuer):
    """`<city>` is a grandchild of `<primaryIssuer>`, and bs4 `.find()` reaches it.

    lxml `.find("city")` would not — it needs `.//city`. Callers rely on the reach:
    see edgar/_party.py:157-162, which only descends to `<issuerAddress>` explicitly
    because the address fields are ambiguous, not because the helper cannot get there.
    """
    assert child_text(issuer, "city") == "LOS ANGELES"
    assert child_text(issuer, "zipCode") == "90067"


def test_child_text_concatenates_all_descendant_text(issuer):
    """`.text` on a container returns the whole subtree's text, not the head text.

    lxml's `.text` would return only the whitespace before `<street1>`, which strips
    to `""` — a silent empty string rather than an error.
    """
    address = child_text(issuer, "issuerAddress")
    for fragment in ("2029 CENTURY PARK EAST", "SUITE 1370", "LOS ANGELES", "CA", "90067"):
        assert fragment in address


def test_child_text_preserves_interior_whitespace_exactly(parse):
    """Pins the interior spacing of concatenated text, which the backends disagree on.

    bs4 and lxml produce different separators between sibling elements' text. Only the
    outer edges are stripped, so any change here reaches callers that compare or hash
    these strings.
    """
    xml = "<r><d>  <e>Y</e>  <f>Z</f> </d></r>"
    assert child_text(parse(xml, "r"), "d") == "Y Z"


def test_child_text_of_an_empty_element_is_empty_string_not_none(issuer):
    """`<entityType/>` yields `""`. The distinction matters: `None` means *absent*."""
    assert child_text(issuer, "entityType") == ""


def test_child_text_of_a_missing_element_is_none(issuer):
    assert child_text(issuer, "notAnElement") is None


def test_child_text_ignores_comments(parse):
    xml = "<r><b><!-- editorial note --><c>X</c></b></r>"
    assert child_text(parse(xml, "r"), "b") == "X"


def test_child_text_strips_surrounding_whitespace(parse):
    xml = "<r><a>\n    padded\n  </a></r>"
    assert child_text(parse(xml, "r"), "a") == "padded"


# --------------------------------------------------------------- child_value


def test_child_value_unwraps_the_nested_value_element(issuer):
    """`child_value` reaches through a wrapper to its `<value>`, `child_text` does not."""
    assert child_value(issuer, "yearOfInc") == "2022"
    # child_text on the same wrapper returns the whole subtree instead, separator included.
    assert child_text(issuer, "yearOfInc") == "true\n2022"


def test_child_value_returns_the_default_when_the_child_is_missing(issuer):
    assert child_value(issuer, "notAnElement") is None
    assert child_value(issuer, "notAnElement", default_value="fallback") == "fallback"


def test_child_value_of_a_present_child_without_a_value_element_is_empty(parse):
    """Present-but-valueless is `""`, distinct from the missing-child default.

    A caller passing `default_value` does NOT get it here — the child exists.
    """
    xml = "<r><child>bare text</child></r>"
    assert child_value(parse(xml, "r"), "child", default_value="fallback") == ""


def test_child_value_appends_footnote_references(parse):
    xml = """<r>
        <underlyingSecurityTitle>
            <value>Class B Common Stock</value>
            <footnoteId id="F2"/>
            <footnoteId id="F3"/>
        </underlyingSecurityTitle>
    </r>"""
    assert child_value(parse(xml, "r"), "underlyingSecurityTitle") == "Class B Common Stock [F2,F3]"


# --------------------------------------------------------------- child_texts


def test_child_texts_returns_every_match_in_document_order(parse):
    xml = """<r>
        <relationship>Executive Officer</relationship>
        <relationship>Director</relationship>
        <relationship>Promoter</relationship>
    </r>"""
    assert child_texts(parse(xml, "r"), "relationship") == [
        "Executive Officer",
        "Director",
        "Promoter",
    ]


def test_child_texts_of_a_missing_element_is_an_empty_list(issuer):
    assert child_texts(issuer, "notAnElement") == []


def test_child_texts_does_not_strip(parse):
    """Unlike `child_text`, `child_texts` returns raw text. Pinned because callers
    downstream do their own stripping and would double-strip or stop stripping."""
    xml = "<r><a> spaced </a></r>"
    assert child_texts(parse(xml, "r"), "a") == [" spaced "]


# ----------------------------------------------------------- optional_decimal


def test_optional_decimal_parses_zero_as_a_decimal(parse):
    """`"0"` must not be confused with absence — SEC fund tables are full of real zeros."""
    xml = "<fundInfo><totAssets>0</totAssets><amt>0.018</amt></fundInfo>"
    fund = parse(xml, "fundInfo")
    assert optional_decimal(fund, "totAssets") == Decimal("0")
    assert optional_decimal(fund, "amt") == Decimal("0.018")


def test_optional_decimal_treats_na_and_absence_and_emptiness_as_none(parse):
    xml = "<fundInfo><na>N/A</na><blank/></fundInfo>"
    fund = parse(xml, "fundInfo")
    assert optional_decimal(fund, "na") is None
    assert optional_decimal(fund, "blank") is None
    assert optional_decimal(fund, "notAnElement") is None


# --------------------------------------------------------------- find_element


def test_find_element_accepts_a_raw_xml_string():
    root = find_element(ISSUER_XML, "primaryIssuer")
    assert root is not None
    assert child_text(root, "cik") == "0001961089"


def test_find_element_accepts_an_already_parsed_element(issuer):
    root = find_element(issuer, "issuerAddress")
    assert root is not None
    assert child_text(root, "city") == "LOS ANGELES"


def test_find_element_returns_none_for_a_missing_name_or_a_non_xml_string():
    assert find_element(ISSUER_XML, "notAnElement") is None
    assert find_element("not xml at all", "primaryIssuer") is None


# ------------------------------------------------- footnotes (Form 3/4/5 tier)


def test_get_footnote_ids_joins_on_the_requested_separator(parse):
    xml = """<r><t><footnoteId id="F2"/><footnoteId id="F3"/></t></r>"""
    tag = find_element(parse(xml, "r"), "t")
    assert get_footnote_ids(tag) == "F2,F3"
    assert get_footnote_ids(tag, sep="|") == "F2|F3"


def test_get_footnote_ids_is_empty_when_there_are_none(parse):
    xml = "<r><t><value>plain</value></t></r>"
    assert get_footnote_ids(find_element(parse(xml, "r"), "t")) == ""


def test_value_with_footnotes_returns_bare_footnotes_when_there_is_no_value(parse):
    xml = """<r><expirationDate><footnoteId id="F1"/></expirationDate></r>"""
    assert value_with_footnotes(find_element(parse(xml, "r"), "expirationDate")) == "[F1]"


def test_value_with_footnotes_returns_the_bare_value_when_there_are_no_footnotes(parse):
    xml = "<r><securityTitle><value>Series E Preferred Stock</value></securityTitle></r>"
    assert value_with_footnotes(find_element(parse(xml, "r"), "securityTitle")) == "Series E Preferred Stock"


def test_value_or_footnote_prefers_the_value(parse):
    xml = """<r><c><value>Music</value><footnoteId id="F1"/></c></r>"""
    assert value_or_footnote(find_element(parse(xml, "r"), "c")) == "Music"


def test_value_or_footnote_falls_back_to_footnote_then_footnote_id(parse):
    footnote = "<r><c><footnote id=\"F1\"/></c></r>"
    footnote_id = "<r><c><footnoteId id=\"F9\"/></c></r>"
    assert value_or_footnote(find_element(parse(footnote, "r"), "c")) == "F1"
    assert value_or_footnote(find_element(parse(footnote_id, "r"), "c")) == "F9"


def test_value_or_footnote_of_an_empty_value_element_is_empty_not_a_footnote(parse):
    """An empty `<value/>` still wins over the footnote fallback.

    This is the truthiness trap at its sharpest: under lxml `if value_el` is false and
    the helper would silently return the footnote id instead of the empty value.
    """
    xml = """<r><c><value/><footnoteId id="F1"/></c></r>"""
    assert value_or_footnote(find_element(parse(xml, "r"), "c")) == ""


def test_value_or_footnote_is_none_when_there_is_neither(parse):
    xml = "<r><c/></r>"
    assert value_or_footnote(find_element(parse(xml, "r"), "c")) is None


# ------------------------------------------------------- dict-building helpers


def test_extract_child_text_returns_a_key_value_pair(issuer):
    assert extract_child_text(issuer, "cik", "cik") == ("cik", "0001961089")
    assert extract_child_text(issuer, "phone", "issuerPhoneNumber") == ("phone", "424-313-1550")
    assert extract_child_text(issuer, "missing", "notAnElement") == ("missing", None)


def test_extract_child_value_returns_a_key_value_pair(issuer):
    assert extract_child_value(issuer, "year", "yearOfInc") == ("year", "2022")
    assert extract_child_value(issuer, "missing", "notAnElement") == ("missing", None)


# ------------------------------------------------------- namespaced documents

# SEC serves the current-filings feed as Atom, so every element is
# `{http://www.w3.org/2005/Atom}entry`. This is not a hypothetical: a plain lxml
# `.//entry` matches NOTHING here, so a naive port makes get_current_filings()
# return an empty feed rather than raising (edgartools-07lk.11.3).
ATOM_XML = """<?xml version="1.0" encoding="ISO-8859-1"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>EDGAR Filings</title>
    <entry>
        <title>4 - WILKS LEWIS (0001076463) (Reporting)</title>
        <summary>Filed: 2026-08-18 AccNo: 0001076463-26-000012</summary>
        <updated>2026-08-18T14:09:29-04:00</updated>
    </entry>
    <entry>
        <title>8-K - ACME CORP (0000012345) (Filer)</title>
        <summary>Filed: 2026-08-18 AccNo: 0000012345-26-000003</summary>
        <updated>2026-08-18T14:11:02-04:00</updated>
    </entry>
</feed>
"""

# Two namespaces in one document, so the parent's namespace is the wrong guess for
# some children and only a local-name match finds them.
MIXED_NS_XML = """<?xml version="1.0"?>
<r xmlns="http://example.com/outer" xmlns:x="http://example.com/inner">
    <a>outer-a</a>
    <x:b>inner-b</x:b>
</r>
"""


def test_a_default_namespace_does_not_hide_elements(parse):
    """The whole reason the adapter matches on local names."""
    feed = parse(ATOM_XML, "feed")
    entries = find_all_elements(feed, "entry")

    assert len(entries) == 2
    assert child_text(entries[0], "title") == "4 - WILKS LEWIS (0001076463) (Reporting)"
    assert child_text(entries[1], "summary") == "Filed: 2026-08-18 AccNo: 0000012345-26-000003"
    assert child_text(entries[0], "updated") == "2026-08-18T14:09:29-04:00"


def test_child_text_reaches_into_a_namespaced_element(parse):
    assert child_text(parse(ATOM_XML, "feed"), "title") == "EDGAR Filings"


def test_a_missing_name_is_still_none_in_a_namespaced_document(parse):
    """The namespace fallbacks must not turn a genuine miss into a match."""
    assert child_text(parse(ATOM_XML, "feed"), "notAnElement") is None
    assert find_all_elements(parse(ATOM_XML, "feed"), "notAnElement") == []


def test_elements_are_found_across_several_namespaces(parse):
    """A document mixing namespaces defeats the parent's-namespace shortcut, so this
    is what the local-name scan behind it is for."""
    root = parse(MIXED_NS_XML, "r")
    assert child_text(root, "a") == "outer-a"
    assert child_text(root, "b") == "inner-b"


# ----------------------------------------------------------- find_all_elements


def test_find_all_elements_returns_every_match_in_document_order(parse):
    xml = "<r><a>one</a><b><a>two</a></b><a>three</a></r>"
    found = find_all_elements(parse(xml, "r"), "a")
    assert [_text_of(el) for el in found] == ["one", "two", "three"]


def test_find_all_elements_is_empty_when_there_are_none(parse):
    assert find_all_elements(parse(ATOM_XML, "feed"), "notAnElement") == []


def test_find_all_elements_accepts_a_raw_xml_string():
    assert len(find_all_elements(ATOM_XML, "entry")) == 2
    assert find_all_elements("not xml at all", "entry") == []


# ------------------------------------------------------------------ parse_xml

# `parse_xml` is the lxml-only document entry point the `from_xml(xml: str)`
# classmethods call instead of `BeautifulSoup(xml, "xml")`, so it is not run through
# the dual-backend `parse` fixture. What it owes them is everything bs4 absorbed
# without being asked (edgartools-07lk.11.3).


def test_parse_xml_returns_the_root_element_itself():
    """Not a tree, and not the root's parent — callers read fields straight off it."""
    root = parse_xml(ISSUER_XML)
    assert isinstance(root, etree._Element)
    assert root.tag == "edgarSubmission"
    assert child_text(root, "entityName") == "1685 38th REIT, L.L.C."


def test_parse_xml_tolerates_whitespace_before_the_declaration():
    """bs4 accepted this; bare lxml raises `XML declaration allowed only at the start
    of the document`. Test fixtures and templated documents lead with a newline all
    the time, so a port without this fails on documents that used to work."""
    assert parse_xml("\n    " + ISSUER_XML).tag == "edgarSubmission"
    assert parse_xml("\ufeff" + ISSUER_XML).tag == "edgarSubmission"


def test_parse_xml_ignores_a_stale_encoding_declaration_on_a_str():
    """A `str` was already decoded by whoever produced it, so its declaration is
    stale. Believing it silently mojibakes every non-ASCII entity name — this is
    `Café` read as `CafÃ©`, which no test would notice from a type or a length."""
    xml = '<?xml version="1.0" encoding="ISO-8859-1"?><r><entityName>Café Büro</entityName></r>'
    assert child_text(parse_xml(xml), "entityName") == "Café Büro"


def test_parse_xml_honors_the_encoding_declaration_on_bytes():
    """Undecoded bytes are the one case where the declaration is the only encoding
    information there is, so it is obeyed rather than overridden."""
    xml = '<?xml version="1.0" encoding="ISO-8859-1"?><r><entityName>Café</entityName></r>'
    assert child_text(parse_xml(xml.encode("ISO-8859-1")), "entityName") == "Café"


def test_parse_xml_recovers_from_malformed_markup_exactly_as_bs4_did():
    """`BeautifulSoup(xml, "xml")` parses with `recover=True`, so this has to too.

    SEC's own XML is not always well-formed. AAR CORP's 2004-02-04 Form 4
    (0000001750-04-000011) carries a mangled attribute — the shape reproduced here —
    and bs4 absorbed it for years. A strict parser rejects the whole document, and
    because `ownership_xml_to_html` catches every exception, the failure showed up
    not as an error but as a filing's text turning back into raw markup
    (edgartools-07lk.11.3). Recovery is part of the contract, not a leniency.
    """
    root = parse_xml('<ownershipDocument><documentType>4</documentType>'
                     '<nonDerivativeTable ativeTable><x>y</x></nonDerivativeTable>'
                     '</ownershipDocument>')
    assert local_name(root) == "ownershipDocument"
    assert child_text(root, "documentType") == "4"


def test_parse_xml_leaves_a_non_xml_document_for_the_caller_to_reject():
    """An HTML error page is not a parse failure any more — it is a wrong document.

    It recovers to an `<html>` root, which every dependent's `local_name(root) !=
    ...` check rejects by name. That is a better message than a parse error, and it
    is what bs4 did.
    """
    assert local_name(parse_xml("<html><body>503 Service Unavailable</body>")) == "html"


def test_parse_xml_still_raises_when_there_is_no_markup_to_recover():
    """Recovery has a floor. lxml returns None rather than raising for content with
    no markup at all, and a caller handed None fails several frames later with an
    AttributeError naming the wrong thing — so it is re-raised here."""
    with pytest.raises(etree.XMLSyntaxError):
        parse_xml("Your request rate has exceeded the SEC limit.")
    with pytest.raises(etree.XMLSyntaxError):
        parse_xml("")


def test_parse_xml_keeps_a_namespaced_root_addressable_by_local_name():
    root = parse_xml(ATOM_XML)
    assert child_text(root, "title") == "EDGAR Filings"
    assert len(find_all_elements(root, "entry")) == 2


# --------------------------------------------------- element_text / local_name

# The neutral forms of `.text` and `.tag`, for the dependents that hold an element
# and need to read it rather than search below it (edgartools-07lk.11.3).


def test_element_text_concatenates_the_whole_subtree(parse):
    """lxml's own `.text` stops at the first child element, so a footnote with any
    markup in it would read as the fragment before that markup — a plausible
    string, not an error. This is the trap `element_text` exists to close."""
    xml = "<r><footnote id='F1'>see <i>note</i> below</footnote></r>"
    footnote = find_element(parse(xml, "r"), "footnote")
    assert element_text(footnote) == "see note below"


def test_element_text_does_not_strip(parse):
    """Unlike `child_text`. Callers that want it stripped say so."""
    xml = "<r><a>  padded  </a></r>"
    assert element_text(find_element(parse(xml, "r"), "a")) == "  padded  "


def test_element_text_of_an_empty_element_is_empty_string(parse):
    assert element_text(find_element(parse("<r><a/></r>", "r"), "a")) == ""


def test_local_name_ignores_the_namespace(parse):
    """What a root-element check has to compare against. lxml reports a namespaced
    root as `{http://www.w3.org/2005/Atom}feed`, so comparing `.tag` to `"feed"` is
    a check that fails on exactly the documents that need it most."""
    assert local_name(parse(ATOM_XML, "feed")) == "feed"
    assert local_name(parse(MIXED_NS_XML, "b")) == "b"


def test_local_name_of_an_unnamespaced_element_is_the_tag(parse):
    assert local_name(parse(ISSUER_XML, "primaryIssuer")) == "primaryIssuer"
