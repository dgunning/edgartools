"""`TwentyF.items` reads the new parser first (edgartools-07lk.3).

TwentyF was the last report class where the legacy ``ChunkedDocument`` was the
PRIMARY source of items; TenK, TenQ and CurrentReport had already flipped, using
legacy only as an empty-result fallback. Deleting ``edgar.files`` in 6.0 means
deleting ChunkedDocument, so every remaining primary use has to go first.

UPDATE (edgartools-07lk.23): the fallback this file was written around is now
gone from ``.items`` in TenK, TenQ and TwentyF alike — measured to change no
result on any of 115 era-stratified fixtures. See
``TestLegacyIsNotConsultedAtAll`` below, which replaced the class that pinned the
old fallback contract.

Its in-code justification for staying legacy-first — that "the pattern-based
extractor doesn't handle the Table of Contents format well" — did not survive
measurement. On the one 20-F where legacy clearly beat the new parser, TOC
detection returned no sections at all, so the TOC path was not what was winning.
The cause was a coverage gate in the pattern extractor (edgartools-dt1f Defect 1;
see test_dt1f_item_coverage_gate.py), and with that fixed the corpus differential
for 20-F fell from 26 legacy-only items to 12.

Two things this pins beyond "the new parser is used":

1. **The output format.** Item numbers come from ``Section.item``, not from the
   section key. The key is not stable across detection strategies — the TOC path
   emits ``part_i_item_1`` and the pattern path emits ``item_1`` for the same
   item — so keying off it would have made ``.items`` return
   ``['part_i_item_1', ...]`` on most filings and ``['Item 1', ...]`` on the
   rest. ``Section.item`` is ``'1'`` either way.

2. **``.items`` and ``__getitem__`` agree.** ``__getitem__`` has read the new
   parser first for some time while ``.items`` read legacy, so the two could
   disagree about what a filing contained. Anything ``.items`` lists must be
   retrievable.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from edgar.company_reports import TwentyF


def _section(title, item):
    """The two fields ``.items`` reads off a Section."""
    return SimpleNamespace(title=title, item=item)

# Item headers as bold paragraphs, which the new parser resolves into sections.
ITEMS_HTML = "<html><body>" + "".join(
    f'<p><b>ITEM {num}. {title}</b></p><p>{"body text " * 40}</p>'
    for num, title in [
        ("1", "IDENTITY OF DIRECTORS, SENIOR MANAGEMENT AND ADVISERS"),
        ("3", "KEY INFORMATION"),
        ("4A", "UNRESOLVED STAFF COMMENTS"),
        ("5", "OPERATING AND FINANCIAL REVIEW AND PROSPECTS"),
        ("16A", "AUDIT COMMITTEE FINANCIAL EXPERT"),
        ("19", "EXHIBITS"),
    ]
) + "</body></html>"

# No item structure of any kind — the condition the legacy fallback exists for.
NO_ITEMS_HTML = "<html><body><p>A narrative with no item headings.</p></body></html>"


def _twenty_f(html):
    """A TwentyF over fixed HTML, with no network and no Filing construction."""
    filing = MagicMock()
    filing.form = "20-F"
    filing.html.return_value = html
    filing.accession_number = "0000000000-00-000000"
    filing.base_dir = None
    report = TwentyF.__new__(TwentyF)
    report._filing = filing
    return report


@pytest.mark.fast
class TestItemsComeFromTheNewParser:

    def test_items_are_found(self):
        assert _twenty_f(ITEMS_HTML).items == [
            'Item 1', 'Item 3', 'Item 4A', 'Item 5', 'Item 16A', 'Item 19'
        ]

    def test_items_are_in_canonical_order(self):
        """4A after 4, 16A after 16, 19 last — not lexicographic, not TOC order."""
        items = _twenty_f(ITEMS_HTML).items
        assert items.index('Item 5') < items.index('Item 16A') < items.index('Item 19')
        assert items.index('Item 4A') < items.index('Item 5')

    def test_no_section_keys_leak_into_items(self):
        for item in _twenty_f(ITEMS_HTML).items:
            assert item.startswith('Item '), f"{item!r} is not an item name"

    def test_the_three_key_shapes_all_produce_item_names(self):
        """The regression a naive flip would have shipped.

        The same item arrives under different section keys depending on which
        strategy detected it — ``part_i_item_1`` from the TOC engine's
        part-aware path, ``Item 1`` from its anchor path, ``item_1`` from the
        pattern extractor. All three are live on the 20-F corpus. Deriving the
        item name from the key would therefore return section keys on most
        filings, and the raw title on sections that are not items at all
        (``Part I``, ``Signatures``).
        """
        sections = {
            'part_i_item_1': _section('part_i_item_1', item='1'),
            'Item 3': _section('Item 3', item='3'),
            'item_16a': _section('Item 16A - Audit Committee', item='16A'),
            'part_i': _section('Part I', item=None),
            'signatures': _section('Signatures', item=None),
        }
        report = _twenty_f(ITEMS_HTML)
        report.__dict__['document'] = SimpleNamespace(sections=sections)
        assert report.items == ['Item 1', 'Item 3', 'Item 16A']

    def test_the_same_item_under_two_keys_is_listed_once(self):
        """A 20-F in the corpus carries both part_i_item_6 and part_iii_item_6."""
        report = _twenty_f(ITEMS_HTML)
        report.__dict__['document'] = SimpleNamespace(sections={
            'part_i_item_6': _section('part_i_item_6', item='6'),
            'part_iii_item_6': _section('part_iii_item_6', item='6'),
        })
        assert report.items == ['Item 6']

    def test_items_do_not_repeat(self):
        items = _twenty_f(ITEMS_HTML).items
        assert len(items) == len(set(items))


@pytest.mark.fast
class TestLegacyIsNotConsultedAtAll:
    """Superseded 07lk.23: legacy is not a fallback here any more, it is gone.

    This class used to assert the *fallback* contract — new parser first, legacy
    when it finds nothing. That fallback was deleted after measurement showed it
    changed `.items` on zero filings across the 115-fixture era-stratified corpus;
    Strategy 5c (edgartools-3dp) had closed its last live case, a 2001 20-F. The
    assertion that legacy answers when the new parser finds nothing is therefore
    no longer a description of this code, and pinning it would block the deletion
    it was written to enable.

    Note this is scoped to `.items`. `TwentyF.__getitem__` still falls back to
    legacy and still needs to: on the same corpus, five 20-F item lookups return
    text only because of it (0001144204-10-017467 Items 5, 6, 11, 12 and 15).
    """

    def test_legacy_is_not_consulted_when_the_new_parser_finds_items(self):
        """Asserted by construction rather than by output, because legacy and new
        agree on this document — if `.items` still built a ChunkedDocument the
        answer would look identical and the deletion would still be blocked.
        """
        report = _twenty_f(ITEMS_HTML)
        sentinel = MagicMock()
        report.__dict__['_chunked_document'] = sentinel
        assert report.items
        sentinel.list_items.assert_not_called()

    def test_legacy_is_not_consulted_when_the_new_parser_finds_nothing_either(self):
        """The 07lk.23 flip: an empty new-parser result is now the final answer."""
        report = _twenty_f(NO_ITEMS_HTML)
        legacy = MagicMock()
        legacy.list_items.return_value = ['Item 7']
        report.__dict__['_chunked_document'] = legacy

        assert report.items == []
        legacy.list_items.assert_not_called()

    def test_no_items_anywhere_is_an_empty_list(self):
        """Not None — `for item in report.items` must stay safe."""
        report = _twenty_f(NO_ITEMS_HTML)
        report.__dict__['_chunked_document'] = None
        assert report.items == []


@pytest.mark.fast
class TestItemsAndLookupAgree:

    def test_every_listed_item_can_be_retrieved(self):
        """`.items` read legacy while `__getitem__` read the new parser, so the
        two could disagree about what the filing contained."""
        report = _twenty_f(ITEMS_HTML)
        for item in report.items:
            assert report[item], f"{item} is listed by .items but {item!r} returns nothing"
