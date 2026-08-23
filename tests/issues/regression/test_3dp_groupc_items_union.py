"""8-K ``.items`` no longer unions in the legacy chunked parser (edgartools-3dp Group C).

``CurrentReport.items`` used to union THREE detection strategies. Group C removed
the middle one -- ``ChunkedDocument.list_items()``, the last read of
``edgar.files`` on this path -- leaving the new parser's section tree and the
text-based pattern extractor.

WHY A UNION NEEDED DIFFERENT EVIDENCE THAN GROUPS A AND B. Those were first-hit
fallback chains, where deleting a fallback can only matter if the modern parser
had already failed a lookup, so a per-lookup comparison measures the risk
directly. A union is not like that: every individual lookup can still answer
while the deletion silently drops an item from a SET. So the measurement compared
item SETS, parsing each filing twice -- once normally, once with
``list_items()`` returning ``[]`` -- across 391 8-K filings spanning 1995 to 2026:
the nine tracked fixtures below, a stride-sampled sweep of 27 quarterly indexes,
and the fourteen filings the 8-K regression suite already pins as hard cases.

The result was not marginal. On the 390 that produced a non-empty item set, the
chunked parser contributed a unique item to ZERO of them, and its raw view was
never even equal-plus-one: identical to the surviving strategies on 275, a strict
subset on 101, and of those it saw nothing whatsoever on 82. It was never a
superset of them on any filing.

That includes the case the deleted code's own comment cited as its
justification. Cimarex ``0001047469-05-006981`` carries two items and the chunked
parser sees only Item 8.01 -- but the text strategy already produces both, which
is what the comment said and why unioning strategy 3 was correct. The comment
argued for keeping the text strategy, not for keeping the chunked one.

TWO THINGS THIS FILE DELIBERATELY DOES NOT DO.

It does not parse twice and compare. That is tautological now: with the branch
gone the two runs are identical by construction and the test cannot fail. The
before/after comparison was migration evidence and was only meaningful while the
strategy was still wired.

It does not assert length floors on item text. Group B's fixture file does that,
because it is about which parser answers a lookup. This one is about which items
appear in a set, so it asserts exact sets -- an item quietly appearing or
vanishing is precisely the failure being guarded against.
"""
import pytest

# Group B's harness, imported rather than copied. ``_forbidding_legacy`` is a
# subtle guard -- it must RAISE rather than return None, and it must be a
# throwaway subclass rather than a patch on the class -- and two drifting copies
# of it is a worse outcome than the coupling. Group C is the direct sequel to
# that file and they merge together.
from test_3dp_groupb_fixture_corpus import EIGHT_K, FixtureFiling, _forbidding_legacy

from edgar.company_reports.current_report import CurrentReport

pytestmark = pytest.mark.fast

# Recorded on 2026-08-23 while the chunked strategy was STILL WIRED, which is
# what makes them a before/after rather than a snapshot of the code as it now is.
# Deleting the strategy changed none of them.
ITEM_SETS_BEFORE_DELETION = {
    "1013243-8-k-2001-03-30": {"Item 5", "Item 7"},
    "1074269-8-k-2001-03-30": {"Item 5", "Item 7"},
    "883787-8-k-2004-09-30": {"Item 1.01", "Item 9.01"},
    "1100748-8-k-2004-09-30": {"Item 1.01", "Item 5.02", "Item 9.01"},
    "1434743-8-k-2008-06-30": {"Item 1.01", "Item 2.03", "Item 9.01"},
    "786947-8-k-2008-06-30": {"Item 8.01", "Item 9.01"},
    "1442999-8-k-2025-06-30": {"Item 1.01", "Item 2.01", "Item 5.02", "Item 7.01", "Item 9.01"},
    "1998387-8-k-2025-06-30": {"Item 2.03", "Item 3.02", "Item 8.01", "Item 9.01"},
    "744452-8-k-2025-06-30": {"Item 2.05", "Item 5.02", "Item 7.01", "Item 9.01"},
}


def _only_section_tree(cls):
    """Strategy 1 alone: the new parser's sections, with the text strategy off."""
    return type("OnlySections" + cls.__name__, (cls,), {"_get_filing_text": lambda self: None})


def _only_text(cls):
    """Strategy 2 alone: the text extractor, with the new parser's sections off."""
    return type("OnlyText" + cls.__name__, (cls,), {"sections": property(lambda self: {})})


def test_the_expectations_cover_every_fixture():
    """A stale key would let a fixture drop out of the parametrized test unnoticed."""
    assert {p.stem for p in EIGHT_K} == set(ITEM_SETS_BEFORE_DELETION)


@pytest.mark.parametrize("path", EIGHT_K, ids=lambda p: p.stem)
def test_the_item_set_survived_the_deletion(path):
    """Exact sets, pinned from the pre-deletion measurement.

    The non-empty assertion is not decoration. A filing that parses to zero items
    matches a zero-item expectation perfectly, so without it a total parser
    failure would read as agreement -- the trap that made 98% of Group B's
    lookups meaningless until content was proved on both sides.
    """
    items = set(CurrentReport(FixtureFiling(path, "8-K")).items)

    assert items, f"{path.name} produced no items at all"
    assert items == ITEM_SETS_BEFORE_DELETION[path.stem]


@pytest.mark.parametrize("path", EIGHT_K, ids=lambda p: p.stem)
def test_items_never_reads_the_legacy_parser(path):
    """The guard, on the path that actually mattered.

    ``list_items()`` was called unconditionally, so unlike Group B's fallbacks
    this branch was reached on every filing -- there is no "the modern parser
    answered first" path that could hide a reintroduction. Verified the way that
    file learned to verify guards: by putting the deleted branch back and
    watching this turn red.
    """
    items = set(_forbidding_legacy(CurrentReport)(FixtureFiling(path, "8-K")).items)

    assert items == ITEM_SETS_BEFORE_DELETION[path.stem]


def test_both_surviving_strategies_are_load_bearing():
    """Neither survivor is redundant, so the union is still a union.

    Worth pinning because the measurement kept finding one strategy to be a
    subset of another, and that is exactly the shape of argument that deleted the
    chunked parser. These two do not have that relationship: the 2008 and 2025
    fixtures are carried by the section tree with the text extractor silent, and
    the 2001 and 2004 ones the other way round.

    (On these fixtures the text extractor reads ``FixtureFiling.text()``, which
    returns the raw HTML rather than extracted text, so it is quieter here than
    on a real filing. The split it demonstrates is real either way -- and over the
    network the section tree is the sole source on filings such as
    ``0001493152-21-030832``, whose Item 5.07 no text pattern finds.)
    """
    by_stem = {p.stem: p for p in EIGHT_K}
    text_only = by_stem["1013243-8-k-2001-03-30"], by_stem["1100748-8-k-2004-09-30"]
    sections_only = by_stem["786947-8-k-2008-06-30"], by_stem["744452-8-k-2025-06-30"]

    for path in text_only:
        filing = FixtureFiling(path, "8-K")
        assert not _only_section_tree(CurrentReport)(filing).items
        assert set(_only_text(CurrentReport)(filing).items) == ITEM_SETS_BEFORE_DELETION[path.stem]

    for path in sections_only:
        filing = FixtureFiling(path, "8-K")
        assert not _only_text(CurrentReport)(filing).items
        assert set(_only_section_tree(CurrentReport)(filing).items) == ITEM_SETS_BEFORE_DELETION[path.stem]
