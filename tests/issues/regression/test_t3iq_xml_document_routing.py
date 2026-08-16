"""
Regression test for edgartools-t3iq: FilingSGML.text() routed XML instances through the
HTML renderer, which stripped the tags that carry the meaning and took ~1.5 hours on a
large instance (reported by M. Gruening).

The misrouting came from `is_probably_html()`, which asks whether '<p>' / '<div' / '<span'
appears ANYWHERE in the string. Inside a 143MB NPORT instance one such substring is a
certainty, so the whole document was classified as HTML and walked node by node
(0001193125-25-295554: 142,667,189 chars, ~1.5h -> ~2s).

Routing is now decided by `is_xml_document()`, which requires BOTH an XML declaration and
a root element that is not <html>. Both halves are load-bearing — the tests below pin each
one against the real filing that motivated it:

  * declaration alone is not enough  -> inline-XBRL 10-Ks open with <?xml ...?> then <html>
  * root element alone is not enough -> 1994 filings open with the SGML marker <PAGE>

What text() RETURNS for unrenderable XML is unchanged: the XML verbatim. Rendering these
needs the SEC's XSLT endpoint, which FilingSGML has no network access for (see the
edgar/sgml/text_extraction.py module docstring). Only the routing changed.
"""

import pytest

from edgar.sgml.text_extraction import is_xml_document, primary_document_text, root_element_name

# Shapes taken from real filings, trimmed to the prolog plus a token of body.
IXBRL_10K = (
    "<?xml version='1.0' encoding='ASCII'?>\n"
    "<!--XBRL Document Created with the Workiva Platform-->\n"
    "<!--Copyright 2024 Workiva-->\n"
    '<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body><p>UNITED STATES</p></body></html>'
)
NPORT_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">'
    "<invstOrSec><name>Some Bond</name><pctVal>1.5</pctVal></invstOrSec>"
    "</edgarSubmission>"
)
PREFIXED_ROOT_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<twe:edgarSubmission xmlns:com="http://www.sec.gov/edgar/common">'
    "<twe:headerData/></twe:edgarSubmission>"
)
LEGACY_FIXED_WIDTH = "<PAGE>\nDRAFT                          BLACK HILLS CORPORATION\n<TABLE>\n<S>  <C>\n</TABLE>\n"
DOCTYPE_HTML = '<!DOCTYPE html>\n<html><body><p>hello</p></body></html>'


# ── Root element detection ─────────────────────────────────────────────────

@pytest.mark.fast
@pytest.mark.parametrize(
    "content,expected",
    [
        (IXBRL_10K, "html"),
        (NPORT_XML, "edgarSubmission"),
        (PREFIXED_ROOT_XML, "edgarSubmission"),  # namespace prefix dropped
        (LEGACY_FIXED_WIDTH, "PAGE"),
        (DOCTYPE_HTML, "html"),
        ("SECURITIES AND EXCHANGE COMMISSION\n   plain text, no markup\n", None),
        ("", None),
    ],
)
def test_root_element_name(content, expected):
    assert root_element_name(content) == expected


# ── The two load-bearing halves of is_xml_document ─────────────────────────

@pytest.mark.fast
def test_ixbrl_is_not_xml_despite_declaration():
    """An XML declaration does not mean 'not HTML'. If this regresses, every modern
    10-K stops rendering and text() returns raw iXBRL markup."""
    assert not is_xml_document(IXBRL_10K)


@pytest.mark.fast
def test_legacy_page_marker_is_not_an_xml_root():
    """<PAGE> reads as a root element named PAGE. If this regresses, historic filings
    are returned verbatim and their page markers stop being stripped."""
    assert not is_xml_document(LEGACY_FIXED_WIDTH)


@pytest.mark.fast
@pytest.mark.parametrize("content", [NPORT_XML, PREFIXED_ROOT_XML])
def test_real_xml_instances_are_detected(content):
    assert is_xml_document(content)


@pytest.mark.fast
@pytest.mark.parametrize("content", ["", None, "plain text with no markup at all"])
def test_non_markup_is_not_xml(content):
    assert not is_xml_document(content)


# ── Routing through primary_document_text ──────────────────────────────────

@pytest.mark.fast
def test_xml_instance_is_returned_verbatim_not_tag_stripped():
    """The correctness half: <invstOrSec> content is meaningless once the tags that
    label it are gone, so the XML must survive intact."""
    out = primary_document_text("NPORT-P", NPORT_XML)
    assert out == NPORT_XML
    assert "<invstOrSec>" in out
    assert "<pctVal>1.5</pctVal>" in out


@pytest.mark.fast
def test_ixbrl_still_renders_to_text():
    out = primary_document_text("10-K", IXBRL_10K)
    assert "UNITED STATES" in out
    assert "<html" not in out
    assert "<p>" not in out


@pytest.mark.fast
def test_legacy_page_markers_still_stripped():
    out = primary_document_text("PRE 14A", LEGACY_FIXED_WIDTH)
    assert "<PAGE>" not in out
    assert "BLACK HILLS CORPORATION" in out


@pytest.mark.fast
def test_xml_routing_does_not_scan_the_whole_document():
    """Guards the performance half. A large XML instance carrying an HTML-looking
    substring must still route as XML — that substring is what made the 143MB NPORT
    take ~1.5 hours. Kept small enough to stay a fast test."""
    big = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">'
        + "<invstOrSec><name>Bond</name><desc>see <p> note</desc></invstOrSec>" * 2000
        + "</edgarSubmission>"
    )
    assert "<p>" in big  # the substring that fooled is_probably_html
    assert is_xml_document(big)
    assert primary_document_text("NPORT-P", big) == big


# ── The real filings from the report ───────────────────────────────────────

@pytest.mark.network
@pytest.mark.parametrize(
    "accession,form",
    [("0000002554-26-000006", "X-17A-5"), ("0000002110-26-000003", "24F-2NT")],
)
def test_reported_xml_forms_route_as_xml(accession, form):
    from edgar import find

    text = find(accession).sgml().text()
    assert is_xml_document(text)
    # Verbatim, not tag-stripped: the closing root tag survives.
    assert text.rstrip().endswith(">")


@pytest.mark.network
def test_large_nport_instance_is_not_walked_as_html():
    """0001193125-25-295554: 142,667,189 chars of <invstOrSec>. Took ~1.5 hours before
    the routing fix. The assertion is the shape of the output, not a wall-clock bound —
    a tag-stripped result is the failure this pins."""
    from edgar import find

    text = find("0001193125-25-295554").sgml().text()
    assert root_element_name(text) == "edgarSubmission"
    assert "<invstOrSec>" in text
