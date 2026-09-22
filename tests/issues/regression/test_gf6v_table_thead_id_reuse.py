"""Table rows were dropped at random because `<thead>` rows were deduplicated by a dead
object's id().

bead edgartools-gf6v.

`_process_table_structure` recorded `id(tr)` for every `<thead>` row, then skipped any tbody
row whose `id(tr)` was in that set. Nothing held the thead proxies alive. lxml materializes
element proxies on demand and frees them when the last reference goes, and CPython reuses the
freed address — so a tbody row could be handed a recycled id, match the stale thead id, and be
silently `continue`d out of the table. A filed row simply disappeared, with no error.

The identical hazard is already documented and correctly handled a few files away, in
`edgar/documents/utils/toc_analyzer.py` (see the comment above `seen_row_ids`, which holds
every row in a list for exactly this reason). This site was missed.

HOW IT SURFACED: `test_issue_rck1_sgml_text_ownership_xml.py` asserts
`filing.sgml().text() == filing.text()`. Both render byte-identical HTML through a
deliberately identical pipeline, so they must agree — but each renders its own Document, and
whichever one hit the collision lost a row. Measured on the ABRAMS Form 4
(0000001923-04-000001): 1 to 22 divergences per 25 in-process iterations before the fix, 0 in
100 after. That is why the regression lane went red at random.

WHY THE TEST IS SHAPED THIS WAY. The bug is probabilistic — it needs a real allocation and GC
pattern, and does not reproduce in a tight loop over saved HTML (400 parses, all identical).
Two tempting tests do NOT gate it, and both were tried and rejected here:
  * stress-running the real filing — the observed rate goes as low as 1 in 25, so even 50
    iterations miss it often, and it needs the network;
  * asserting the thead proxies are still alive at tbody time — this PASSES on the unfixed
    code, because the tree keeps them alive under the conditions a unit test creates.
So the fix does not rely on liveness at all: the dedup no longer uses `id()`. Membership is
tested by identity against a list that is held for the whole function, which makes the
collision impossible by construction. That IS deterministically testable — force `id()` to
collide and assert the row survives anyway, which is what the first test below does. It fails
on the old code for the real reason rather than by luck.
"""

import pytest
from lxml import html as lxml_html

from edgar.documents.config import ParserConfig
from edgar.documents.strategies import table_processing
from edgar.documents.strategies.table_processing import TableProcessor
from edgar.documents.table_nodes import TableNode


TABLE_HTML = """
<table>
  <thead><tr><th>Header A</th><th>Header B</th></tr></thead>
  <tbody>
    <tr><td>row one</td><td>1</td></tr>
    <tr><td>row two</td><td>2</td></tr>
  </tbody>
</table>
"""


def _process():
    processor = TableProcessor(ParserConfig(form='4'))
    table = TableNode()
    processor._process_table_structure(lxml_html.fromstring(TABLE_HTML), table)
    return table


def test_a_row_survives_even_when_its_id_collides_with_a_thead_row(monkeypatch):
    """Simulate the id() reuse that CPython performs after lxml frees a thead proxy.

    `id` is shadowed inside the table_processing module so that EVERY element reports the
    same value. On the old id()-keyed code that makes every tbody row look like a thead row
    already processed, and all of them are skipped. The fix compares identity, so a collided
    id changes nothing.
    """
    monkeypatch.setattr(table_processing, "id", lambda obj: 0xC0FFEE, raising=False)

    table = _process()

    assert len(table.rows) == 2, (
        f"expected both tbody rows, got {len(table.rows)} — a row whose id() collides with "
        "a thead row is being skipped as 'already processed'. That is exactly what happens "
        "in production when lxml frees a thead proxy and CPython reuses the address."
    )
    assert len(table.headers) == 1


def test_the_ordinary_case_is_unchanged():
    """Control: with no collision, headers and rows split the normal way.

    Must pass both before and after the fix — it exists to show the first test fails for the
    collision and not because the fixture or the processor is broken.
    """
    table = _process()

    assert len(table.headers) == 1
    assert len(table.rows) == 2


def test_thead_rows_are_not_duplicated_into_the_body():
    """Control: the dedup still does its job — a thead row must not also appear as a row."""
    table = _process()

    body_text = " ".join(
        str(getattr(cell, "content", cell))
        for row in table.rows
        for cell in row.cells
    )
    assert "Header A" not in body_text, (
        "the thead row leaked into the body — the dedup stopped working"
    )
