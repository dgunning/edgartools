"""
Regression test for issue #826.

`Section.tables()` returned each underlying <table> element many times
(up to ~24x on deeply nested 20-F sections) because
`Section._extract_section_html` walked the entire section subtree with
`etree.iterwalk` and serialized EVERY collected element via `tostring()`.
Since `tostring(elem)` includes the element's full subtree, a <table>
nested under collected ancestors was emitted once for itself plus once
for each ancestor — inflating the table count returned by
`_get_tables_from_toc_section`.

The fix only serializes "top-level" collected elements (those whose
parent is not also in the collected set), so each <table> appears exactly
once in the reassembled section HTML.

Ground truth (verified by hand against the live filings):
  AAPL 10-K 0000320193-25-000079  part_ii_item_8 : 123 -> 34 (34 unique)
  AAPL 10-Q 0000320193-25-000073  part_i_item_1  :  58 -> 17 (17 unique)
  TSM  20-F 0001628280-26-025362  part_iii_item_19: 1149 -> ~150

The 20-F section is the high-multiplier (x24) case. It is NOT fully
dup-free even after the fix — a *separate* anchor-boundary overlap bug
leaves a small cross-section residual (worst x4) — so its assertion only
guards that the nested-serialization explosion (this bug) is gone.
"""
import hashlib
from collections import Counter

import pytest

import edgar


def _html_of(table_node):
    html = table_node.html
    return html() if callable(html) else html


def _hash_counts(tables):
    return Counter(hashlib.sha1(_html_of(t).encode("utf-8")).hexdigest() for t in tables)


@pytest.mark.network
def test_section_tables_no_duplication_aapl_10k():
    """part_ii_item_8 of AAPL's 10-K must return each table exactly once."""
    typed = edgar.find("0000320193-25-000079").obj()
    section = typed.sections["part_ii_item_8"]

    tables = section.tables()
    counts = _hash_counts(tables)

    # 34 distinct tables, each appearing exactly once (pre-fix: 123 total / 34 unique)
    assert len(tables) == 34, f"expected 34 tables, got {len(tables)}"
    assert len(counts) == 34, f"expected 34 unique tables, got {len(counts)}"
    assert max(counts.values()) == 1, (
        f"tables duplicated: worst single dup x{max(counts.values())}"
    )
    # Distinct TableNode objects (the duplication was real serialization, not
    # the same object yielded twice).
    assert len({id(t) for t in tables}) == len(tables)

    # The fix only removes redundant serialization — it must not drop content.
    assert len(section.text()) == 60874


@pytest.mark.network
def test_section_tables_no_duplication_aapl_10q():
    """A second form (10-Q) must also be fully dup-free after the fix."""
    typed = edgar.find("0000320193-25-000073").obj()
    section = typed.sections["part_i_item_1"]

    tables = section.tables()
    counts = _hash_counts(tables)

    # 17 distinct tables, each exactly once (pre-fix: 58 total / 17 unique)
    assert len(tables) == 17, f"expected 17 tables, got {len(tables)}"
    assert len(counts) == 17, f"expected 17 unique tables, got {len(counts)}"
    assert max(counts.values()) == 1, (
        f"tables duplicated: worst single dup x{max(counts.values())}"
    )


@pytest.mark.network
def test_section_tables_nested_explosion_gone_tsm_20f():
    """The deeply-nested 20-F path (pre-fix x24 / 1149 tables) must collapse.

    This section still has a small residual from a *separate* anchor-boundary
    overlap bug (worst ~x4), so we assert the nested-serialization explosion
    is gone rather than full dup-freedom.
    """
    typed = edgar.find("0001628280-26-025362").obj()
    section = typed.sections["part_iii_item_19"]

    tables = section.tables()
    counts = _hash_counts(tables)

    # Pre-fix: 1149 returned, worst single dup x24. Post-fix the count
    # collapses by ~8x and no table is replicated more than a handful of times.
    assert len(tables) < 300, f"expected <300 tables, got {len(tables)} (explosion not fixed)"
    assert max(counts.values()) <= 5, (
        f"nested-serialization duplication still present: worst x{max(counts.values())}"
    )
