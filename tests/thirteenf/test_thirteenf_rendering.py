"""
Tests for 13F rendering utilities (edgar.thirteenf.rendering).

Pure function tests — no network calls or filing data needed.
"""

import math

import pytest

from edgar.thirteenf.rendering import (
    _is_number,
    _status_text,
    _fmt_change,
    sparkline,
    SPARK_CHARS,
)


# ── _is_number ───────────────────────────────────────────────────────────────

class TestIsNumber:

    def test_valid_numbers(self):
        assert _is_number(42) is True
        assert _is_number(3.14) is True
        assert _is_number(0) is True
        assert _is_number(-1) is True

    def test_none_and_nan(self):
        assert _is_number(None) is False
        assert _is_number(float('nan')) is False

    def test_non_numeric(self):
        assert _is_number("hello") is False
        assert _is_number([1, 2]) is False

    def test_numeric_strings(self):
        assert _is_number("42") is True
        assert _is_number("3.14") is True


# ── sparkline ────────────────────────────────────────────────────────────────

class TestSparkline:

    def test_increasing_values(self):
        result = sparkline([100, 110, 120, 130, 140])
        assert len(result) == 5
        # First char should be lower or equal to last char
        assert SPARK_CHARS.index(result[0]) <= SPARK_CHARS.index(result[-1])

    def test_constant_values(self):
        result = sparkline([100, 100, 100])
        mid = len(SPARK_CHARS) // 2
        assert all(c == SPARK_CHARS[mid] for c in result)

    def test_all_zeros(self):
        result = sparkline([0, 0, 0])
        mid = len(SPARK_CHARS) // 2
        assert all(c == SPARK_CHARS[mid] for c in result)

    def test_empty_input(self):
        assert sparkline([]) == ""

    def test_all_none(self):
        result = sparkline([None, None, None])
        assert result == "   "

    def test_none_values_become_spaces(self):
        result = sparkline([100, None, 100])
        assert result[1] == " "
        assert len(result) == 3

    def test_nan_values_become_spaces(self):
        result = sparkline([100, float('nan'), 100])
        assert result[1] == " "

    def test_single_value(self):
        result = sparkline([100])
        assert len(result) == 1

    def test_non_numeric_becomes_none(self):
        result = sparkline([100, "bad", 100])
        assert result[1] == " "


# ── _status_text ─────────────────────────────────────────────────────────────

class TestStatusText:

    @pytest.mark.parametrize("status,expected_text", [
        ("NEW", "NEW"),
        ("CLOSED", "CLOSED"),
        ("INCREASED", "▲ INCREASED"),
        ("DECREASED", "▼ DECREASED"),
        ("UNCHANGED", "• UNCHANGED"),
    ])
    def test_status_labels(self, status, expected_text):
        result = _status_text(status)
        assert result.plain == expected_text

    def test_unknown_status(self):
        result = _status_text("SOMETHING_ELSE")
        assert result.plain == "• UNCHANGED"


# ── _fmt_change ──────────────────────────────────────────────────────────────

class TestFmtChange:

    def test_positive_value(self):
        result = _fmt_change(1000)
        assert result.plain == "+1,000"
        assert "green" in result.style

    def test_negative_value(self):
        result = _fmt_change(-500)
        assert result.plain == "-500"
        assert "red" in result.style

    def test_zero_value(self):
        result = _fmt_change(0)
        assert result.plain == "+0"
        assert "dim" in result.style

    def test_percentage_format(self):
        result = _fmt_change(12.5, is_pct=True)
        assert result.plain == "+12.5%"

    def test_negative_percentage(self):
        result = _fmt_change(-3.2, is_pct=True)
        assert result.plain == "-3.2%"

    def test_none_value(self):
        result = _fmt_change(None)
        assert result.plain == "-"

    def test_nan_value(self):
        result = _fmt_change(float('nan'))
        assert result.plain == "-"
