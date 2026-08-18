"""Characterization tests pinning the `edgar.xmltools` contract across the lxml port.

`edgar/xmltools.py` is the shared XML helper layer for 12 parsers (Form D, Form 144,
Form 3/4/5 ownership, 13F, Schedule 13D/G, muni advisors, EFFECT, filing summaries).
Bead edgartools-07lk.11.2 moves it from BeautifulSoup to `lxml.etree` with unchanged
signatures, so ~350 call sites keep compiling whether or not their behavior survives.

That is the risk these tests exist for. Every difference below was verified against the
bs4 and lxml versions installed in this repo, and every one of them fails *silently* —
a naive port returns `None` or `""` where it used to return a value, and the parsers go
on to build objects full of empty fields rather than raising.

    truthiness  bs4 `bool(Tag)` is True even for a childless `<c/>`; lxml
                `bool(Element)` is False even for `<b>text</b>` (and warns).
                `child_text`/`child_value`/`value_or_footnote`/`value_with_footnotes`
                all guard with a bare `if el`, so a direct port makes every one of
                them return None. Use `el is not None`.

    find depth  bs4 `.find()` searches all descendants; lxml `.find()` searches
                direct children only. Descendant search needs `.//name`.

    .text       bs4 `.text` concatenates all descendant text; lxml `.text` is only
                the text before the first child element. Use `"".join(itertext())`.

    whitespace  the two backends do not agree on interior whitespace between
                elements, which shows up in any helper returning subtree text.

The assertions call the helpers, never the backend, so they must hold unchanged after
the port. `_root` below is the single line that changes.
"""
from decimal import Decimal

from bs4 import BeautifulSoup

from edgar.xmltools import (
    child_text,
    child_texts,
    child_value,
    extract_child_text,
    extract_child_value,
    find_element,
    get_footnote_ids,
    optional_decimal,
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


def _root(xml: str, name: str):
    """Parse `xml` and return the element named `name`.

    THE ONE LINE THAT CHANGES when xmltools moves to lxml (edgartools-07lk.11.2).
    Everything below asserts on the helpers' return values, not on the backend.
    """
    return BeautifulSoup(xml, features="xml").find(name)


def issuer():
    return _root(ISSUER_XML, "primaryIssuer")


# ---------------------------------------------------------------- child_text


def test_child_text_reads_an_element_that_has_no_element_children():
    """The truthiness trap, in the single most-called helper.

    `<cik>` holds text and nothing else, so it has zero *element* children. lxml
    considers such an element false, and `child_text`'s `if el` guard would drop it.
    """
    assert child_text(issuer(), "cik") == "0001961089"
    assert child_text(issuer(), "issuerPhoneNumber") == "424-313-1550"


def test_child_text_searches_descendants_not_only_direct_children():
    """`<city>` is a grandchild of `<primaryIssuer>`, and bs4 `.find()` reaches it.

    lxml `.find("city")` would not — it needs `.//city`. Callers rely on the reach:
    see edgar/_party.py:157-162, which only descends to `<issuerAddress>` explicitly
    because the address fields are ambiguous, not because the helper cannot get there.
    """
    assert child_text(issuer(), "city") == "LOS ANGELES"
    assert child_text(issuer(), "zipCode") == "90067"


def test_child_text_concatenates_all_descendant_text():
    """`.text` on a container returns the whole subtree's text, not the head text.

    lxml's `.text` would return only the whitespace before `<street1>`, which strips
    to `""` — a silent empty string rather than an error.
    """
    address = child_text(issuer(), "issuerAddress")
    for fragment in ("2029 CENTURY PARK EAST", "SUITE 1370", "LOS ANGELES", "CA", "90067"):
        assert fragment in address


def test_child_text_preserves_interior_whitespace_exactly():
    """Pins the interior spacing of concatenated text, which the backends disagree on.

    bs4 and lxml produce different separators between sibling elements' text. Only the
    outer edges are stripped, so any change here reaches callers that compare or hash
    these strings.
    """
    xml = "<r><d>  <e>Y</e>  <f>Z</f> </d></r>"
    assert child_text(_root(xml, "r"), "d") == "Y Z"


def test_child_text_of_an_empty_element_is_empty_string_not_none():
    """`<entityType/>` yields `""`. The distinction matters: `None` means *absent*."""
    assert child_text(issuer(), "entityType") == ""


def test_child_text_of_a_missing_element_is_none():
    assert child_text(issuer(), "notAnElement") is None


def test_child_text_ignores_comments():
    xml = "<r><b><!-- editorial note --><c>X</c></b></r>"
    assert child_text(_root(xml, "r"), "b") == "X"


def test_child_text_strips_surrounding_whitespace():
    xml = "<r><a>\n    padded\n  </a></r>"
    assert child_text(_root(xml, "r"), "a") == "padded"


# --------------------------------------------------------------- child_value


def test_child_value_unwraps_the_nested_value_element():
    """`child_value` reaches through a wrapper to its `<value>`, `child_text` does not."""
    assert child_value(issuer(), "yearOfInc") == "2022"
    # child_text on the same wrapper returns the whole subtree instead, separator included.
    assert child_text(issuer(), "yearOfInc") == "true\n2022"


def test_child_value_returns_the_default_when_the_child_is_missing():
    assert child_value(issuer(), "notAnElement") is None
    assert child_value(issuer(), "notAnElement", default_value="fallback") == "fallback"


def test_child_value_of_a_present_child_without_a_value_element_is_empty():
    """Present-but-valueless is `""`, distinct from the missing-child default.

    A caller passing `default_value` does NOT get it here — the child exists.
    """
    xml = "<r><child>bare text</child></r>"
    assert child_value(_root(xml, "r"), "child", default_value="fallback") == ""


def test_child_value_appends_footnote_references():
    xml = """<r>
        <underlyingSecurityTitle>
            <value>Class B Common Stock</value>
            <footnoteId id="F2"/>
            <footnoteId id="F3"/>
        </underlyingSecurityTitle>
    </r>"""
    assert child_value(_root(xml, "r"), "underlyingSecurityTitle") == "Class B Common Stock [F2,F3]"


# --------------------------------------------------------------- child_texts


def test_child_texts_returns_every_match_in_document_order():
    xml = """<r>
        <relationship>Executive Officer</relationship>
        <relationship>Director</relationship>
        <relationship>Promoter</relationship>
    </r>"""
    assert child_texts(_root(xml, "r"), "relationship") == [
        "Executive Officer",
        "Director",
        "Promoter",
    ]


def test_child_texts_of_a_missing_element_is_an_empty_list():
    assert child_texts(issuer(), "notAnElement") == []


def test_child_texts_does_not_strip():
    """Unlike `child_text`, `child_texts` returns raw text. Pinned because callers
    downstream do their own stripping and would double-strip or stop stripping."""
    xml = "<r><a> spaced </a></r>"
    assert child_texts(_root(xml, "r"), "a") == [" spaced "]


# ----------------------------------------------------------- optional_decimal


def test_optional_decimal_parses_zero_as_a_decimal():
    """`"0"` must not be confused with absence — SEC fund tables are full of real zeros."""
    xml = "<fundInfo><totAssets>0</totAssets><amt>0.018</amt></fundInfo>"
    fund = _root(xml, "fundInfo")
    assert optional_decimal(fund, "totAssets") == Decimal("0")
    assert optional_decimal(fund, "amt") == Decimal("0.018")


def test_optional_decimal_treats_na_and_absence_and_emptiness_as_none():
    xml = "<fundInfo><na>N/A</na><blank/></fundInfo>"
    fund = _root(xml, "fundInfo")
    assert optional_decimal(fund, "na") is None
    assert optional_decimal(fund, "blank") is None
    assert optional_decimal(fund, "notAnElement") is None


# --------------------------------------------------------------- find_element


def test_find_element_accepts_a_raw_xml_string():
    root = find_element(ISSUER_XML, "primaryIssuer")
    assert root is not None
    assert child_text(root, "cik") == "0001961089"


def test_find_element_accepts_an_already_parsed_element():
    root = find_element(issuer(), "issuerAddress")
    assert root is not None
    assert child_text(root, "city") == "LOS ANGELES"


def test_find_element_returns_none_for_a_missing_name_or_a_non_xml_string():
    assert find_element(ISSUER_XML, "notAnElement") is None
    assert find_element("not xml at all", "primaryIssuer") is None


# ------------------------------------------------- footnotes (Form 3/4/5 tier)


def test_get_footnote_ids_joins_on_the_requested_separator():
    xml = """<r><t><footnoteId id="F2"/><footnoteId id="F3"/></t></r>"""
    tag = find_element(_root(xml, "r"), "t")
    assert get_footnote_ids(tag) == "F2,F3"
    assert get_footnote_ids(tag, sep="|") == "F2|F3"


def test_get_footnote_ids_is_empty_when_there_are_none():
    xml = "<r><t><value>plain</value></t></r>"
    assert get_footnote_ids(find_element(_root(xml, "r"), "t")) == ""


def test_value_with_footnotes_returns_bare_footnotes_when_there_is_no_value():
    xml = """<r><expirationDate><footnoteId id="F1"/></expirationDate></r>"""
    assert value_with_footnotes(find_element(_root(xml, "r"), "expirationDate")) == "[F1]"


def test_value_with_footnotes_returns_the_bare_value_when_there_are_no_footnotes():
    xml = "<r><securityTitle><value>Series E Preferred Stock</value></securityTitle></r>"
    assert value_with_footnotes(find_element(_root(xml, "r"), "securityTitle")) == "Series E Preferred Stock"


def test_value_or_footnote_prefers_the_value():
    xml = """<r><c><value>Music</value><footnoteId id="F1"/></c></r>"""
    assert value_or_footnote(find_element(_root(xml, "r"), "c")) == "Music"


def test_value_or_footnote_falls_back_to_footnote_then_footnote_id():
    footnote = "<r><c><footnote id=\"F1\"/></c></r>"
    footnote_id = "<r><c><footnoteId id=\"F9\"/></c></r>"
    assert value_or_footnote(find_element(_root(footnote, "r"), "c")) == "F1"
    assert value_or_footnote(find_element(_root(footnote_id, "r"), "c")) == "F9"


def test_value_or_footnote_of_an_empty_value_element_is_empty_not_a_footnote():
    """An empty `<value/>` still wins over the footnote fallback.

    This is the truthiness trap at its sharpest: under lxml `if value_el` is false and
    the helper would silently return the footnote id instead of the empty value.
    """
    xml = """<r><c><value/><footnoteId id="F1"/></c></r>"""
    assert value_or_footnote(find_element(_root(xml, "r"), "c")) == ""


def test_value_or_footnote_is_none_when_there_is_neither():
    xml = "<r><c/></r>"
    assert value_or_footnote(find_element(_root(xml, "r"), "c")) is None


# ------------------------------------------------------- dict-building helpers


def test_extract_child_text_returns_a_key_value_pair():
    assert extract_child_text(issuer(), "cik", "cik") == ("cik", "0001961089")
    assert extract_child_text(issuer(), "phone", "issuerPhoneNumber") == ("phone", "424-313-1550")
    assert extract_child_text(issuer(), "missing", "notAnElement") == ("missing", None)


def test_extract_child_value_returns_a_key_value_pair():
    assert extract_child_value(issuer(), "year", "yearOfInc") == ("year", "2022")
    assert extract_child_value(issuer(), "missing", "notAnElement") == ("missing", None)
