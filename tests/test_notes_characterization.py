"""Golden-file characterization of note text/markdown extraction (07lk.11.7).

`notes_output_baseline.json` is what `notes.py` emitted for every note in
`tests/fixtures/notes_html`, generated while the module still ran on
BeautifulSoup and committed unchanged. The bs4 -> lxml port re-derives it.

This output is RAG-facing: it is the text an LLM reads when someone calls
`note.to_context()` or `notes.to_markdown()`. A dropped separator here is not a
cosmetic diff, it is a wrong answer downstream. So the comparison is the emitted
string, exactly -- narrative in both LLM and plain modes, the full per-table
markdown render in both modes, and the aligned plain text of every table.

The corpus is 16 real note TextBlocks from three filers in different industries
(AAPL, KO, JPM), 63 tables in total.

WHAT THE CORPUS DOES *NOT* COVER. Mutating each risky translation to a
deliberately wrong version showed 4 of 8 were exercised by real notes:

    _text_skipping_tables -> text_content()          CAUGHT (16/16)
    _joined_cell_text -> text_content()              CAUGHT (16/16)
    _joined_cell_text -> ' ' separator               CAUGHT (16/16)
    _text_skipping_tables -> splice-and-remove       not caught
    tostring(with_tail=False) -> True                not caught
    _without_tables without tail preservation        not caught
    _inner_html -> tostring(root)                    not caught
    _parse_note_html -> fromstring                   not caught

The tests after the golden-file section supply the missing half. Their expected
values were read off the BeautifulSoup implementation, not reasoned about.

That exercise earned its place twice over: it caught a bug where a note whose
HTML is a *single* <div> lost that div, because `lxml.html.fromstring` roots a
one-element fragment AT the element but invents a wrapping <div> for a
multi-element one -- so there is no way to tell a note's own outermost div from
a synthetic one. `fragments_fromstring` returns the top-level nodes themselves,
which is what bs4's soup children were.
"""
import json
import pathlib

import lxml.html
import pytest

import edgar.xbrl.notes as notes

pytestmark = pytest.mark.fast

REPO = pathlib.Path(__file__).parent.parent
CORPUS = REPO / "tests" / "fixtures" / "notes_html"
BASELINE = CORPUS / "notes_output_baseline.json"


class _StubStatement:
    """Stands in for the Statement `_render_statement_to_markdown` reads.

    `Statement.text()` is not part of this port; the stub returns a fixed string
    so the comparison measures the extraction code and not the statement layer.
    """

    def __init__(self, html: str, plain: str):
        self._html = html
        self._plain = plain

    def text(self, raw_html: bool = False):
        return self._html if raw_html else self._plain


def _note_files():
    return sorted(p for p in CORPUS.glob("*.html"))


@pytest.fixture(scope="module")
def baseline():
    return json.loads(BASELINE.read_text())


def _capture(path: pathlib.Path, expected: dict):
    html = path.read_text()
    stub = _StubStatement(html, expected["_stub_plain"])
    out = {}
    for flag, key in ((True, "llm"), (False, "plain")):
        out[f"narrative_{key}"] = notes._extract_narrative_markdown(html, flag)
        out[f"render_{key}"] = notes._render_statement_to_markdown(stub, path.stem, flag)
    tables = notes._parse_note_html(html).xpath(".//table")
    out["table_count"] = len(tables)
    out["tables_plain"] = [notes._html_table_to_plain_text(t) for t in tables[:8]]
    return out


def test_every_note_is_in_the_baseline(baseline):
    assert sorted(baseline) == [p.name for p in _note_files()]


@pytest.mark.parametrize("path", _note_files(), ids=lambda p: p.stem[:40])
def test_the_emitted_text_matches_the_bs4_baseline(path, baseline):
    expected = baseline[path.name]
    got = _capture(path, expected)
    for key, want in expected.items():
        if key == "_stub_plain":
            continue
        assert got[key] == want, f"{path.name}: {key} changed"


def test_the_baseline_is_not_vacuous(baseline):
    """A baseline of Nones would compare equal to an extractor that returns
    nothing at all."""
    assert sum(v["table_count"] for v in baseline.values()) > 50
    emitted = sum(len(v.get("render_llm") or "") for v in baseline.values())
    assert emitted > 100_000


def test_the_corpus_spans_more_than_one_filer():
    """Different filers nest their note HTML differently; one filer's habits are
    not a characterization."""
    prefixes = {p.name.split("-")[0] for p in _note_files()}
    assert len(prefixes) >= 3, prefixes


# --------------------------------------------------------- the uncovered half


NARRATIVE_CASES = [
    ("text after table", '<div>Lead-in.<table><tr><td>1</td></tr></table>Trailing.</div>',
     "Lead-in. Trailing."),
    ("spaced after table", '<div>A <table><tr><td>1</td></tr></table> B</div>', "A B"),
    ("nested wrapper", '<div>A<div>C<table><tr><td>1</td></tr></table>D</div>B</div>', "A C D B"),
]


@pytest.mark.parametrize("name,html,expected", NARRATIVE_CASES, ids=[c[0] for c in NARRATIVE_CASES])
def test_text_outside_tables_does_not_glue_words(name, html, expected):
    """`get_text(separator=' ')` puts a space between two of bs4's separate
    strings. Removing the table and splicing its tail onto the previous sibling
    -- the obvious way to stop lxml deleting that tail -- merges them into one
    string, and the separator never appears. Both `spaced` cases fail then."""
    assert notes._text_skipping_tables(notes._parse_note_html(html)) == expected


@pytest.mark.parametrize("name,html,expected", [
    ("text after table", '<div>Lead-in.<table><tr><td>1</td></tr></table>Trailing.</div>',
     "<div>Lead-in.Trailing.</div>"),
    ("nested wrapper", '<div>A<div>C<table><tr><td>1</td></tr></table>D</div>B</div>',
     "<div>A<div>CD</div>B</div>"),
], ids=["text after table", "nested wrapper"])
def test_stripping_tables_keeps_the_text_that_followed_them(name, html, expected):
    """The HTML handed to `process_content`. Here the tail MUST be spliced --
    serialization concatenates adjacent strings anyway, so this is what bs4's
    decompose + str(soup) produced. Dropping the tail loses "Trailing." from
    the narrative entirely."""
    stripped = notes._without_tables(notes._parse_note_html(html))
    assert notes._inner_html(stripped).strip() == expected


def test_a_single_element_note_keeps_its_own_wrapper():
    """`fromstring` roots a one-element fragment AT that element; emitting its
    children would drop the note's outermost <div>, which bs4 kept."""
    root = notes._parse_note_html('<div class="note">Only child.</div>')
    assert notes._inner_html(root).strip() == '<div class="note">Only child.</div>'


def test_a_multi_element_note_gains_no_phantom_wrapper():
    """The mirror image: `fromstring` invents a wrapping <div> for a
    multi-element fragment, which bs4 never had."""
    root = notes._parse_note_html('<div>One</div><div>Two</div>')
    assert notes._inner_html(root).strip() == '<div>One</div><div>Two</div>'


def test_serializing_a_table_does_not_absorb_the_following_text():
    """lxml's tostring appends the element's tail by default. That text is
    narrative belonging to the document; bs4's str(tag) never included it, and
    it would be rendered twice -- once inside the table, once as narrative."""
    root = notes._parse_note_html('<div><table><tr><td>1</td></tr></table>TAIL-TEXT</div>')
    table = root.xpath(".//table")[0]
    assert lxml.html.tostring(table, encoding="unicode", with_tail=False) == \
        "<table><tr><td>1</td></tr></table>"
    assert "TAIL-TEXT" in lxml.html.tostring(table, encoding="unicode", with_tail=True)


@pytest.mark.parametrize("html,expected", [
    ('<table><tr><td><span> 1,234 </span><span> </span></td></tr></table>', ["1,234"]),
    ('<table><tr><td><span>Net</span><span>Sales</span></td></tr></table>', ["NetSales"]),
    ('<table><tr><th>H1</th><td>V1</td></tr></table>', ["H1", "V1"]),
], ids=["padded spans", "two words", "th and td"])
def test_cell_text_strips_each_string_and_joins_with_nothing(html, expected):
    """`get_text(strip=True)` with no separator: every string stripped, then
    concatenated. text_content() would keep the padding and give ' 1,234  ',
    and a space separator would give 'Net Sales' -- note that the run-together
    'NetSales' is what bs4 produced, so it is what the port must produce."""
    root = notes._parse_note_html(html)
    cells = root.xpath(".//td | .//th")
    assert [notes._joined_cell_text(c) for c in cells] == expected


def test_unparseable_content_returns_none_rather_than_raising():
    """bs4 built an empty soup for blank input; lxml raises ParserError."""
    assert notes._extract_narrative_markdown("", True) is None
    assert notes._extract_narrative_markdown("   \n ", True) is None
