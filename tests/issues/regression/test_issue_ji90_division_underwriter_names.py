"""A firm that files as a *division* of its broker-dealer is a real underwriter.

``_looks_like_term_fragment`` rejects a name when any non-first word starts
lowercase and is not in ``_UW_NAME_LOWER_OK``. The allowlist held connectors and
corporate-form tokens ('and', 'of', 'llc', 'inc', ...) but not 'division' or the
article 'a', so the legal names of boutique underwriters were rejected:

    EF Hutton, division of Benchmark Investments, LLC                 49 chars
    ThinkEquity, a division of Fordham Financial Management, Inc.     61 chars

Both are well under the 80-char cap the guard applies; they failed on the single
token 'division'. A rejected name is dropped from the roster at both guard sites,
so ``RegistrationS1.underwriting.lead_manager`` returned **None** — silently, with
no warning and no partial result — on every filing these firms led. EF Hutton and
ThinkEquity underwrote a large share of small-cap IPOs in 2021-2023, so this was a
population rather than an outlier.

The guard arrived with the gh-868 fix (09bf080e), which stopped a lock-up table
header leaking into the roster. That defect is still guarded — see the junk cases
below, which stay rejected — the guard was simply too strict about real names.

Found by sweeping 66 small S-1s while checking whether the 220 MB Airbnb gh-868
cassettes could be replaced by a smaller filing (bead edgartools-ji90).
"""
import pytest

from edgar.offerings.prospectus._424b_tables.underwriters import (
    is_plausible_underwriter_name,
)
from tests._offline_filings import offline_filing

# Real firm names that file under the "division of" construction.
DIVISION_FIRMS = [
    "EF Hutton, division of Benchmark Investments, LLC",
    "ThinkEquity, a division of Fordham Financial Management, Inc.",
    "Kingswood, a division of Benchmark Investments, LLC",
    "Titan Partners Group, a division of American Capital Partners",
]

# Non-firm text seen leaking from real filings' tables. Every one of these must
# stay rejected: relaxing the guard must not reopen gh-868.
TABLE_JUNK = [
    "Earliest Date Available for Sale in the Public Market",  # gh-868, Airbnb lock-up
    "Shares Eligible for Future Sale",
    "Conversion of debt to Preferred Series D",
    "Shares issued for acquisition of assets - Series E",
    "Prior to the Reverse Stock Split",
    "All officers, directors and director nominees as a group",
]


class TestNameGuard:
    """The guard must admit real firm names and keep rejecting table text."""

    @pytest.mark.parametrize("name", DIVISION_FIRMS)
    def test_division_of_firm_names_are_plausible(self, name):
        assert is_plausible_underwriter_name(name), (
            f"{name!r} is a real underwriter and was rejected; lead_manager "
            "would be None on every filing it led"
        )

    @pytest.mark.parametrize("junk", TABLE_JUNK)
    def test_table_junk_is_still_rejected(self, junk):
        """The silence check: widening the allowlist must not reopen gh-868."""
        assert not is_plausible_underwriter_name(junk)

    def test_conventional_firm_names_are_unaffected(self):
        for name in ("Morgan Stanley & Co. LLC", "Needham & Company, LLC",
                     "Evercore Group L.L.C.", "BofA Securities, Inc."):
            assert is_plausible_underwriter_name(name)


class TestJi90AgainstFiling:
    """Ground truth: the roster of a real IPO led by a division-named firm."""

    @pytest.mark.vcr
    def test_lead_manager_is_the_firm_not_none(self):
        # Unicycive Therapeutics S-1/A (2021-06-30), IPO led by EF Hutton.
        # Before the fix this returned None: the sole underwriter on the cover
        # was rejected by the name guard, leaving an empty roster.
        obj = offline_filing("0001213900-21-035033").obj()
        uw = obj.underwriting
        assert uw is not None
        assert uw.lead_manager == "EF Hutton, division of Benchmark Investments, LLC"
        assert "EF Hutton, division of Benchmark Investments, LLC" in [
            u.name for u in uw.underwriters
        ]
