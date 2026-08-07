"""Regression test for GitHub issue #846.

``Ownership.to_context()`` raised ``ValueError: Cannot specify ',' with 's'`` for
insider filings whose share values are non-numeric strings. ``SecurityHolding.shares``
is a raw XBRL string that can carry decimals and footnote markers (e.g.
``'42526.111'``, ``'4819.15 [F1]'``), and the method formatted them with the raw
thousands-grouping spec ``f"{x:,}"`` — which Python rejects for ``str`` values.

The fix routes the three share-formatting sites in ``to_context`` (Form 3 minimal
holdings, Form 3 standard holdings, Form 4/5 holdings-after) through the existing
``edgar.ownership.core.format_numeric`` helper, which strips commas / ``$`` /
footnote refs via ``safe_numeric`` and falls back to the raw string when it cannot
parse a number.

Despite the issue title saying "Form 4", every filing the reporter listed is a
Form 3; the crash site is the Form 3 holdings line that was missed when the related
Form 3 fix shipped in v5.35.1.
"""
import pytest

from edgar.ownership.core import format_numeric


@pytest.mark.fast
@pytest.mark.parametrize("raw, expected", [
    ("42526.111", "42,526.11"),    # decimal string -> grouped, 2dp
    ("4819.15 [F1]", "4,819.15"),  # footnote marker stripped
    ("1401.258", "1,401.26"),
    ("1,234,567", "1,234,567"),    # already-grouped integer string
    ("100", "100"),                # plain integer string
    (1000000, "1,000,000"),        # native int
])
def test_format_numeric_handles_share_strings(raw, expected):
    """format_numeric must never raise on string share values (GH #846)."""
    assert format_numeric(raw) == expected


@pytest.mark.fast
def test_format_numeric_does_not_raise_value_error():
    """The exact failure mode: a string value must not trigger the ',' format error."""
    # f"{'4819.15 [F1]':,}" would raise "Cannot specify ',' with 's'".
    result = format_numeric("4819.15 [F1]")
    assert isinstance(result, str)
    assert "[F1]" not in result


@pytest.mark.network
def test_wmt_form3_to_context_does_not_raise():
    """The reporter's reproduction must return text at every detail level (GH #846)."""
    import edgar

    filing = edgar.get_by_accession_number("0002110643-26-000002")  # listed as WMT; is a Form 3
    obj = filing.obj()
    assert obj.form == "3"

    for detail in ("minimal", "standard", "full"):
        ctx = obj.to_context(detail=detail)
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    standard = obj.to_context()
    # Ground truth: holding share string '42526.111' renders grouped to 2dp.
    assert "42,526.11" in standard
    # Footnote markers must not leak into the rendered shares.
    assert "[F1] shares" not in standard
