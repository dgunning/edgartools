"""Regression tests for issue edgartools-7pga / GH #875:
ProxyStatement.voting_proposals emits text fragments as proposals on some
merger proxies (DEFM14A).

Bug:
    On DEFM14A merger proxies the Incorporation-by-Reference section cites 8-K
    items by their decimal sub-item number ("information furnished pursuant to
    Item 2.02 or Item 7.01 of a Current Report on Form 8-K"). The proposal
    pattern ``(?:proposal|item )(\\d+)[:\\-.\\s]+(desc)`` read "Item 2.02" as
    proposal 2 with description "02 or Item 7.01 ...", because the separator
    class included ``.`` and swallowed the decimal point.

    Example: Veeco DEFM14A 0001104659-25-125601 produced two bogus proposals
    numbered 2 and 3 (no #1) with descriptions "02 or Item 7.01 of a Current
    Report on Form 8-K ..." and "03 therein); Veeco's Current Report ...".
    Essential Utilities DEFM14A 0001193125-25-337599 was clean (3 proposals).

Fix (edgar/proxy/html_extractor.py):
    1. ``(?!\\.\\d)`` after the number so a decimal sub-item ("Item 2.02") can't
       parse as a proposal.
    2. Skip a description that begins with a digit (a real title starts with a
       word, never a bare number).
    3. Validate numbering starts at 1 — if the lowest captured number isn't 1
       the anchor for proposal 1 was missed and the rest are fragments; prefer
       an empty list over garbage.
"""
import pytest

from edgar.proxy.html_extractor import extract_voting_proposals


class TestVotingProposalsNoFragments:
    """Deterministic, no-network guards for the three defenses."""

    def test_decimal_item_reference_not_a_proposal(self):
        """An 8-K Incorporation-by-Reference citation must yield no proposals."""
        text = (
            "The following documents are incorporated by reference (other than "
            "information furnished pursuant to Item 2.02 or Item 7.01 of a Current "
            "Report on Form 8-K, or exhibits thereto under Item 9.01) and contain "
            "important information about the companies."
        )
        assert extract_voting_proposals(text) == []

    def test_start_at_two_discarded_as_missed_anchor(self):
        """A list whose lowest number is 2 (no proposal 1) is fragments → empty."""
        text = (
            "Proposal 2: Ratification of the Appointment of the Independent Auditor.\n"
            "Proposal 3: Advisory Vote to Approve Executive Compensation.\n"
        )
        assert extract_voting_proposals(text) == []

    def test_description_starting_with_digit_skipped(self):
        """A fragment description that begins with a number is not a proposal."""
        text = "Item 8.02 of the Current Report contains the press release.\n"
        assert extract_voting_proposals(text) == []

    def test_real_proposals_starting_at_one_kept(self):
        """A well-formed proposal list (numbered from 1) is preserved."""
        text = (
            "Proposal 1: Share Issuance Proposal. The board recommends a vote FOR.\n"
            "Proposal 2: Adjournment Proposal. The board recommends a vote FOR.\n"
        )
        props = extract_voting_proposals(text)
        assert [p.number for p in props] == [1, 2]
        assert props[0].description.lower().startswith("share issuance")
        assert not any(p.description[0].isdigit() for p in props)


@pytest.mark.network
class TestDefm14aGroundTruth:
    """Hand-verified against the two real DEFM14A filings in the issue."""

    def test_veeco_emits_no_fragment_proposals(self):
        """Veeco's merger proxy must not surface Incorporation-by-Reference
        fragments as proposals (the garbage case)."""
        from edgar import find
        proxy = find("0001104659-25-125601").obj()
        props = proxy.voting_proposals
        # No fragment descriptions, and no broken start-at-2 numbering.
        assert not any(p.description[0].isdigit() for p in props), \
            f"fragment proposals leaked: {[p.description for p in props]}"
        assert all(p.number >= 1 for p in props)
        if props:
            assert props[0].number == 1

    def test_essential_utilities_three_clean_proposals(self):
        """Essential Utilities' merger proxy keeps its 3 real proposals."""
        from edgar import find
        proxy = find("0001193125-25-337599").obj()
        props = proxy.voting_proposals
        assert [p.number for p in props] == [1, 2, 3]
        descs = " ".join(p.description.upper() for p in props)
        assert "SHARE ISSUANCE" in descs and "ADJOURNMENT" in descs
