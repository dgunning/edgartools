"""Regression: ``edgar.xbrl.core.format_value(0, ...)`` returned the control character U+0014.

Origin: found during design review of GitHub Issue #1655 and #1737
(https://github.com/dgunning/edgartools/issues/1655,
https://github.com/dgunning/edgartools/issues/1737). Both design documents
noted that the helper's zero branch returned an invisible character instead of
a zero.

The zero branch read ``return "\\x14" if value == 0 else str(value)`` with a
literal 0x14 byte in the source since the XBRL2 rewrite (af5bdd22) -- most
likely a mangled em dash (U+2014, whose low byte is 0x14). Zero now goes
through the same formatting as every other number: "$0" for a monetary value,
"0" otherwise, with the decimals the caller asked for.

Statement rendering blanks a zero cell before it reaches this helper; that
display is unchanged (asserted below on a tracked fixture).
"""
from pathlib import Path

import pytest

from edgar.xbrl.core import format_value

CONTROL_CHARS = {chr(c) for c in range(0x20)} - {"\n", "\t"}


@pytest.mark.parametrize("value, is_monetary, scale, decimals, symbol, expected", [
    (0, True, -6, None, None, "$0"),
    (0.0, True, -6, -6, None, "$0"),
    (-0.0, True, -6, None, None, "$0"),
    (0, True, -3, None, "€", "€0"),
    (0, False, 0, None, None, "0"),
    (0, False, -6, 2, None, "0.00"),
    (0.0, False, 0, None, None, "0"),
])
def test_zero_formats_like_any_other_number(value, is_monetary, scale, decimals, symbol, expected):
    formatted = format_value(value, is_monetary, scale, decimals, symbol)
    assert formatted == expected
    assert not CONTROL_CHARS & set(formatted)


def test_zero_matches_the_shape_of_a_nonzero_value():
    assert format_value(1_000_000, True, -6) == "$1"
    assert format_value(0, True, -6) == "$0"
    assert format_value(-1_000_000, True, -6) == "$(1)"


def test_non_numeric_values_unchanged():
    assert format_value("n/a", True, -6) == "n/a"
    assert format_value("", True, -6) == ""


def test_source_has_no_control_characters():
    import edgar.xbrl.core as core
    source = Path(core.__file__).read_text(encoding="utf-8")
    assert not CONTROL_CHARS & set(source)


def test_rendered_statement_zero_cells_stay_blank():
    """Statement rendering keeps blanking a filed zero before it reaches format_value.

    Ground truth: Golub Capital BDC 10-Q for 2025-03-31, 0001476765-25-000040
    (tests/fixtures/xbrl/gbdc), R6 cash flow, $ thousands: "Proceeds from non-cash
    dividends" is 3,549 for the six months ended 2025-03-31 and 0 for 2024.
    """
    from edgar.xbrl import XBRL
    rendered = XBRL.from_directory(Path("tests/fixtures/xbrl/gbdc")).render_statement("CashFlowStatement")
    row = next(r for r in rendered.rows if r.metadata.get("concept") == "gbdc_ProceedsFromNonCashDividends")
    assert [c.value for c in row.cells] == [3_549_000, 0]
    assert [c.get_formatted_value() for c in row.cells] == ["$3,549", ""]
    text = str(rendered) + rendered.to_markdown()
    assert "\x14" not in text
