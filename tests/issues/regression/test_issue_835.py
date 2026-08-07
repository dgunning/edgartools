"""
Regression test for GH #835.

extract_nonaccrual() returned an empty investment list for MAIN's 2026-03-31
10-Q despite non-accrual assets being present. Root cause: the affirmative
footnote classifier hard-coded "and" in the label pattern, while MAIN changed
its footnote wording from

    "Non-accrual and non-income producing debt investment."
to
    "Non-accrual or non-income producing debt investment."

so the footnote no longer matched and Layer-1 extraction silently produced
nothing.

Reported by HristoRaykov. See bead edgartools-bded for the broader hardening
work; this file pins the specific "and"/"or" fix.
"""
import re

import pytest

from edgar import Company
from edgar.bdc.nonaccrual import AFFIRMATIVE_PATTERNS, extract_nonaccrual


def _is_affirmative(text: str) -> bool:
    """Mirror the Layer-1 affirmative gate in _extract_from_footnotes."""
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in AFFIRMATIVE_PATTERNS)


class TestIssue835AffirmativePatterns:
    """Network-free: the footnote classifier must accept both wordings."""

    def test_and_wording_still_matches(self):
        # The original wording must keep matching (no regression).
        assert _is_affirmative("Non-accrual and non-income producing debt investment.")

    def test_or_wording_now_matches(self):
        # The new MAIN wording — the actual #835 break.
        assert _is_affirmative("Non-accrual or non-income producing debt investment.")

    def test_hyphenless_or_wording_matches(self):
        # "non accrual" (space) plus the "or" connector.
        assert _is_affirmative("Non accrual or non income producing debt investment.")


@pytest.mark.network
class TestIssue835MAIN:
    """Ground-truth: MAIN's #835 10-Q must yield non-accrual investments.

    Anchored on MAIN per the BDC testing convention (stable issuer, not the
    volatile latest-year list).
    """

    def test_main_10q_returns_nonaccrual_investments(self):
        # The exact filing from the report: period 2026-03-31, filed 2026-05-08.
        filings = Company("MAIN").get_filings(
            form=["10-K", "10-Q"], filing_date="2026-05-08"
        )
        assert len(filings) > 0, "Expected MAIN's 2026-05-08 10-Q to be available"
        filing = filings[0]

        result = extract_nonaccrual(filing)

        assert result is not None
        # Before the fix this was an empty list (silent data loss).
        assert result.num_nonaccrual > 0, (
            "Expected non-accrual investments for MAIN 10-Q period 2026-03-31; "
            "got an empty list (#835 regression)"
        )
        assert result.extraction_method == "footnote"
