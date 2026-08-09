"""New-vs-legacy full-document markdown parity ratchet (edgartools-zqjn, GH #886).

The sibling of ``test_section_parity_ratchet.py``, and it exists for the same
reason: a measurement nobody re-runs is a measurement that gets lost. The
section half of ``zqjn`` lost its original benchmark and five months of progress
with it. This pins the markdown half from the day it was first measured.

WHAT IT GUARDS. ``Filing.markdown()`` is the last public rendering method still
on the legacy parser (``_filings.py:1746``). Rerouting it to ``edgar.documents``
fixes GH #886 — images are dropped today and the new parser renders them, 252 of
them across this corpus — but the new renderer's output is also ~26% shorter on a
10-K, and shorter is either compaction or content loss.

``BASELINE_NUMBER_LOSS`` is how much of legacy's numeric content each tracked
filing currently loses, measured 2026-08-07. The assertion is one-directional,
mirroring the section ratchet: the loss may shrink freely, and any *increase*
fails. So work on the exhibit-index bug (``edgartools-2vzk``) needs no change
here until a filing reaches zero, while a change that starts dropping a table
somewhere else turns this red.

Numbers, not words or characters — ``markdown_parity.py``'s module docstring
explains why at length, and it is worth reading before touching a threshold
here. Briefly: characters cannot distinguish compaction from loss, word counts
are dominated by legacy's repeated table headers, and numbers are the only
signal a reformat cannot move.

WHAT IS AND IS NOT MEASURED IN CI. Same split as the section ratchet.
``tests/fixtures/html`` and ``tests/fixtures/parity_gate`` are tracked (61 of the
115 fixtures); ``tests/fixtures/text_boundary_corpus`` is gitignored, so the
era-stratified filings exist on developer machines only. Only tracked fixtures
are pinned here, so the baseline means the same thing in both places — and
``test_the_tracked_corpus_is_present`` fails if the tracked half goes missing,
because "measured nothing" must never read as "nothing wrong".
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures" / "parser_corpus"))
import markdown_parity  # noqa: E402
import parity_benchmark  # noqa: E402

# Offline, but renders the whole corpus through two markdown pipelines. ~220s for
# all 115 fixtures locally, less in CI where the era corpus is absent. Slow lane.
pytestmark = pytest.mark.slow


# Distinct numeric values each filing renders in legacy markdown and NOT in new,
# measured 2026-08-07 on main (4bb2c3e0). Tracked fixtures only.
#
# REBASELINED 2026-08-07 after edgartools-2vzk. Fixing the exhibit index took the
# corpus-wide total from 1965 to 1191 distinct values (-39%) with zero filings
# regressing, and six tracked filings now lose nothing at all.
#
# It did NOT empty this dict, which the pre-fix note predicted it would. What is
# left is a different and more mixed population, and the largest part of it looks
# like it is not our bug: unh/10k's residual is values such as 10000.55 and
# 10001.15, i.e. LEGACY running two numbers together, the numeric counterpart of
# the word-gluing that glued() already discounts. Extending that discount to
# numbers is the next refinement to the harness, and would likely drop this
# baseline again without any parser change.
#
# The real remaining signal is the executive-officers table ('executive',
# 'officer', 'president' in the word shortfalls, e.g. adbe/10k).
#
# REBASELINED AGAIN 2026-08-09 after edgartools-y264, which took the tracked
# total from 902 to 739 (-18%) with zero filings regressing. Thirteen entries
# moved. That the corpus-wide effect is an order of magnitude larger than the
# filing it was found on is the point worth keeping: y264 started as "why does
# unh/10k still lose 82?" and the answer was two more branches of
# _is_header_row missing a figures veto, which were quietly collapsing tables
# in a dozen other filings too — msft/10q 68 -> 8, msft/10k 57 -> 15,
# amzn/10k 34 -> 13, meta/10k 53 -> 39.
#
# The gluing hypothesis above was also settled, and it holds: of unh/10k's
# remaining 74, 69 are legacy running a principal into a coupon ($1,000 +
# 2.875% -> $1,0002.875%) and 5 are page-number footers the new parser is right
# to drop. Nothing in that filing's residual is content the new renderer loses.
# So the harness refinement is still worth doing, and is now known to be the
# ONLY thing left on unh/10k rather than a guess about most of it.
BASELINE_NUMBER_LOSS = {
    ("8-K", "0000887919-21-000012"): 2,
    ("20-F", "0001062993-16-008650"): 42,
    ("20-F", "0001062993-21-003193"): 22,
    ("10-Q", "aapl/10q"): 10,
    ("10-Q", "ba/10q"): 1,
    ("10-Q", "gbdc/10q"): 24,
    ("10-Q", "gs/10q"): 6,
    ("10-Q", "hubs/10q"): 18,
    ("10-Q", "ibm/10q"): 6,
    ("10-Q", "jnj/10q"): 1,
    ("10-Q", "jpm/10q"): 6,
    ("10-Q", "ko/10q"): 2,
    ("10-Q", "msft/10q"): 8,
    ("10-Q", "nflx/10q"): 6,
    ("10-Q", "nvda/10q"): 2,
    ("10-Q", "pg/10q"): 24,
    ("10-Q", "tsla/10q"): 4,
    ("10-Q", "unp/10q"): 2,
    ("10-K", "915358/10k"): 25,
    ("10-K", "abbv/10k"): 4,
    ("10-K", "adbe/10k"): 16,
    ("10-K", "amzn/10k"): 13,
    ("10-K", "axp/10k"): 18,
    ("10-K", "ba/10k"): 14,
    ("10-K", "bac/10k"): 5,
    ("10-K", "c/10k"): 2,
    ("10-K", "cat/10k"): 17,
    ("10-K", "crm/10k"): 26,
    ("10-K", "cvx/10k"): 4,
    ("10-K", "gbdc/10k"): 67,
    ("10-K", "gs/10k"): 9,
    ("10-K", "hd/10k"): 32,
    ("10-K", "hubs/10k"): 24,
    ("10-K", "jnj/10k"): 7,
    ("10-K", "jpm/10k"): 1,
    ("10-K", "ko/10k"): 3,
    ("10-K", "ma/10k"): 2,
    ("10-K", "meta/10k"): 39,
    ("10-K", "ms/10k"): 6,
    ("10-K", "msft/10k"): 15,
    ("10-K", "nflx/10k"): 21,
    ("10-K", "nke/10k"): 7,
    ("10-K", "nvda/10k"): 16,
    ("10-K", "orcl/10k"): 7,
    ("10-K", "pfe/10k"): 3,
    ("10-K", "rf/10k"): 4,
    ("10-K", "tsla/10k"): 22,
    # Was 186 until the two-up maturity-row fix (edgartools-v3ec) restored
    # the long-term debt schedule. Re-banked rather than left at 186: the
    # "do not re-bank a decrease" rule above is about renderer noise of a
    # point or two, and leaving a 104-point drop unbanked would let the
    # schedule regress all the way back without tripping anything.
    #
    # Then 82 until edgartools-y264 restored the buyback table and the
    # stock-option assumptions. The 74 left are all accounted for and none of
    # them are ours: 69 legacy gluings and 5 page-number footers. This entry
    # will not reach zero by fixing the parser — only by teaching the harness
    # to discount glued numbers the way it already discounts glued words.
    ("10-K", "unh/10k"): 74,
    ("10-K", "unp/10k"): 7,
    ("10-K", "v/10k"): 13,
    ("10-K", "wfc/10k"): 15,
    ("10-K", "wmt/10k"): 14,
    ("10-K", "xom/10k"): 1,
}

# Tracked filings that already lose nothing. Kept as a separate set rather than
# as zero-valued entries above, because "already correct" and "known broken by
# this much" are different claims and only one of them is a work item.
CLEAN_FILINGS = {
    ("8-K", "0001104659-03-004925"),
    # Reached zero via edgartools-v3ec: its remaining two lost numbers were in a
    # table whose rows were being classified as headers.
    ("10-K", "googl/10k"),
    # Reached zero via edgartools-y264. Its last lost number was 6.65 — the top
    # of the interest-rate range "0.03% – 6.65%" in the term-debt table, in a
    # row whose range cells were being counted as text.
    ("10-K", "aapl/10k"),
    ("8-K", "0001437749-16-028287"),
    ("20-F", "0000928385-01-500187"),
    ("10-Q", "xom/10q"),
    ("10-K", "ibm/10k"),
    ("10-K", "pg/10k"),
}

TRACKED = set(BASELINE_NUMBER_LOSS) | CLEAN_FILINGS

# Legacy renders no images at all — that is GH #886 in one number. Pinned as a
# floor so a renderer change that silently stops emitting them is caught here
# rather than after the reroute ships.
BASELINE_NEW_IMAGES = 252

# Fixtures available when the gitignored era corpus IS present, i.e. on a
# developer machine. The image floor above was counted over all of them, so it
# only applies to a run that measured all of them; CI sees 61 and gets the weaker
# assertion. Named rather than inlined so the two numbers stay legibly related.
FULL_CORPUS_SIZE = 115


@pytest.fixture(scope="module")
def measured():
    """Render whatever corpus this environment actually has, both ways.

    Returns results keyed by (form, label) plus the set of labels present, since
    every assertion below has to tell "no loss" apart from "never looked".
    """
    corpus = parity_benchmark.build_corpus(parity_benchmark.GATE_FORMS)
    assert corpus, "fixture corpus is missing entirely — nothing was measured"
    results = {}
    for entry in corpus:
        row = markdown_parity.measure_markdown(entry)
        results[(row["form"], row["label"])] = row
    return results, set(results)


class TestRerouteLosesNoMoreThanRecorded:
    """The reroute gate: no filing may start losing numbers it was not already."""

    def test_no_filing_loses_more_numbers(self, measured):
        results, _present = measured
        regressions = {}
        for key, row in results.items():
            if key not in TRACKED or not row["scored"]:
                continue
            allowed = BASELINE_NUMBER_LOSS.get(key, 0)
            if row["missing_number_total"] > allowed:
                regressions[key] = (
                    f"{row['missing_number_total']} lost, baseline {allowed}; "
                    f"e.g. {row['missing_numbers'][:6]}"
                )
        assert not regressions, (
            "the new renderer now drops numbers the legacy one renders, on "
            f"filings where that was not previously true (or not this badly): "
            f"{regressions}"
        )

    def test_clean_filings_stay_clean(self, measured):
        results, present = measured
        dirty = {
            key: results[key]["missing_numbers"][:6]
            for key in CLEAN_FILINGS
            if key in present and results[key]["scored"]
            and results[key]["missing_number_total"] > 0
        }
        assert not dirty, (
            f"these filings previously retained every number and no longer do: {dirty}"
        )

    def test_a_repaired_filing_is_banked(self, measured):
        """The ratchet's other half: move a filing to CLEAN_FILINGS when it is fixed.

        Not a parser failure — a failure to bank the win. Left unbanked, the
        baseline keeps permitting a loss that no longer exists and the guard
        quietly loosens. Only filings this environment could measure count; an
        absent fixture has not been repaired.

        Deliberately triggers only at zero, not on any decrease. Counts drift by
        one or two whenever the renderer changes at all, and a ratchet that has
        to be re-banked on every unrelated commit gets disabled instead of read.
        """
        results, present = measured
        repaired = {
            key: baseline
            for key, baseline in BASELINE_NUMBER_LOSS.items()
            if key in present and results[key]["scored"]
            and results[key]["missing_number_total"] == 0
        }
        assert not repaired, (
            "these filings now lose nothing — move them from BASELINE_NUMBER_LOSS "
            f"to CLEAN_FILINGS in the same commit that fixed them: {repaired}"
        )


class TestTheRerouteStillBuysWhatItIsFor:

    def test_the_new_renderer_still_emits_images(self, measured):
        """GH #886 is the reason to reroute; guard the thing being bought."""
        results, _present = measured
        scored = [r for r in results.values() if r["scored"]]
        new_images = sum(r["new"]["images"] for r in scored)
        legacy_images = sum(r["legacy"]["images"] for r in scored)
        assert legacy_images == 0, (
            f"legacy markdown rendered {legacy_images} images — if that is now "
            "true, GH #886's premise has changed and this file needs revisiting"
        )
        # Floor, not equality: the corpus in CI is smaller than the local one.
        full_run = len(scored) >= FULL_CORPUS_SIZE
        expected = BASELINE_NEW_IMAGES if full_run else 1
        assert new_images >= expected, (
            f"the new renderer emitted {new_images} images, expected at least "
            f"{expected}. Rerouting Filing.markdown() is supposed to FIX image "
            "loss; if this drops, it no longer does."
        )


class TestTheCorpusItselfIsIntact:
    """Guards against the measurement quietly shrinking to nothing."""

    def test_the_tracked_corpus_is_present(self, measured):
        _results, present = measured
        missing = sorted(TRACKED - present)
        assert not missing, (
            f"tracked fixtures absent from the corpus: {missing}. The parity "
            "assertions cannot mean anything without them."
        )

    def test_neither_renderer_crashes(self, measured):
        results, _present = measured
        errors = [(k, r["new_error"] or r["legacy_error"])
                  for k, r in results.items()
                  if r["new_error"] or r["legacy_error"]]
        assert not errors, f"renderer raised on: {errors}"

    def test_the_legacy_pipeline_still_produces_markdown(self, measured):
        """No fixture may newly fall back to the ``<pre>`` escape hatch.

        Zero today. A filing joining this set is not a parity finding — it means
        ``get_clean_html`` stopped rooting HTML it used to handle, which would
        silently remove that filing from every rate above.
        """
        results, _present = measured
        degraded = sorted(k for k, r in results.items() if r["legacy_degraded"])
        assert not degraded, (
            f"legacy markdown degraded to a <pre> block on: {degraded}"
        )
