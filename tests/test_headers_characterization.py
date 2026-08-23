"""Golden-file characterization of ``IndexHeaders.load`` (edgartools-07lk.11.4).

Written while ``headers.py`` still ran on BeautifulSoup, so that the bs4 -> lxml
port could be proved to change nothing. The baseline JSON is the full pydantic
dump of every tracked header fixture, generated from the bs4 implementation and
committed unchanged.

WHY A GOLDEN FILE RATHER THAN FIELD ASSERTIONS. ``tests/test_headers.py`` checks
a handful of fields on two fixtures. A parser swap can move anything -- a
stripped space, a dropped tail, a null where a nested model used to be -- and
field assertions only catch what someone thought to name. The dump catches the
rest, which is the point: the epic's postmortem says Phase 1's only real
regression came from an invisible behavioural contract, not from a coding error.

The five fixtures are not uniform, deliberately. Four are the HTML
``-index-headers.html`` form, where the SGML header sits inside an HTML comment.
``form4.index-headers.html`` is bare SGML with no comment at all, and the loader
raises ``IndexError`` on it -- see the test at the bottom, which pins that as it
currently is rather than as it should be.
"""
import json
import pathlib

import pytest

from edgar.headers import IndexHeaders

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
HEADER_DIR = REPO / "data" / "headers"
BASELINE = REPO / "tests" / "fixtures" / "headers" / "index_headers_baseline.json"

# The one fixture whose content is not the format the loader parses.
BARE_SGML = "form4.index-headers.html"


def _baseline():
    return json.loads(BASELINE.read_text())


def _fixtures():
    return sorted(HEADER_DIR.glob("*.html"))


def test_the_corpus_and_baseline_line_up():
    """A renamed or deleted fixture must fail loudly, not shrink the test silently."""
    assert BASELINE.exists(), f"missing baseline {BASELINE}"
    on_disk = {p.name for p in _fixtures()}

    assert on_disk, f"no header fixtures under {HEADER_DIR}"
    assert on_disk == set(_baseline()), (
        "header fixtures and baseline have diverged; regenerate the baseline "
        "deliberately rather than letting a fixture drop out of coverage"
    )


@pytest.mark.parametrize("name", sorted(set(_baseline()) - {BARE_SGML}))
def test_parsed_headers_match_the_baseline_exactly(name):
    """Full model dump, not selected fields.

    Compared as parsed JSON rather than as text so the failure message names the
    differing key instead of showing two 1KB strings.
    """
    expected = _baseline()[name]
    assert "__error__" not in expected, f"{name} is an error fixture; test it explicitly"

    parsed = IndexHeaders.load((HEADER_DIR / name).read_text())
    actual = json.loads(parsed.model_dump_json())

    assert actual == expected


@pytest.mark.parametrize("name", sorted(set(_baseline()) - {BARE_SGML}))
def test_each_baseline_fixture_actually_carries_data(name):
    """Guards the comparison above from passing on emptiness.

    If a future parser returned a model with every field None, the dump would
    still equal a baseline captured from that same broken parser. These are the
    fields the loader exists to produce, so they must be populated for the
    equality check to mean anything.
    """
    expected = _baseline()[name]

    assert expected["form"], f"{name} has no form"
    assert expected["accession_number"], f"{name} has no accession number"
    assert expected["filing_date"], f"{name} has no filing date"


def test_bare_sgml_without_an_html_comment_still_raises():
    """Characterization, not endorsement.

    This fixture is raw SGML header text with no enclosing HTML comment, and
    ``load`` indexes ``[0]`` into the comment list without checking it. The
    result is a bare ``IndexError`` rather than a message naming the problem.

    Pinned so the lxml port is shown not to change it. No live path reaches this:
    ``Filing.index_headers`` fetches the real ``-index-headers.html``, which is
    always comment-wrapped, and no test references this fixture. Improving the
    error is tracked separately -- doing it here would mean a behaviour change
    riding along inside a parser port, which is exactly what makes ports hard to
    review.
    """
    with pytest.raises(IndexError):
        IndexHeaders.load((HEADER_DIR / BARE_SGML).read_text())


class TestTheContractsTheParserSwapHadToPreserve:
    """Edge cases where lxml and BeautifulSoup do NOT agree by default.

    Found by running both parsers side by side over synthetic inputs rather than
    by reading the migration notes: the epic's gotcha list predicted that an
    unterminated comment would make lxml see an empty document, and on this file
    it does the opposite — libxml2 recovers and returns the comment. Predictions
    about parser behaviour are worth exactly what measuring them costs.
    """

    def test_empty_input_raises_indexerror_not_parsererror(self):
        """bs4 returned an empty soup; lxml raises ParserError on empty input.

        Left as IndexError so the swap is not silently also an exception-type
        change for anyone catching it.
        """
        with pytest.raises(IndexError):
            IndexHeaders.load("")

    def test_whitespace_only_input_raises_indexerror_too(self):
        with pytest.raises(IndexError):
            IndexHeaders.load("   \n  ")

    def test_a_comment_before_the_root_element_is_still_found(self):
        """bs4 searched the whole document; an element-rooted xpath would not.

        Today's SEC files put the comment inside <head>, so this passes either
        way and would not have caught the mistake — it is here because the fix
        (walking getroottree()) is invisible and easy to 'simplify' away later.
        """
        source = (HEADER_DIR / "23AndMe.index-headers.html").read_text()
        start, end = source.index("<!--"), source.index("-->") + 3
        relocated = source[start:end] + "\n<HTML><HEAD><TITLE>t</TITLE></HEAD></HTML>"

        assert IndexHeaders.load(relocated).form == "8-K"
        # and it parses to the same thing as when the comment sits inside <head>
        assert (IndexHeaders.load(relocated).model_dump_json()
                == IndexHeaders.load(source).model_dump_json())
