"""Regression test for GitHub Issue #915: Workiva TOC rows with split
label/title hrefs.

Reported against Tesla's FY2023 10-K (accession 0001628280-24-002390):
``obj['Item 3']`` returned 145,561 chars — the ~1.2K legal-proceedings body
plus everything through Part II Item 5 — because the section map was missing
``part_i_item_1b``, ``part_i_item_4`` and ``part_ii_item_5`` and anchored
Items 1/1A at the wrong positions, so Item 3's end boundary overshot to the
next detected anchor.

Root cause: Tesla's Workiva TOC splits each row into a label link
("Item 4.") and a title link ("Mine Safety Disclosures") with *different*
hrefs, and the label hrefs are broken. ``_analyze_workiva_toc`` grouped a
row's links by href and took the first group that parsed to an item — the
label group:

- When the label target existed but was wrong (Item 1 → a bare page-break
  div that actually precedes Item 8), the item anchored at the wrong place.
- When the label target didn't exist, the row survived only if the title
  text was in the keyword vocabulary ("Legal Proceedings" yes; "Mine Safety
  Disclosures", "Unresolved Staff Comments" and Item 5's long title no —
  those items were silently dropped).

Fix: each row is resolved as a whole. When a row names a single item, the
anchor is chosen across ALL of the row's href groups — preferring a target
that exists and whose neighbourhood matches the item's own heading
(``_anchor_matches_heading``). Rows where no group parses but the row text
carries the number are recovered when exactly one group has a real target.

The unit tests exercise ``_analyze_workiva_toc`` on a minimal Tesla-shaped
TOC (no network). The end-to-end assertions are VCR-backed and pinned to the
reported filing.

GitHub Issue: https://github.com/dgunning/edgartools/issues/915
"""

import pytest

from edgar.documents.utils.toc_analyzer import TOCAnalyzer

# Minimal Tesla-shaped Workiva TOC. Each row splits the "Item N." label and
# the title into separate links with DIFFERENT hrefs:
# - w* label hrefs are broken: w205/w208/w214/w217 have no target at all;
#   w67 (Item 1's label) targets a bare div whose next heading is Item 8's.
# - t* title hrefs target a div directly preceding the item's real heading.
# The Item 7 row is a healthy shared-href row (label, title and page all t43)
# to pin the unchanged path. Six item rows keep the link-based TOC finder
# engaged (it needs several "Item N." links to pick the table).
WORKIVA_SPLIT_HREF_HTML = """
<html><body>
<div>TABLE OF CONTENTS</div>
<table>
<tr><td><a href="#w67">Item 1.</a></td><td><a href="#t16">Business</a></td><td><a href="#t16">4</a></td></tr>
<tr><td><a href="#w205">Item 1B.</a></td><td><a href="#t22">Unresolved Staff Comments</a></td><td><a href="#t22">28</a></td></tr>
<tr><td><a href="#w208">Item 3.</a></td><td><a href="#t28">Legal Proceedings</a></td><td><a href="#t28">30</a></td></tr>
<tr><td><a href="#w214">Item 4.</a></td><td><a href="#t31">Mine Safety Disclosures</a></td><td><a href="#t31">30</a></td></tr>
<tr><td colspan="3">PART II</td></tr>
<tr><td><a href="#w217">Item 5.</a></td><td><a href="#t37">Market for Registrant's Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities</a></td><td><a href="#t37">31</a></td></tr>
<tr><td><a href="#t43">Item 7.</a></td><td><a href="#t43">Management's Discussion and Analysis of Financial Condition and Results of Operations</a></td><td><a href="#t43">33</a></td></tr>
</table>
<div id="t16"></div>
<div>ITEM 1. BUSINESS</div>
<div id="t22"></div>
<div>ITEM 1B. UNRESOLVED STAFF COMMENTS</div>
<div id="t28"></div>
<div>ITEM 3. LEGAL PROCEEDINGS</div>
<div id="t31"></div>
<div>ITEM 4. MINE SAFETY DISCLOSURES</div>
<div id="t37"></div>
<div>ITEM 5. MARKET FOR REGISTRANT'S COMMON EQUITY</div>
<div id="t43"></div>
<div>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</div>
<div id="w67"></div>
<div>ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA</div>
</body></html>
"""


@pytest.fixture
def workiva_mapping():
    return TOCAnalyzer(form="10-K")._analyze_workiva_toc(WORKIVA_SPLIT_HREF_HTML)


class TestWorkivaSplitHrefRows:
    """Rows whose label and title links carry different hrefs resolve correctly."""

    def test_wrong_label_target_rejected_by_heading_match(self, workiva_mapping):
        """Item 1's label target exists but precedes Item 8's heading; the
        title link is preferred because its neighbourhood matches "ITEM 1"."""
        assert workiva_mapping.get("part_i_item_1") == "t16"

    def test_broken_label_href_title_in_vocabulary(self, workiva_mapping):
        """Item 3's label target doesn't exist; "Legal Proceedings" is in the
        keyword vocabulary, so this row survived even before the fix."""
        assert workiva_mapping.get("part_i_item_3") == "t28"

    def test_broken_label_href_title_not_in_vocabulary(self, workiva_mapping):
        """The reported drops: label targets missing and titles not in the
        vocabulary. The item number now comes from the label group's text and
        the anchor from the title link, instead of dropping the row."""
        assert workiva_mapping.get("part_i_item_1b") == "t22"
        assert workiva_mapping.get("part_i_item_4") == "t31"
        assert workiva_mapping.get("part_ii_item_5") == "t37"

    def test_shared_href_row_unchanged(self, workiva_mapping):
        """A healthy Workiva row (all links share one href) maps as before."""
        assert workiva_mapping.get("part_ii_item_7") == "t43"

    def test_no_rows_dropped(self, workiva_mapping):
        assert set(workiva_mapping) == {
            "part_i_item_1", "part_i_item_1b", "part_i_item_3",
            "part_i_item_4", "part_ii_item_5", "part_ii_item_7",
        }


@pytest.mark.fast
@pytest.mark.vcr
def test_tesla_2023_10k_item_3_does_not_overflow():
    """End-to-end on the reported filing: Tesla FY2023 10-K (Workiva agent).

    Pinned by accession and VCR-backed. Before the fix ``obj['Item 3']``
    returned 145,561 chars (Item 3 through Part II Item 5) and the section
    map was missing Items 1B, 4 and 5.
    """
    from edgar import Filing

    filing = Filing(form='10-K', filing_date='2024-01-29', company='Tesla, Inc.',
                    cik=1318605, accession_no='0001628280-24-002390')
    obj = filing.obj()
    secs = obj.document.sections

    # The dropped items are back, so Item 3 is bounded by Item 4's anchor.
    assert "part_i_item_1b" in secs
    assert "part_i_item_4" in secs
    assert "part_ii_item_5" in secs

    item3 = obj['Item 3']
    assert item3 is not None
    assert len(item3) == 1_165
    assert item3.lstrip().startswith("ITEM 3. LEGAL PROCEEDINGS")
    # The over-captured slice used to run through "ITEM 6. [RESERVED]".
    assert "[RESERVED]" not in item3

    # Items 1 and 1A no longer anchor at the broken label targets (Item 1's
    # label pointed at the div preceding Item 8, capturing 10K chars of the
    # wrong content; Item 8 in turn was truncated to 2.5K chars).
    assert len(secs["part_i_item_1"].text()) == 45_669
    assert len(secs["part_i_item_1a"].text()) == 79_150
    assert len(secs["part_ii_item_8"].text()) == 161_466

    # Every section resolves cleanly — no over-capture / truncation warnings.
    for name, section in secs.items():
        assert not getattr(section, "warnings", []), (name, section.warnings)

    # The Workiva agent parse now matches the generic parse on this filing
    # (24 sections, identical anchors) instead of 21 with wrong anchors.
    from edgar.documents.utils.toc_analyzer import TOCAnalyzer

    html = filing.html()
    analyzer = TOCAnalyzer(form="10-K")
    assert analyzer.analyze_toc_structure(html, agent='Workiva') == \
        analyzer.analyze_toc_structure(html)
