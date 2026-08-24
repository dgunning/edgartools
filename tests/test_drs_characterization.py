"""Characterization of the DRS underlying-form detector's bs4 -> lxml port
(edgartools-07lk.11.9.6).

`drs_baseline.json` is what `_detect_underlying_form` produced over seven real
filings, captured while the module still ran on BeautifulSoup. Two things are
pinned per file: the (form_type, amendment) tuple, and a fingerprint of the
text the tuple was derived from -- sha256 plus char and word counts plus both
ends, since the corpus is 15MB and committing the text itself would not be
sensible.

THE CORPUS IS DELIBERATELY NOT DRS FILINGS. `test_drs.py` already covers the
regexes, with twelve hand-written one-line strings. What those cannot cover is
the only thing this port changes: how the text those regexes run against is
extracted. So the corpus is real filing HTML of the shapes a DRS wraps -- a
genuine S-1, three 8-Ks from 2001/2004/2008 (the deeply nested layout-table
era), a foreign private issuer's 20-F, and two modern iXBRL filings.

WHAT MAKES THIS PORT SUBTLE. `get_text(separator=' ', strip=True)` is the
third of bs4's three text behaviours, and it is the one with no lxml
equivalent at all: strip each string, drop the empties, join the rest with a
single space. `text_content()` is not it -- that joins with nothing, so
"FORM" and "S-1" in adjacent cells become "FORMS-1" and the detector returns
Unknown. The EDGE inputs below each fail one specific mistranslation.

Two of them are not stylistic but functional, and they are why this file is
longer than a six-line port deserves:

  * A `<style>` or `<script>` block naming a different form. bs4 classified
    that text as Stylesheet/Script and left it out of get_text(); lxml
    includes it, so the detector would read the CSS and report the wrong form.
  * 300-deep nesting. libxml2 discards below depth 256 unless huge_tree is
    set, and bs4 never did -- so the cover page of a 2000s filing can vanish
    entirely. See edgartools-xqvr.
"""
import hashlib
import json
import pathlib

import pytest

from edgar.offerings.prospectus.drs import _detect_underlying_form, _html_to_text

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
FIX = REPO / "tests" / "fixtures"
BASELINE = FIX / "drs_baseline.json"

CORPUS = [
    "html/abnb/s1/abnb-s1-2020-11-16.html",
    "html/1013243/8k/1013243-8-k-2001-03-30.html",
    "html/1100748/8k/1100748-8-k-2004-09-30.html",
    "html/786947/8k/786947-8-k-2008-06-30.html",
    "html/1018735/20f/1018735-20-f-2025-06-03.html",
    "html/aapl/10k/aapl-10-k-2024-11-01.html",
    "html/ibm/10q/ibm-10-q-2025-07-24.html",
]

_PAD = "padding sentence. " * 500  # ~9000 chars, past the 8000-char cover window

EDGE = {
    "empty": "",
    "whitespace": "   \n\t  ",
    "bare-fragment": "<center>FORM S-1 REGISTRATION STATEMENT</center>",
    # get_text(' ', strip=True) joins with a SPACE. text_content() joins with
    # nothing, which glues these two cells into "FORMS-1" and detects nothing.
    "form-split-across-cells":
        "<html><body><table><tr><td>FORM</td><td>S-1</td></tr></table></body></html>",
    "form-split-across-block-tags":
        "<html><body><div>FORM</div><div>F-1</div><div>REGISTRATION STATEMENT</div></body></html>",
    # A stylesheet naming a DIFFERENT form. bs4 never saw it; lxml does, and
    # <style> comes first, so the detector would answer S-4 instead of S-1.
    "style-block-names-another-form":
        "<html><head><style>.x{content:'FORM S-4'}</style></head>"
        "<body>FORM S-1 REGISTRATION STATEMENT</body></html>",
    "script-block-names-another-form":
        "<html><head><script>var t='FORM S-4 REGISTRATION STATEMENT';</script></head>"
        "<body>FORM S-1 REGISTRATION STATEMENT</body></html>",
    # bs4's get_text() skipped comments too.
    "comment-names-another-form":
        "<html><body><!-- FORM S-4 REGISTRATION STATEMENT -->"
        "FORM S-1 REGISTRATION STATEMENT</body></html>",
    # libxml2 discards below depth 256 without huge_tree; bs4 never did.
    "cover-page-nested-300-deep":
        "<html><body>" + "<div>" * 300 + "FORM F-1 REGISTRATION STATEMENT"
        + "</div>" * 300 + "</body></html>",
    # lxml refuses a str carrying an encoding declaration.
    "xml-prolog":
        '<?xml version="1.0" encoding="utf-8"?>'
        "<html><body>FORM S-3 REGISTRATION STATEMENT</body></html>",
    "nbsp-between-words":
        "<html><body>FORM&nbsp;S-4&nbsp;REGISTRATION STATEMENT</body></html>",
    "numeric-entity":
        "<html><body>FORM&#160;20-F ANNUAL REPORT</body></html>",
    # A comment SPLITTING a run of text. Dropping comments at parse time merges
    # the two strings into one node, and one node is stripped once rather than
    # twice, so the interior spacing survives where bs4 collapsed it.
    "comment-splits-a-form-name":
        "<html><body><p>FORM <!-- filer note --> S-1 REGISTRATION STATEMENT</p></body></html>",
    # The cover text is the script's TAIL. Removing the subtree tail-and-all
    # deletes the cover page and the detector answers Unknown.
    "script-followed-by-the-cover-text":
        "<html><body><script>var x=1;</script>FORM F-4 REGISTRATION STATEMENT</body></html>",
    "amendment-and-form":
        "<html><body><p>Amendment No. 7</p><p>FORM S-1</p></body></html>",
    # Only the first 8000 characters are examined. If extraction inserts or
    # drops whitespace, this boundary moves and the answer changes.
    "form-just-past-the-cover-window":
        f"<html><body><p>{_PAD}</p><p>FORM S-4 REGISTRATION STATEMENT</p></body></html>",
    "form-just-inside-the-cover-window":
        "<html><body><p>" + "padding sentence. " * 300
        + "</p><p>FORM S-4 REGISTRATION STATEMENT</p></body></html>",
}


def fingerprint(text):
    return {
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "chars": len(text),
        "words": len(text.split()),
        "head": text[:200],
        "tail": text[-200:],
    }


@pytest.fixture(scope="module")
def baseline():
    return json.loads(BASELINE.read_text())


# ------------------------------------------------------------- golden file


@pytest.mark.parametrize("rel", CORPUS, ids=lambda r: r.split("/")[-1])
def test_real_filings_match_the_bs4_baseline(rel, baseline):
    html = (FIX / rel).read_text(encoding="utf-8", errors="replace")
    form, amendment = _detect_underlying_form(html)
    expected = baseline[f"corpus::{rel}"]
    assert [form, amendment] == expected["detected"]
    assert fingerprint(_html_to_text(html)) == expected["text"]


@pytest.mark.parametrize("name", sorted(EDGE), ids=lambda n: n)
def test_edge_inputs_match_the_bs4_baseline(name, baseline):
    entry = baseline[f"EDGE::{name}"]
    form, amendment = _detect_underlying_form(EDGE[name])
    assert [form, amendment] == entry["detected"]
    assert fingerprint(_html_to_text(EDGE[name])) == entry["text"]


def test_the_baseline_is_not_vacuous(baseline):
    """A detector that answered Unknown for everything would match a baseline
    of Unknowns, and an extractor that returned '' would match a baseline of
    empty hashes."""
    detected = [v["detected"][0] for v in baseline.values() if "detected" in v]
    assert len([d for d in detected if d != "Unknown"]) == 15
    chars = sum(v["text"]["chars"] for v in baseline.values() if "text" in v)
    assert chars > 2_000_000


# ----------------------------------------------- the traps, stated directly


def test_the_separator_is_a_space_not_nothing():
    """`get_text(' ', strip=True)`, not `text_content()`. A cover page that
    puts FORM and S-1 in adjacent cells -- which is how filers typeset it --
    reads as "FORMS-1" if the strings are joined with nothing, and the
    detector returns Unknown."""
    assert _detect_underlying_form(EDGE["form-split-across-cells"])[0] == "S-1"
    assert "FORM S-1" in _html_to_text(EDGE["form-split-across-cells"])


@pytest.mark.parametrize("key,tag", [("style-block-names-another-form", "style"),
                                     ("script-block-names-another-form", "script")])
def test_a_stylesheet_naming_another_form_is_not_believed(key, tag):
    """bs4 classified this text as Stylesheet/Script and left it out of
    get_text(). lxml includes it, and it comes FIRST, so the detector would
    report S-4 for a document whose cover page says S-1."""
    assert _detect_underlying_form(EDGE[key])[0] == "S-1"
    assert "S-4" not in _html_to_text(EDGE[key])


def test_a_comment_naming_another_form_is_not_believed():
    assert _detect_underlying_form(EDGE["comment-names-another-form"])[0] == "S-1"


def test_the_text_a_comment_interrupts_is_rejoined_the_way_bs4_rejoined_it():
    """Comments are kept in the tree on purpose. Dropping them at parse time
    merges the strings either side into a single node, and a single node is
    stripped once rather than twice -- so `FORM <!--x--> S-1` would keep its
    interior padding where bs4 collapsed it to one space."""
    assert _html_to_text(EDGE["comment-splits-a-form-name"]) == \
        "FORM S-1 REGISTRATION STATEMENT"


def test_the_text_after_a_script_is_not_deleted_with_it():
    """`with_tail=False`. A filer that opens the body with a script tag puts
    the cover page in that script's tail; removing the subtree tail-and-all
    takes the cover page with it."""
    assert _detect_underlying_form(EDGE["script-followed-by-the-cover-text"])[0] == "F-4"


def test_a_cover_page_nested_300_deep_is_still_read():
    """libxml2 discards everything below depth 256 unless huge_tree is set --
    silently. bs4 never did. See edgartools-xqvr."""
    assert _detect_underlying_form(EDGE["cover-page-nested-300-deep"])[0] == "F-1"


def test_an_encoding_declaration_does_not_raise():
    assert _detect_underlying_form(EDGE["xml-prolog"])[0] == "S-3"


def test_only_the_first_8000_characters_are_examined():
    """Pinned because extraction whitespace moves this boundary: a translation
    that inserts a space per tag pushes the form name out of the window."""
    assert _detect_underlying_form(EDGE["form-just-inside-the-cover-window"])[0] == "S-4"
    assert _detect_underlying_form(EDGE["form-just-past-the-cover-window"])[0] == "Unknown"


@pytest.mark.parametrize("content", ["", "   \n\t  "])
def test_blank_input_answers_unknown_rather_than_raising(content):
    """bs4 built an empty soup; lxml raises ParserError on blank input."""
    assert _detect_underlying_form(content) == ("Unknown", None)
    assert _html_to_text(content) == ""
