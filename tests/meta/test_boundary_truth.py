"""Boundary truth set: start-exact and end-exact rates (edgartools-llmp.11).

Before this file, nothing measured whether a section's START or END was
right. The parity ratchet counts items found; the boundary corpus pins text
lengths captured from the pipeline itself, which catch drift and prove
nothing. ``tests/fixtures/parser_corpus/boundary_truth.json`` is the first
independent record: for each fixture and item, the first and last 80
characters of the correct slice, whitespace-collapsed, read against the
rendered filing on 2026-10-11. Each item carries ``verified``:

    "eye"    the boundary was read and is right as recorded
    "wrong"  the pipeline's boundary is known to be wrong; ``start``/``end``
             hold the correct text where it could be established and null
             where it could not, so the item scores as a miss either way
    "title"  the filer prints no "Item N" label; the slice correctly opens on
             the section title (JPMorgan, Edison, Citi's index path)

The scorer reports start-exact, end-exact and both, by form, and this file
pins the rates as a ratchet: a detector change that moves a boundary that was
right fails here, and one that fixes a "wrong" item must flip it to "eye" in
the same commit (``test_fixed_items_are_relabelled``).

Fixtures are the tracked ``html/``, ``parity_gate/`` and ``heldout_retired/``
trees only, so every item here is measured on CI; the gitignored era corpus
is deliberately absent.
"""
import sys

import pytest

from tests.paths import FIXTURES_DIR

sys.path.insert(0, str(FIXTURES_DIR / "parser_corpus"))
import scoring  # noqa: E402

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def truth():
    return scoring.load_truth()


@pytest.fixture(scope="module")
def corpus():
    return {(e["label"], e["form"]): e for e in scoring.consistency_corpus()}


@pytest.fixture(scope="module")
def scored(truth, corpus):
    """{(label, form): {section: {found, start, end}}} for every truth fixture present."""
    out = {}
    for entry in truth["fixtures"]:
        key = (entry["fixture"], entry["form"])
        e = corpus.get(key)
        assert e is not None and e["tracked"], f"truth fixture {key} is not in the tracked corpus"
        live = scoring.measure_sections(e["path"], e["form"])
        out[key] = scoring.score_truth(entry, live)
    return out


def _rates(truth, scored, form):
    n = start = end = both = 0
    for entry in truth["fixtures"]:
        if entry["form"] != form:
            continue
        for name in entry["items"]:
            got = scored[(entry["fixture"], entry["form"])][name]
            n += 1
            start += got["start"]
            end += got["end"]
            both += got["start"] and got["end"]
    return n, start, end, both


# Pinned 2026-10-11 on fix/llmp12-running-header-strip (page-furniture start). Counts, not
# percentages, so a one-item regression is visible. Update in the same commit
# as a detector change that moves them, and say which items moved.
PINNED = {
    # form: (items, start_exact, end_exact, both)
    # 2026-10-12 (llmp.11.2): +33 pattern-path items the harness could not see
    # while it keyed on section names ('mda', 'business'): 28 eye, 5 wrong
    # (ge 1/1C/9A, 0000950153-99-001234 7, 0001193125-21-101193 1B).
    # 2026-10-12 (llmp.12.2): GE's missing items come from its cross-reference
    # index, not the pattern pass: 1/1C/9A wrong -> title, +2/10 title, +5 and
    # +7A wrong (page-granular index slices open mid-page).
    # 2026-10-12 (llmp.12.2): another item's header ends a pattern item at any
    # heading level; 0000950153-99-001234 Items 5 and 7 wrong -> eye.
    # 2026-10-13 (llmp.12): an exhibit index or schedule printed after Item 16
    # is its own exhibit_index section and Item 16 ends at its own text, a
    # policy decision that relabelled ma, orcl, es and 915358 Item 16 from
    # wrong (they ran through the index) to eye; Southern's Item 16 no longer
    # anchors on an inline-XBRL fact id in Item 15 (Items 15, 16 wrong -> eye);
    # ExxonMobil's "FINANCIAL SECTION" divider is trailing furniture and cvx's
    # index is split off (Item 16 wrong -> eye on both).
    # 2026-10-14 (llmp.12.1): eight held-out 10-Ks retired to heldout_retired with
    # their blind labels (+157 items: 131 eye, 26 wrong; heldout/README.md v2).
    # 2026-10-14 (llmp.12.1): an anchor's preceding block lines are not its
    # heading (TechPrecision's own PART dividers, Item 9/9A); the start pass
    # walks from where the slice starts (Vasomedical's PART I); a "PART II /
    # ITEM 7A" breadcrumb is furniture (Plum Creek); HTML comments no longer
    # print in section text (Bright Green's page-number field codes); an
    # open-ended section's final page number is dropped (Bright Green Item 8,
    # 915358 Item 8 relabelled without "F-45"); pattern sections drop trailing
    # page numbers ("- 22 -", Landec) and backlinks (xom 10-Q Item 1 wrong ->
    # eye). Retired items: 26 wrong -> 6.
    "10-K": (934, 908, 880, 874),   # 97.2% / 94.2% / 93.6%
    "10-Q": (111, 110, 108, 107),   # 99.1% / 97.3% / 96.4%
}


def test_rates_have_not_fallen(truth, scored):
    worse = {}
    for form, (n, start, end, both) in PINNED.items():
        live = _rates(truth, scored, form)
        if live[0] != n or live[1] < start or live[2] < end or live[3] < both:
            worse[form] = {"pinned": (n, start, end, both), "live": live}
    assert not worse, f"boundary accuracy fell (items, start, end, both): {worse}"


def test_rates_are_repinned_when_they_improve(truth, scored):
    better = {}
    for form, (n, start, end, both) in PINNED.items():
        live = _rates(truth, scored, form)
        if live[0] == n and (live[1] > start or live[2] > end or live[3] > both):
            better[form] = {"pinned": (n, start, end, both), "live": live}
    assert not better, f"boundary accuracy improved; re-pin PINNED so the ratchet tightens: {better}"


def test_eye_verified_items_are_exact(truth, scored):
    """Every item a person verified must still score exact on both sides."""
    misses = []
    for entry in truth["fixtures"]:
        for name, want in entry["items"].items():
            if want["verified"] != "eye":
                continue
            got = scored[(entry["fixture"], entry["form"])][name]
            if not (got["found"] and got["start"] and got["end"]):
                misses.append((entry["fixture"], name, got))
    assert not misses, "eye-verified boundaries moved:\n" + "\n".join(
        f"  {f} {n}: {g}" for f, n, g in misses
    )


def test_fixed_items_are_relabelled(truth, scored):
    """An item recorded as wrong that now matches its correct text must be relabelled 'eye'."""
    fixed = []
    for entry in truth["fixtures"]:
        for name, want in entry["items"].items():
            if want["verified"] != "wrong":
                continue
            got = scored[(entry["fixture"], entry["form"])][name]
            if got["found"] and got["start"] and got["end"]:
                fixed.append((entry["fixture"], name))
    assert not fixed, f"these 'wrong' items now match their correct text; relabel them 'eye': {fixed}"
