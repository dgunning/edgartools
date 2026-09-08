"""Regression test for issue #1227.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1227

`Statement.to_markdown()` emitted filed labels into pipe-table cells verbatim.
Global Arena Holding tags a label that contains a literal pipe -- "Number of
common stock issued for conversion of debt | shares" -- so its data row carried
four unescaped pipes where a two-column row has three. Every Markdown parser
reads that as a three-column row, and the row stops matching the header.

`edgar/markdown.py:814` already escaped pipes when building tables from filing
HTML; the XBRL renderer had no equivalent. The fix puts the rule in
`edgar.xbrl.rendering._md_cell` and runs the column headers, the row labels and
the formatted values through it.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL

GAHC = Path(__file__).resolve().parents[3] / "data" / "xbrl" / "datafiles" / "gahc"
ROLE = ("http://globalarenaholding.com/role/"
        "StockholdersDeficitCommonStockNarrativeDetails")


def _unescaped_pipes(line: str) -> int:
    """Count the pipes a Markdown parser reads as column delimiters."""
    return line.replace(r"\|", "").count("|")


@pytest.fixture(scope="module")
def gahc_markdown():
    assert GAHC.exists(), f"missing fixture: {GAHC}"
    xbrl = XBRL.from_directory(GAHC)
    return xbrl.statements[ROLE].to_markdown(detail="minimal")


def test_filed_pipe_in_a_label_is_escaped(gahc_markdown):
    row = next(line for line in gahc_markdown.splitlines()
               if "conversion of debt" in line.lower())

    assert r"conversion of debt \| shares" in row
    # Two columns: a leading delimiter, one between them, a trailing one.
    assert _unescaped_pipes(row) == 3


def test_every_row_has_the_column_count_the_header_declares(gahc_markdown):
    lines = [line for line in gahc_markdown.splitlines() if line.startswith("|")]
    assert len(lines) > 2, "expected a header, a separator and data rows"

    expected = _unescaped_pipes(lines[0])
    for line in lines:
        assert _unescaped_pipes(line) == expected, f"row does not match header: {line!r}"


def test_a_newline_in_a_cell_cannot_end_the_row():
    from edgar.xbrl.rendering import _md_cell

    assert _md_cell("first\nsecond") == "first second"
    assert _md_cell("first\r\nsecond") == "first second"
    assert _md_cell(None) == ""
    assert _md_cell(447) == "447"
