"""
Regression test for edgartools-puhs: FilingSGML.text() passed the legacy SGML
financial-data-schedule dialect straight through to the caller, so pre-1997 filings
came back with <TABLE>, <CAPTION>, <S>, <C> and <F1> embedded in their text
(reported by M. Gruening; Filer Manual vol 2 sections 5.2.1.3, 5.2.1.4, 5.2.2).

The constraint that shapes this fix: these documents ARE their fixed-width layout, and
the branch that returns them promises to preserve it. So nothing may change the width of
a line carrying data.

  * <TABLE>, </TABLE>, <CAPTION> and the <S>/<C> column-type row each occupy a whole
    line -> drop the line, no column moves.
  * Footnote refs are inline in cell data ("3,615<F2>") -> rewrite, don't delete.
    <F2> becomes [F2]: only the delimiters change, so it is width-neutral for every
    footnote number. Dropping the F (-> [2]) would shrink every reference by one
    character and shift the rest of the line.

The patterns are deliberately tight. 1990s filings use a bare "<" as a less-than sign,
and blanket angle-bracket deletion would eat real content.
"""

import re

import pytest

from edgar.sgml.text_extraction import primary_document_text, strip_sgml_dialect_markup

# Shape taken from 0000003673-94-000020 (1994 10-K, Monongahela Power generating table).
LEGACY_TABLE = """                            - 8 -
<TABLE>
<CAPTION>
                                   System-Owned Stations
Station             Units    Total     gahela  Edison    Penn   Commenced (b)

Coal-fired:
     <S>             <C>     <C>       <C>     <C>      <C>        <C>
     Albright        3       292       292      -        -         1952
</TABLE>
"""

# Shape taken from 0000012400-94-000008 (1994 PRE 14A), footnote refs inline in data.
LEGACY_FOOTNOTES = """        NAME OF BENEFICIAL OWNER            OF BENEFICIAL OWNERSHIP   <F1>
        Glenn C. Barber                     2,687
        Bruce B. Brundage                   3,615<F2>
        Dale E. Clement                     9,597
        Michael B. Enzi                       998<F3>
"""


# ── Whole-line markers are dropped ─────────────────────────────────────────

@pytest.mark.fast
@pytest.mark.parametrize("marker", ["<TABLE>", "</TABLE>", "<CAPTION>", "<table>", "</Table>"])
def test_structure_markers_on_their_own_line_are_dropped(marker):
    out = strip_sgml_dialect_markup(f"before\n{marker}\nafter\n")
    assert out == "before\nafter\n"


@pytest.mark.fast
@pytest.mark.parametrize(
    "row",
    [
        "     <S>             <C>     <C>       <C>",
        "<S><C>",
        "  <s>   <c>   <c>  ",
    ],
)
def test_column_type_rows_are_dropped(row):
    out = strip_sgml_dialect_markup(f"header\n{row}\ndata\n")
    assert out == "header\ndata\n"


@pytest.mark.fast
def test_a_line_mixing_markers_with_data_is_not_dropped():
    """Only rows that are PURELY column markers go. A line with real content stays,
    even if it happens to contain a marker."""
    line = "     <S>   Albright   292"
    assert line in strip_sgml_dialect_markup(f"{line}\n")


# ── Footnote references are rewritten, width-neutrally ─────────────────────

@pytest.mark.fast
@pytest.mark.parametrize("n", [1, 2, 9, 10, 12, 99, 100])
def test_footnote_rewrite_is_width_neutral(n):
    """<Fn> and [Fn] are the same length for every n, because only the delimiters
    change. This is why the F is kept: [n] would be one character shorter."""
    original = f"3,615<F{n}>"
    out = strip_sgml_dialect_markup(original)
    assert out == f"3,615[F{n}]"
    assert len(out) == len(original)


@pytest.mark.fast
def test_footnote_refs_survive_as_references():
    """Deleting them was rejected — they point at footnotes still in the document."""
    out = strip_sgml_dialect_markup(LEGACY_FOOTNOTES)
    assert "[F1]" in out and "[F2]" in out and "[F3]" in out
    assert "<F1>" not in out


@pytest.mark.fast
def test_data_line_widths_are_unchanged():
    out = strip_sgml_dialect_markup(LEGACY_FOOTNOTES)
    for line in out.split("\n"):
        restored = re.sub(r"\[(F\d+)\]", r"<\1>", line)
        assert len(line) == len(restored)
    # And the columns still line up: every value starts at the same offset.
    offsets = {line.index("2,687") for line in out.split("\n") if "2,687" in line}
    assert offsets == {LEGACY_FOOTNOTES.split("\n")[1].index("2,687")}


# ── Page markers, bare and numbered ────────────────────────────────────────

@pytest.mark.fast
@pytest.mark.parametrize("marker", ["<PAGE>", "<PAGE 1>", "<PAGE 12>", "<page>"])
def test_page_markers_are_removed(marker):
    assert "PAGE" not in strip_sgml_dialect_markup(f"text {marker} more").upper().replace("TEXT", "")


# ── Conservative: real content with angle brackets survives ────────────────

@pytest.mark.fast
@pytest.mark.parametrize(
    "content",
    [
        "if x < 5 and y > 3 then",
        "net income < $1,000 in 1993",
        "ratio of <1.5 to 1",
        "See Note <reference to be supplied>",
    ],
)
def test_prose_angle_brackets_are_not_touched(content):
    """The reporter's own scan flagged many '<...>' runs that are not tags at all.
    Blanket deletion would eat inequalities out of 1990s filings."""
    assert strip_sgml_dialect_markup(content) == content


# ── End to end ─────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_legacy_table_has_no_dialect_left():
    out = primary_document_text("10-K", LEGACY_TABLE)
    assert not re.findall(r"<(?:TABLE|CAPTION|S|C|F\d+)>", out, re.IGNORECASE)
    # The data itself is untouched.
    assert "Albright        3       292       292" in out


# ── The real filings from the report ───────────────────────────────────────

@pytest.mark.network
@pytest.mark.parametrize(
    "accession", ["0000003673-94-000020", "0000012400-94-000008"]
)
def test_reported_filings_have_no_dialect_markup(accession):
    from edgar import find

    text = find(accession).sgml().text()
    leftover = sorted(set(re.findall(r"<[A-Za-z/][^<>]{0,20}>", text)))
    assert leftover == [], f"dialect markup survived: {leftover}"


@pytest.mark.network
def test_reported_footnotes_are_rewritten_not_dropped():
    from edgar import find

    text = find("0000012400-94-000008").sgml().text()
    assert sorted(set(re.findall(r"\[F\d+\]", text))) == ["[F1]", "[F2]", "[F3]", "[F4]"]
