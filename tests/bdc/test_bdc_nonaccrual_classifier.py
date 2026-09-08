"""
Golden-set tests for the BDC non-accrual footnote classifier.

These are network-free regression tests over real footnote wordings observed
across BDC 10-K/10-Q filings (ARCC, FSK, GBDC, MAIN, PSEC). They pin the
behaviour of `_classify_nonaccrual_footnote` so the next time an issuer drifts
its footnote phrasing, CI catches the miss instead of a user.

Each case is (footnote_text, linked_to_investments, expected_flag). Texts are
verbatim (or lightly trimmed) from filings; see GH #835 for the original report
that motivated the hardening.
"""
from decimal import Decimal

import pytest

from edgar.bdc.nonaccrual import _build_warnings, _classify_nonaccrual_footnote


# --- Real affirmative labels that MUST be recognized as non-accrual flags ---
AFFIRMATIVE_CASES = [
    # MAIN — the #835 break: "and" originally, "or" in the latest filing.
    ("Non-accrual and non-income producing debt investment.", True),
    ("Non-accrual or non-income producing debt investment.", True),
    # ARCC — sentence form with a verb.
    ("Loan was on non-accrual status as of December 31, 2025.", True),
    # FSK — short sentence.
    ("Asset is on non-accrual status.", True),
    # GBDC — long, well-formed sentence (matches an affirmative pattern).
    (
        "Investment was on non-accrual status as of September 30, 2025, meaning "
        "that the Company has ceased recognizing interest income on the loan.",
        True,
    ),
    # PSEC — verb-less label that matched NO sentence pattern; recognized only
    # via the structure-corroborated short-label rule. Silently missed before.
    ("Investment on non-accrual status as of the reporting date (see Note 2).", True),
    ("(7)Investment on non-accrual status as of the reporting date (see Note 2).", True),
]


# --- Texts that MUST NOT be flagged ---
NEGATIVE_CASES = [
    # Explicit denials.
    ("There were no investments on non-accrual status as of period end.", True),
    ("The Company had no portfolio company investment on non-accrual status.", True),
    ("As of December 31, 2025, no loans were on non-accrual.", True),
    # GBDC rollforward table — mentions non-accrual in passing, runs 100+ words,
    # and is linked to investment facts. Length must keep it out.
    (
        "Gross additions Gross reductions " + ("word " * 120)
        + "non-accrual status changes during the period.",
        True,
    ),
    # A long policy/narrative footnote, not linked to specific investments.
    (
        "The Company places loans on non-accrual status when " + ("x " * 40)
        + "principal or interest payments become 90 days or more past due.",
        False,
    ),
    # No non-accrual mention at all.
    ("First lien senior secured loan; floating rate (SOFR + 5.50%).", True),
]


@pytest.mark.parametrize("text, linked", AFFIRMATIVE_CASES)
def test_affirmative_footnotes_recognized(text, linked):
    assert _classify_nonaccrual_footnote(text.lower(), linked) is True


@pytest.mark.parametrize("text, linked", NEGATIVE_CASES)
def test_non_flags_rejected(text, linked):
    assert _classify_nonaccrual_footnote(text.lower(), linked) is False


def test_short_label_requires_linkage():
    """The generous short-label rule only fires when XBRL links to investments.

    An unrecognized-by-pattern short footnote with no investment linkage stays
    out (and contributes nothing to Layer-1 extraction anyway)."""
    text = "investment on non-accrual status as of the reporting date".lower()
    assert _classify_nonaccrual_footnote(text, linked_to_investments=True) is True
    assert _classify_nonaccrual_footnote(text, linked_to_investments=False) is False


class TestBuildWarnings:
    """Break-the-silence diagnostics — empty/odd results must not be silent."""

    def test_silence_warning_when_portfolio_but_no_signal(self):
        warnings = _build_warnings(
            method='none',
            total_fv=Decimal('1000000000'),
            recognized_footnotes=0,
            num_investments=0,
            period='2025-12-31',
        )
        assert len(warnings) == 1
        assert 'No non-accrual data extracted' in warnings[0]

    def test_no_silence_warning_when_no_portfolio(self):
        # Non-BDC or unparseable filing — don't cry wolf.
        warnings = _build_warnings(
            method='none',
            total_fv=None,
            recognized_footnotes=0,
            num_investments=0,
            period='2025-12-31',
        )
        assert warnings == []

    def test_linkage_gap_warning(self):
        # Footnotes recognized as flags, but nothing resolved for the period.
        warnings = _build_warnings(
            method='custom_concept',
            total_fv=Decimal('1000000000'),
            recognized_footnotes=3,
            num_investments=0,
            period='2025-12-31',
        )
        assert any('resolved no investments' in w for w in warnings)

    def test_healthy_footnote_extraction_has_no_warnings(self):
        warnings = _build_warnings(
            method='footnote',
            total_fv=Decimal('1000000000'),
            recognized_footnotes=5,
            num_investments=5,
            period='2025-12-31',
        )
        assert warnings == []
