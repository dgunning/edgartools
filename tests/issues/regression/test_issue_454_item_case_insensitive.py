"""TenK item lookup is case-insensitive, offline (GH #454, edgartools-3dp Group B).

``test_issue_454_get_item_with_part.py`` covers this, but every test in it is
network-marked, so the gap it guards was invisible to the fast suite and only
surfaced in the 21-minute regression job. This file pins the same contract on a
tracked fixture.

WHAT BROKE. ``TenK.__getitem__`` matched the item spelling two ways, both
case-sensitive: ``normalized.startswith('Item ')`` when deriving the item
number, and ``normalized in item_to_section`` when mapping to a friendly section
name. So ``'Item 7'`` resolved, ``'item 7'`` resolved by accident through a
different branch, and ``'ITEM 7'`` resolved through neither. On main that never
showed, because the legacy chunked parser sat underneath and lowercased its
keys; Group B deleted that fallback and the latent gap became a live miss.

TenQ, TwentyF and CurrentReport were already case-insensitive here -- TenK was
the only one of the four that was not.

WHY BOTH FIXTURES. The two halves of the bug live on different lookup paths, and
a filing exercises one or the other depending on how its sections were detected.
Where the detector produces part-qualified keys (``part_ii_item_7``) the item
number path answers; where it produces friendly names (``business``, ``mda``)
the mapping path answers. The 1999 gate fixture is a friendly-name filing, so it
would NOT have caught the item-number half on its own -- which is how the
incomplete first fix passed a network probe and still left the fixture broken.
"""
import pathlib

import pytest

from edgar.company_reports.ten_k import TenK

pytestmark = pytest.mark.fast

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
GATE_10K = FIXTURES / "parity_gate" / "10-K" / "0000950153-99-001234.html"


class FixtureFiling:
    filing_date = None

    def __init__(self, path: pathlib.Path, form: str):
        self._path = path
        self.form = form
        self.company = "fixture"
        self.accession_number = path.stem
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")


def _tenk():
    assert GATE_10K.exists(), f"missing tracked fixture {GATE_10K}"
    return TenK(FixtureFiling(GATE_10K, "10-K"))


@pytest.mark.parametrize("spelling", ["Item 1", "item 1", "ITEM 1", "iTeM 1", "Item  1"])
def test_getitem_accepts_any_casing(spelling):
    """Same item, same text, however the caller spells it.

    Asserted as equality against the canonical spelling rather than as
    "not None": a branch that returned SOME item for 'ITEM 1' would satisfy a
    None-check while quietly answering with the wrong section.
    """
    tenk = _tenk()
    canonical = tenk["Item 1"]

    assert canonical, "the canonical spelling must answer, or this proves nothing"
    assert tenk[spelling] == canonical


@pytest.mark.parametrize("item", ["Item 1", "ITEM 1", "item 1"])
def test_get_item_with_part_accepts_any_casing(item):
    """The exact call from the issue, which is what CI caught."""
    tenk = _tenk()
    canonical = tenk.get_item_with_part("Part I", "Item 1", markdown=False)

    assert canonical
    assert tenk.get_item_with_part("Part I", item, markdown=False) == canonical


def test_a_combined_item_heading_is_not_read_as_an_item_number():
    """The boundary the case-insensitive pattern has to respect.

    ``Items 1 and 2`` is a real 10-K heading. A pattern loose enough to accept
    ``ITEM 1`` must still not read ``Items 1 and 2`` as item ``s 1 and 2``, so
    the whitespace after the word is required rather than optional.
    """
    from edgar.company_reports.ten_k import _ITEM_PREFIX

    assert _ITEM_PREFIX.match("ITEM 7").group(1) == "7"
    assert _ITEM_PREFIX.match("Item  7").group(1) == "7"
    assert _ITEM_PREFIX.match("Items 1 and 2") is None
    assert _ITEM_PREFIX.match("itemize") is None


def test_an_item_the_filing_lacks_is_still_a_miss_in_every_casing():
    """Case-insensitivity must not turn a genuine absence into a false hit.

    This 1999 filing predates Item 1A (added 2005), so both spellings must miss.
    Without this, a fix that made lookups permissive enough to match anything
    would pass every other test in this file.
    """
    tenk = _tenk()

    assert tenk.get("Item 1A") is None
    assert tenk.get("ITEM 1A") is None
