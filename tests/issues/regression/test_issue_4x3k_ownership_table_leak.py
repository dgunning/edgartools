"""A beneficial-ownership table is not an underwriting table.

The two have the same shape — a name column beside a 'Number of Shares' column —
so an ownership table satisfies ``has_row_based_header``, and having no bank
names in its rows it satisfies ``trust_structure`` too, which accepts every row
label as a firm. On Learn CW Investment Corp's S-1 (``0001140361-21-010426``)
that produced::

    lead_manager: 'Before Offering'          <- a column header
    roster:       'Before Offering',
                  'CWAM LC Sponsor LLC',     <- the sponsor
                  'Robert Hutter', 'Adam Fisher', 'Greg Mauro',
                  'Alan Howard', 'Daniel H. Stern',   <- individual directors
                  'Evercore Group L.L.C.'    <- the one real underwriter, last

The filing has a perfectly good underwriter table two hundred tables later
(``Underwriter | Number of Units`` -> Evercore), so nothing was missing; an
ownership table simply got there first.

WHY THE NAME GUARD CANNOT DO THIS. gh-868 added
``is_plausible_underwriter_name`` to keep table text out of the roster, and it
catches the Airbnb lock-up header because that string is long and full of
lowercase words. It cannot catch this one: ``is_plausible_underwriter_name('Before
Offering')`` is True, and so is every director's name. They are plausible firm
names by any per-name test. Only the table knows what it is, so the table is
what gets rejected (bead edgartools-4x3k).
"""
import pytest

from edgar.offerings.prospectus._424b_tables.underwriters import (
    _is_ownership_table,
    is_plausible_underwriter_name,
)
from tests._offline_filings import offline_filing

# The individuals Learn CW's ownership table listed as underwriters.
LEARN_CW_DIRECTORS = [
    "Robert Hutter", "Adam Fisher", "Greg Mauro", "Alan Howard", "Daniel H. Stern",
]


class TestOwnershipTableDetection:
    """The header region decides; prose and footnotes do not."""

    def test_learn_cw_header_rows_are_recognised(self):
        """The real shape: a name/shares header, then a stacked second header row."""
        rows = [
            ["Name and Address of Beneficial Owner (1)", "Number of Shares Owned (2)",
             "Approximate Percentage of Issued\nand Outstanding Ordinary Shares"],
            ["Before Offering", "After Offering", "Before Offering", "After Offering"],
            ["CWAM LC Sponsor LLC (3)", "7,187,500", "6,250,000", "98.7%", "19.8%"],
        ]
        assert _is_ownership_table([], rows)

    def test_a_real_underwriter_table_is_not_an_ownership_table(self):
        """Learn CW's actual underwriting table, which must survive."""
        rows = [["Underwriter", "Number of Units"],
                ["Evercore Group L.L.C."],
                ["Total", "25,000,000"]]
        assert not _is_ownership_table([], rows)

    def test_conventional_allocation_table_is_not_an_ownership_table(self):
        rows = [["Underwriters", "Number of Shares"],
                ["Morgan Stanley & Co. LLC", "1,000,000"],
                ["Goldman Sachs & Co. LLC", "500,000"]]
        assert not _is_ownership_table([], rows)

    def test_a_footnote_mentioning_ownership_does_not_discard_the_table(self):
        """The silence check.

        Only the header region is read. A genuine underwriter table that carries
        a footnote about beneficial ownership must keep its syndicate — rejecting
        it would trade this bug for a worse one.
        """
        rows = [
            ["Underwriter", "Number of Shares"],
            ["Morgan Stanley & Co. LLC", "1,000,000"],
            ["Each person known by us to be the beneficial owner of more than 5% of "
             "our outstanding shares is listed in the table above."],
        ]
        assert not _is_ownership_table([], rows)

    def test_the_leaked_names_are_plausible_to_the_name_guard(self):
        """Why this had to be fixed at the table.

        gh-868's per-name guard passes every one of these, which is why the
        roster looked entirely reasonable while being entirely wrong.
        """
        assert is_plausible_underwriter_name("Before Offering")
        assert is_plausible_underwriter_name("After Offering")
        for director in LEARN_CW_DIRECTORS:
            assert is_plausible_underwriter_name(director)


class Test4x3kAgainstFiling:
    """Ground truth: Learn CW's underwriter is Evercore, and only Evercore."""

    @pytest.mark.vcr
    def test_roster_is_the_underwriter_not_the_owners(self):
        # Learn CW Investment Corp S-1 (2021-03-29), sole underwriter Evercore.
        obj = offline_filing("0001140361-21-010426").obj()
        uw = obj.underwriting
        assert uw is not None
        names = [u.name for u in uw.underwriters]

        assert uw.lead_manager == "Evercore Group L.L.C."
        assert names == ["Evercore Group L.L.C."]
        # The specific leaks, named so a regression says which half broke.
        assert "Before Offering" not in names
        assert "CWAM LC Sponsor LLC" not in names
        for director in LEARN_CW_DIRECTORS:
            assert director not in names
