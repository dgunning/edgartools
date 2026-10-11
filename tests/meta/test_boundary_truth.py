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

Fixtures are the tracked ``html/`` and ``parity_gate/`` trees only, so every
item here is measured on CI; the gitignored era corpus is deliberately
absent.
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


# Pinned 2026-10-11 on fix/llmp12-part-divider-bound (10-K; 10-Q unchanged). Counts, not
# percentages, so a one-item regression is visible. Update in the same commit
# as a detector change that moves them, and say which items moved.
PINNED = {
    # form: (items, start_exact, end_exact, both)
    "10-K": (739, 616, 650, 562),   # 83.4% / 88.0% / 76.0%
    "10-Q": (111, 96, 107, 92),     # 86.5% / 96.4% / 82.9%
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
