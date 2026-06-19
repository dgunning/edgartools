"""Regression test for edgartools-t043: per-transaction footnote attribution.

Footnote references in a Form 4/5 transaction attach to many sub-elements
(securityTitle, transactionDate, transactionShares, transactionPricePerShare,
postTransactionAmounts, ...), not only <transactionCoding>. The extractor
previously collected footnoteIds from <transactionCoding> alone, so a footnote
attached elsewhere (e.g. a 10b5-1 disclosure on <securityTitle>) was dropped and
TransactionActivity.footnote_ids / .footnotes_text came through empty.

Follow-up to GitHub #863 (Problem 2): the summary-level has_10b5_1_plan had a
full-footnote fallback, but per-transaction footnote reasoning was still blind.

The 374Water Form 4 fixture is a real filing whose only transaction footnote
(F1) is attached to <securityTitle> with nothing under <transactionCoding> —
exactly the dropped-attribution case — so this runs offline.
"""

from pathlib import Path

import pytest

from edgar.ownership.core import get_footnotes
from edgar.ownership.forms import Form4

FIXTURE = Path('data/ownership/374WaterForm4.xml')

pytestmark = pytest.mark.skipif(not FIXTURE.exists(), reason='fixture not available')


def _summary():
    return Form4.parse_xml(FIXTURE.read_text()).get_ownership_summary()


def test_transaction_footnote_ids_are_populated_from_whole_transaction():
    """Each transaction surfaces the footnote attached to <securityTitle>."""
    summary = _summary()

    assert summary.transactions, "fixture should produce transactions"
    # Every transaction in this filing references footnote F1 (vesting terms),
    # attached to <securityTitle> — not <transactionCoding>.
    for t in summary.transactions:
        assert 'F1' in (t.footnote_ids or ''), f"missing F1 on {t.footnote_ids!r}"
        assert t.footnotes_text, "footnote text should resolve from the IDs"
        assert 'Vesting commencement' in t.footnotes_text


def test_footnote_ids_are_deduped_within_a_transaction():
    """A footnote referenced twice in one transaction is not resolved twice."""
    summary = _summary()

    for t in summary.transactions:
        ids = [i for i in (t.footnote_ids or '').split('\n') if i]
        assert len(ids) == len(set(ids)), f"duplicate footnote ids: {ids!r}"
        # Resolved text should not repeat the same footnote sentence.
        assert t.footnotes_text.count('Vesting commencement date') == 1


def test_get_footnotes_dedupes_preserving_order():
    """Unit check on the shared helper used by table extraction."""
    from bs4 import BeautifulSoup

    xml = (
        "<root>"
        "<securityTitle><footnoteId id='F1'/></securityTitle>"
        "<transactionShares><footnoteId id='F2'/></transactionShares>"
        "<transactionPricePerShare><footnoteId id='F1'/></transactionPricePerShare>"
        "</root>"
    )
    tag = BeautifulSoup(xml, 'xml').find('root')

    assert get_footnotes(tag) == 'F1\nF2'
