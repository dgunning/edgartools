"""
Regression test for beads issue edgartools-l6cl: EightK.items under-reported items.

Two independent defects, both surfaced by 2005-era 8-Ks that are plain text wrapped
in minimal HTML:

1. The text-based extraction anchored item headers at the start of a line only. GMAC's
   2005-03-16 8-K glues its Item 4.02 header onto the trailing end of a horizontal rule
   with no line break ("------------Item 4.02 Non-Reliance on..."), so Item 4.02 was
   never detected while Item 8.01 — which follows a blank line — was. The same anchor
   was used to slice item content, so ``eightk['Item 4.02']`` returned None too.

2. ``.items`` early-returned as soon as the two HTML strategies produced any item at
   all, so a partial result was never topped up from the text strategy. Cimarex's
   2005-03-18 8-K contains Items 8.01 and 9.01; the section parser produced the
   dot-less "Item 8"/"Item 9" (discarded as unreliable) and the chunked parser saw only
   Item 8.01, so 9.01 was lost even though the text strategy finds it. The three
   strategies are now unioned. This also fixes modern filings: Exxon's 2026-05-01 8-K
   lost its Item 7.01 the same way.

The union is safe because ``filing.text()`` renders the primary document alone — the
same precision domain as the two HTML strategies — and because the relaxed anchor only
adds the after-a-horizontal-rule case, leaving mid-sentence references
("as described in Item 8.01") unmatched.
"""

import pytest

from edgar import Filing
from edgar.company_reports import EightK
from edgar.company_reports.current_report import (
    _extract_item_content_from_text,
    _extract_items_from_text,
)

# GMAC 8-K whose Item 4.02 header is glued onto a horizontal rule.
GMAC_FILING = Filing(company='GENERAL MOTORS ACCEPTANCE CORP', cik=40729, form='8-K',
                     filing_date='2005-03-16', accession_no='0000040729-05-000026')

# Cimarex 8-K where the HTML strategies return a partial (Item 8.01 only) result.
CIMAREX_FILING = Filing(company='CIMAREX ENERGY CO', cik=1168054, form='8-K',
                        filing_date='2005-03-18', accession_no='0001047469-05-006981')

# BayCorp 8-K: header advertises four items, the document body carries three headers.
BAYCORP_FILING = Filing(company='BAYCORP HOLDINGS LTD', cik=1012127, form='8-K',
                        filing_date='2005-03-18', accession_no='0001012127-05-000006')


@pytest.mark.network
def test_item_glued_to_horizontal_rule_is_detected():
    """GMAC: "------------Item 4.02" must be recognized as an item header."""
    eightk = GMAC_FILING.obj()
    assert isinstance(eightk, EightK)

    # Both items appear in the SGML header's ITEM INFORMATION lines
    # ("Non-Reliance on Previously Issued Financial Statements..." and "Other Events")
    # and as section headers in the document text.
    assert eightk.items == ['Item 4.02', 'Item 8.01']


@pytest.mark.network
def test_rule_anchored_item_content_is_retrievable():
    """GMAC: the recovered Item 4.02 must also be readable, without bleeding into 8.01."""
    eightk = GMAC_FILING.obj()

    content = eightk['Item 4.02']
    assert content is not None, "Item 4.02 content should be retrievable"

    # Content starts at the header itself, not at the horizontal rule preceding it.
    assert content.startswith('Item 4.02')
    assert '-----' not in content.split('\n', 1)[0]

    # A distinctive phrase from the 4.02 section.
    assert 'should no longer be relied upon' in content

    # The section stops before Item 8.01 rather than swallowing it.
    assert 'Item 8.01' not in content
    assert 'internal control considerations' not in content

    # Item 8.01 is retrievable in its own right and is a different section.
    item_801 = eightk['Item 8.01']
    assert item_801 is not None
    assert item_801.startswith('Item 8.01')
    assert 'In order to analyze the internal control considerations' in item_801

    # The bare-number lookup form works too.
    assert eightk['4.02'] == content


@pytest.mark.network
def test_text_strategy_tops_up_partial_html_result():
    """Cimarex: Item 9.01 is only found by the text strategy, which must be unioned in."""
    eightk = CIMAREX_FILING.obj()

    # SGML header ITEM INFORMATION: "Other Events", "Financial Statements and Exhibits".
    # Both appear as "ITEM 8.01"/"ITEM 9.01" headers in the document text.
    assert eightk.items == ['Item 8.01', 'Item 9.01']


@pytest.mark.network
def test_items_report_only_headers_present_in_the_document():
    """BayCorp: the header advertises an Item 9.01 the document never heads.

    The SGML header lists four ITEM INFORMATION entries (1.01, 2.01, 2.03 and
    "Financial Statements and Exhibits" = 9.01), but the document body has no Item 9.01
    header at all — it goes straight from the Item 2.03 text to SIGNATURES and an
    "EXHIBIT INDEX" heading. ``.items`` reports what the document actually heads, so
    three items is the correct answer for the document-parsing strategies. Recovering
    the fourth would require reading the SGML header, which is a separate change.
    """
    eightk = BAYCORP_FILING.obj()
    assert eightk.items == ['Item 1.01', 'Item 2.01', 'Item 2.03']

    # Every reported item is retrievable — the property and the accessor agree.
    for item in eightk.items:
        assert eightk[item] is not None, f"{item} listed but not retrievable"


@pytest.mark.network
def test_modern_multi_item_8k_gains_no_false_positives():
    """Nike's four-item 8-K: unioning the text strategy must not invent items."""
    filing = Filing(company='NIKE, Inc.', cik=320187, form='8-K',
                    filing_date='2026-06-23', accession_no='0000320187-26-000070')
    eightk = filing.obj()

    # Matches the SGML header exactly: Results of Operations; Departure of Directors;
    # Regulation FD Disclosure; Financial Statements and Exhibits.
    assert eightk.items == ['Item 2.02', 'Item 5.02', 'Item 7.01', 'Item 9.01']


@pytest.mark.network
def test_modern_8k_recovers_item_missed_by_html_strategies():
    """Exxon: Item 7.01 is in the SGML header and the text, but not the HTML strategies."""
    filing = Filing(company='EXXON MOBIL CORP', cik=34088, form='8-K',
                    filing_date='2026-05-01', accession_no='0000034088-26-000065')
    eightk = filing.obj()

    assert eightk.items == ['Item 2.02', 'Item 7.01']


def test_extract_items_anchors():
    """The relaxed anchor adds the after-a-rule case and nothing else."""
    # Item glued onto a horizontal rule (the GMAC shape).
    glued = "-" * 60 + "Item 4.02 Non-Reliance on Previously Issued Financial Statements\n"
    assert _extract_items_from_text(glued) == ['4.02']

    # Other rule characters and a rule followed by spaces.
    assert _extract_items_from_text("=" * 8 + "Item 2.02 Results\n") == ['2.02']
    assert _extract_items_from_text("_" * 8 + "  Item 7.01 Regulation FD\n") == ['7.01']

    # Item at the start of a line, indented or not.
    assert _extract_items_from_text("Item 8.01 Other Events\n") == ['8.01']
    assert _extract_items_from_text("    Item 8.01 Other Events\n") == ['8.01']

    # Mid-sentence references are not items.
    assert _extract_items_from_text("as described in Item 8.01 above\n") == []
    assert _extract_items_from_text("The adjustments in Item 4.02 and Item 8.01.\n") == []

    # A short run of dashes is punctuation, not a rule — "Item 1-Item 4" still yields
    # only Item 1, as it did before the change.
    assert _extract_items_from_text("Item 1-Item 4.  Not applicable.\n") == ['1']

    # Realistic mix: rule-glued header, line-start header, mid-sentence back-reference.
    text = (
        "check the appropriate box\n\n"
        + "-" * 60 + "Item 4.02 Non-Reliance on Previously Issued Financial Statements\n\n"
        "GMAC concluded that its statements should no longer be relied upon.\n\n"
        "Item 8.01 Other Events\n\n"
        "The restatements described in Item 4.02 were evaluated.\n"
    )
    assert _extract_items_from_text(text) == ['4.02', '8.01']


def test_extract_item_content_anchors():
    """Content extraction uses the same anchor for both section boundaries."""
    text = (
        "check the appropriate box\n\n"
        + "-" * 60 + "Item 4.02 Non-Reliance on Previously Issued Financial Statements\n\n"
        "GMAC concluded that its statements should no longer be relied upon.\n\n"
        "Item 8.01 Other Events\n\n"
        "The restatements described in Item 4.02 were evaluated.\n"
    )

    content = _extract_item_content_from_text(text, 'Item 4.02')
    assert content is not None
    # Starts at the header, not at the rule the anchor consumed.
    assert content.startswith('Item 4.02 Non-Reliance')
    assert 'no longer be relied upon' in content
    # Ends at the next item header.
    assert 'Item 8.01' not in content

    item_801 = _extract_item_content_from_text(text, '8.01')
    assert item_801 is not None
    assert item_801.startswith('Item 8.01 Other Events')
    assert 'were evaluated' in item_801

    # A mid-sentence reference alone does not make a retrievable section.
    assert _extract_item_content_from_text("see Item 5.02 for details\n", 'Item 5.02') is None

    # A rule-glued header ends the preceding section.
    two_sections = (
        "Item 2.02 Results of Operations\n\n"
        "Revenue grew.\n"
        + "=" * 40 + "Item 9.01 Financial Statements and Exhibits\n\n"
        "Exhibit 99.1\n"
    )
    first = _extract_item_content_from_text(two_sections, '2.02')
    assert first is not None
    assert 'Revenue grew' in first
    assert 'Item 9.01' not in first
    assert '=====' not in first
