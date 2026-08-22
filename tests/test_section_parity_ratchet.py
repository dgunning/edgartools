"""New-vs-legacy section-extraction parity ratchet (edgartools-zqjn).

The gate for deleting ``edgar.files``/``ChunkedDocument`` (``07lk.3``) is
evidence that the new parser finds everything the legacy one finds. This test
pins that evidence so it stays true between now and the 6.0 freeze window,
instead of being re-discovered by hand — which is how the January-2026 baseline
was lost in the first place.

The measurement lives in ``tests/fixtures/parser_corpus/parity_benchmark.py``;
run it directly for the full report, per-form coverage, and the work list.

WHAT THIS GUARDS. ``BASELINE_GAPS`` is every (form, filing, item) the legacy
parser finds and the new one misses, as measured on 2026-08-05. The assertion is
a **subset** check, mirroring the anomaly census in
``test_section_boundary_corpus.py``: the live gap set may shrink freely, and any
*new* gap fails. So a fix that closes an entry needs no change here, while a
change that breaks a currently-clean filing turns this red.

That asymmetry is why ``wfc/10k`` is no longer listed at all: it now measures
clean, so any gap appearing on it is a *new* gap and fails. Removing a fixture
from ``BASELINE_GAPS`` tightens this guard rather than loosening it.

TWO CORPORA, AND ONLY ONE OF THEM REACHES CI. ``tests/fixtures/html`` is tracked.
``tests/fixtures/text_boundary_corpus`` — which holds every 8-K and 20-F fixture,
the two forms that gate the deletion — is **gitignored** (``.gitignore`` line 81,
91 MB), so it exists on developer machines and nowhere else. A CI run therefore
measures roughly half the baseline.

The first version of this file did not account for that and asserted against
whatever it happened to find, so on CI the twelve unmeasured entries looked like
twelve *fixed* gaps and the ratchet reported success at closing them. Absent is
not fixed. Entries whose fixture is missing are partitioned out and reported, and
``test_the_tracked_corpus_is_present`` fails if the tracked half goes missing too
— otherwise "measured nothing" would once again read as "nothing wrong".

Deliberately NOT asserted: the coverage percentages. They move with the corpus
and read as precision the sample size does not support. The differential is the
thing the deletion decision actually rests on.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures" / "parser_corpus"))
import parity_benchmark  # noqa: E402

# Offline, but re-parses the corpus through two parsers (~140s locally, less on
# CI where the era fixtures are absent). Slow lane.
pytestmark = pytest.mark.slow


# Measured 2026-08-05 on main. Each entry is a section the parser we plan to
# DELETE finds and the one we plan to KEEP does not.
#
# Three shapes are visible here, and they are the work list for dt1f:
#
#   1. Two systematic gaps on modern 10-Ks — Item 16 (Form 10-K Summary) on
#      axp/cvx/jnj and one era filing, Item 1C (Cybersecurity) on bac/jpm/tsla.
#      CLOSED 2026-08-14, and they were neither two problems nor detection
#      holes: both items were being found and discarded. The hybrid detector
#      augments a successful TOC result with pattern-detected items the TOC
#      omitted, behind a gate that asked whether Part III was complete. Part III
#      is complete on nearly every filing, so the augmentation almost never ran,
#      and the items a TOC actually omits — the optional one and the one added
#      in 2023 — were exactly the ones nobody got. Seven filings, one gate.
#   2. Near-total failures, where the new parser returns almost nothing on a
#      filing legacy handles. THE TWO 10-K ENTRIES IN THIS GROUP WERE ONE
#      DEFECT AND ARE CLOSED (2026-08-14): both filings write their headers as
#      "Item 1:  Business", and the 10-K patterns accepted only a period
#      between the number and the title, so every item-numbered pattern failed
#      together and the last detection strategy came back with one section.
#      Thirty-two items across three filings, from a separator. The 20-F outlier
#      0001144204-10-017467 is EDGARizer-generated filer-agent HTML: 12,880
#      <font> tags and zero <p>, the class edgartools-mpjh tracks. It left this
#      group on 2026-08-13 (22 gaps -> 8) when dt1f Defect 1 was fixed; the
#      eight that remain are an ordinary gap, not a collapse.
#   3. Singletons, most of them pre-2015 HTML.
#
# wfc/10k WAS IN GROUP 2 AND WAS NEVER BROKEN. Removed 2026-08-14 with its
# fixture unchanged and the parser untouched: all ten "missing" items were a
# measurement artefact. The benchmark's normalise_new() matched only the
# structural key spelling (part_ii_item_7) and returned None for the friendly
# one (mda), so a filing whose sections are named the friendly way scored as a
# near-total miss. TenK.items lists all 23 items on that filing and
# tenk['Item 1'] returns 46,618 characters of Wells Fargo's business section —
# it was correct the whole time.
#
# The lesson is about this file as much as that one: a gap recorded here is a
# claim about the parser, and it sat for a week as "a live bug on a modern
# large-bank filing" without anyone asking the library the same question the
# harness was asking. Before triaging any remaining entry, check what a user
# actually gets — report.items and report['Item N'] — not only what the
# benchmark reports.
#
# Entries keyed on an accession number come from the untracked era corpus and
# are unmeasurable in CI; the ticker-keyed ones are tracked and always run.
#
# Banked 2026-08-07: ("8-K", "0001437749-16-028287") Item 2 closed as a side
# effect of edgartools-2vzk. That filing puts its heading — "Item 2.02 Results of
# Operations and Financial Condition." — inside a <table> cell (verified), so it
# was read through the same _extract_text that was fabricating a space between
# adjacent inline elements. The new parser now resolves item_202.
#
# A markdown-rendering fix closing a section-extraction gap is not a coincidence:
# both harnesses read cell text through that one extractor. Worth remembering
# when triaging the remaining dt1f gaps — some may be extraction, not detection.
BASELINE_GAPS = {
    ("8-K", "0001104659-03-004925"): ["9"],
    # CLOSED 2026-08-20, together with ("20-F", "0000928385-01-500187") below:
    # both were pre-2002 filings that parse to ContainerNode > TextNode with zero
    # HeadingNodes and zero ParagraphNodes, and every header strategy in the
    # pattern extractor drew its candidates from headings, sections, bold
    # paragraphs or table cells. There was no candidate source at all on those
    # documents, so detection returned nothing however good the patterns were.
    # Strategy 5c reads bare TextNodes, taking the node's first line as the
    # header. Regression test:
    # tests/issues/regression/test_3dp_bare_textnode_headers.py.
    # Banked 2026-08-14: 14 -> 3, closing the item-separator defect below. What
    # remains is era semantics plus one regex detail, not separators: in 1999
    # Item 4 was "Submission of Matters to a Vote of Security Holders" and Item
    # 14 was "Exhibits ... and Reports on Form 8-K", and the 10-K vocabulary
    # holds only the modern meanings (Mine Safety, Principal Accountant Fees).
    # Banked 2026-08-21: 3 -> 2. Item 7A's header carried a newline inside it —
    # "Quantitative and Qualitative\nDisclosures about Market Risk" — and `.`
    # does not cross one. That observation turned out to describe a whole class
    # of misses rather than one filing: header text arrives carrying the source
    # HTML's line wrapping, so every pattern that joins words with `.*` failed on
    # a wrapped header while every pattern built from `\s+` matched, and which
    # items a filing lost was decided by that accident. Header text is now
    # whitespace-normalized before matching (edgartools-dt1f.1). What remains
    # here is era semantics: in 1999 Item 4 was "Submission of Matters to a Vote
    # of Security Holders" and Item 14 "Exhibits ... and Reports on Form 8-K",
    # and the 10-K vocabulary holds only the modern meanings.
    # Banked 2026-08-22: 2 -> 0, closing that era gap. Both titles are now
    # alternatives alongside the modern ones, so the pre-2011 Item 4 and the
    # pre-2003 Item 14 match instead of being found and discarded. This filing
    # therefore carries NO gap at all and stays listed only in the
    # must-stay-measurable set below. Regression test:
    # tests/issues/regression/test_dt1f1_era_item_titles.py.
    # ("10-K", "0001193125-10-073212") CLOSED 2026-08-22. Its header reads "ITEM
    # 9A(T). CONTROLS AND PROCEDURES" — 9A(T) was the SEC's transitional
    # designation for a smaller reporting company's internal-control report,
    # roughly 2007-2010 — and the "(" was not in the item separator's punctuation
    # class, so the match died there and no controls_procedures section was
    # created. _ITEM_SEP now carries an optional parenthesized designation, which
    # reaches all three item-based forms through the existing drift guard.
    # Measured across every available fixture, the change adds this one section
    # and alters nothing else on 55 10-K, 31 10-Q and 18 20-F filings. Regression
    # test: tests/issues/regression/test_dt1f1_item_9at.py.
    # Banked 2026-08-14: 4 -> 1, same fix.
    ("10-K", "0001193125-21-101193"): ["11"],
    # Banked 2026-08-14: 19 -> 1, same fix.
    # Banked 2026-08-22: 1 -> 0. The last one was Item 5, and the reason was a
    # word cap rather than a pattern: ContextualDetector — the only detector
    # that fires on this filer's markup — refuses to call anything over fifteen
    # words a header, and Item 5's canonical SEC title is seventeen. A filing's
    # own "Item N"/"PART N" label now waives that length test. Regression test:
    # tests/issues/regression/test_dt1f1_long_item_titles.py.
    # CLOSED 2026-08-14, together with axp/bac/cvx/jnj/jpm/tsla and
    # 0001193125-21-082408: the TOC-augmentation gate asked whether Part III was
    # complete before running the pattern pass, and Part III is complete on
    # nearly every filing, so the pass was skipped on filings whose TOC simply
    # omitted Item 16 or Item 1C. Both items were already being found and thrown
    # away. Regression test:
    # tests/issues/regression/test_dt1f_toc_augmentation_gate.py.
    # ("10-Q", "gs/10q") CLOSED 2026-08-22. Both items were found and then thrown
    # away: this filer renders "PART II. OTHER INFORMATION" as a ParagraphNode
    # whose own style carries no weight and whose child TextNode is bold, a shape
    # only Strategy 3b catches — and that strategy was gated to 10-K and 8-K. With
    # no Part II marker, _detect_10q_parts labelled every later header Part I, so
    # the part_ii_* patterns rejected their own headers on part context and the
    # filing resolved part_i_item_1..4 and nothing else. Strategy 3b now runs for
    # 10-Q, restricted to PART boundaries and the terminal SIGNATURES line.
    # Regression test: tests/issues/regression/test_dt1f1_10q_part_boundary.py.
    # ("20-F", "0000928385-01-500187") CLOSED 2026-08-20 — see the note on the
    # 10-K entry above; one fix closed both.
    # Banked 2026-08-21: 3 -> 1, with the header whitespace normalization noted
    # on the 10-K entry above. Items 6 and 11 were written wrapped across lines
    # ("Item 6. Directors, Senior Management and\nEmployees") and their patterns
    # join words with `.*`. Item 16 remains, and it is a separator defect rather
    # than a wrapping one: this filer writes the lettered subsections as "Item
    # 16. A. Audit Committee Financial Expert", so neither `item_16a` (which
    # expects the letter attached, "Item 16A") nor `item_16` (which expects
    # "[Reserved]") matches, while legacy reads the whole series as Item 16.
    ("20-F", "0001062993-16-008650"): ["16"],
    # ("20-F", "0001144204-10-017467") CLOSED 2026-08-21, in two steps. It was
    # banked 2026-08-13 at 22 -> 8 by edgartools-dt1f Defect 1: the fallback
    # strategies in the pattern extractor were gated on whether *any* header
    # mentioned an item, and on this filing three promoted headings (one of them
    # a prose cross-reference) suppressed the strategies that find the other
    # fifteen, leaving four sections against legacy's twenty-six. The gate now
    # asks for coverage of the form's item list instead of presence of one item.
    # Regression test: tests/issues/regression/test_dt1f_item_coverage_gate.py.
    #
    # The last eight — Items 5, 6, 11, 12, 15 and 16D-F — were never a detection
    # miss at all: every one of those headers was in the header list the whole
    # time, wrapped across lines by the filer's EDGARizer output ("ITEM\n5.
    # OPERATING\nAND FINANCIAL REVIEW AND PROSPECTS"), and failed only at the
    # pattern match. Header text is now whitespace-normalized first
    # (edgartools-dt1f.1). Regression test:
    # tests/issues/regression/test_dt1f1_wrapped_item_headers.py.
}

# The tracked fixtures every environment must be able to measure. If one of
# these goes missing the corpus is broken, not merely reduced.
#
# Two sources: the ticker-keyed 10-K/10-Q fixtures under tests/fixtures/html,
# and the four gap-carrying gate-form filings copied into tests/fixtures/
# parity_gate so 8-K and 20-F are guarded in CI rather than only on a developer
# machine. Listed explicitly rather than inferred from the label shape — the
# inference was right until parity_gate existed, and a guard that quietly stops
# covering things is the failure this file already had once.
TRACKED_GAP_FIXTURES = (
    {key for key in BASELINE_GAPS if "/" in key[1]}
    | {
        ("8-K", "0001104659-03-004925"),
        ("8-K", "0001437749-16-028287"),
        ("20-F", "0000928385-01-500187"),
        ("20-F", "0001062993-16-008650"),
        # Copied into parity_gate on 2026-08-14 with the item-separator fix.
        # It is the filing that fix was found on — colon-separated headers,
        # every item-numbered pattern failing at once, one section resolved
        # where legacy found fifteen — and leaving it in the gitignored era
        # corpus would have made the regression invisible to CI.
        ("10-K", "0000950153-99-001234"),
        # Copied into parity_gate on 2026-08-22 with the Item 9A(T) fix, for the
        # same reason. This one carries NO baseline gap — that is the point: it
        # is listed here so the fixture cannot quietly disappear and take the
        # only CI-visible evidence for a whole cohort of 2007-2010 filings with
        # it. Membership of this set means "must stay measurable", not "still
        # broken".
        ("10-K", "0001193125-10-073212"),
        # Copied into parity_gate on 2026-08-22 with the Defect C fix, and
        # likewise carrying no baseline gap any more. This one is the filing the
        # item-separator fix was measured on (TenK.items == ['Item 8'] before
        # it), so it guards two fixes at once and must stay measurable.
        ("10-K", "0001376474-16-000635"),
    }
)

# Filings where NEITHER parser finds an item — every one pre-2009, all from the
# era corpus. Not a parity signal (the delta is zero), but pinned so a *modern*
# filing joining them is caught: that would be a gap in both parsers at once.
BASELINE_BOTH_BLIND = 16


@pytest.fixture(scope="module")
def measured():
    """Measure whatever corpus this environment actually has.

    Returns the per-filing results alongside the set of labels present, because
    every assertion below needs to distinguish "no gap" from "never looked".
    """
    corpus = parity_benchmark.build_corpus(parity_benchmark.GATE_FORMS)
    assert corpus, "fixture corpus is missing entirely — nothing was measured"
    results = [parity_benchmark.measure(entry) for entry in corpus]
    present = {(entry["form"], entry["label"]) for entry in corpus}
    return results, present


def _live_gaps(results):
    return {
        (r["form"], r["label"]): set(r["legacy_only"])
        for r in results if r["legacy_only"]
    }


class TestTheLegacyParserFindsNothingNew:
    """The deletion gate: no section may be legacy-only that was not already."""

    def test_no_new_parity_gap_appears(self, measured):
        results, _present = measured
        baseline = {k: set(v) for k, v in BASELINE_GAPS.items()}
        live = _live_gaps(results)

        regressions = {
            key: sorted(items - baseline.get(key, set()))
            for key, items in live.items()
            if items - baseline.get(key, set())
        }
        assert not regressions, (
            "the new parser lost ground against the parser we plan to delete: "
            f"{regressions}. Each entry is an item legacy finds and new does "
            "not, on a filing where that was not previously true."
        )

    def test_closed_gaps_are_recorded(self, measured):
        """The ratchet's other half: tighten the baseline when a gap closes.

        Not a failure of the parser — a failure to bank the win. Left un-banked,
        the baseline keeps permitting a gap that no longer exists, and the guard
        silently loosens.

        Only fixtures this environment could actually measure are considered. A
        fixture that is absent has not been fixed, and saying so was the bug that
        made this test pass a false success on its first CI run.
        """
        results, present = measured
        baseline = {k: set(v) for k, v in BASELINE_GAPS.items()}
        live = _live_gaps(results)

        stale = {
            key: sorted(items - live.get(key, set()))
            for key, items in baseline.items()
            if key in present and items - live.get(key, set())
        }
        assert not stale, (
            f"these recorded gaps are closed — remove them from BASELINE_GAPS "
            f"in the same commit that closed them: {stale}"
        )


class TestTheCorpusItselfIsIntact:
    """Guards against the measurement quietly shrinking to nothing."""

    def test_the_tracked_corpus_is_present(self, measured):
        """The tracked fixtures must always be measurable.

        The era corpus is gitignored and legitimately absent in CI, but
        ``tests/fixtures/html`` is committed. If those go missing the run is
        broken, and every assertion above would otherwise pass by measuring
        nothing.
        """
        _results, present = measured
        missing = sorted(TRACKED_GAP_FIXTURES - present)
        assert not missing, (
            f"tracked fixtures absent from the corpus: {missing}. The parity "
            "assertions cannot mean anything without them."
        )

    def test_unmeasured_baseline_entries_are_only_the_untracked_ones(self, measured):
        """Whatever this environment could not measure must be explainable.

        An entry going unmeasured is fine when its fixture is gitignored and
        expected to be missing; it is not fine when a tracked fixture silently
        stops being collected. This pins the difference rather than leaving the
        reduced sample to pass unremarked.
        """
        _results, present = measured
        unmeasured = {key for key in BASELINE_GAPS if key not in present}
        unexplained = sorted(unmeasured & TRACKED_GAP_FIXTURES)
        assert not unexplained, (
            f"tracked baseline fixtures were not measured: {unexplained}"
        )


class TestBothParsersStillSeeTheSameCorpus:

    def test_both_blind_set_does_not_grow(self, measured):
        results, _present = measured
        blind = [r for r in results if r["both_blind"]]
        assert len(blind) <= BASELINE_BOTH_BLIND, (
            f"{len(blind)} filings now yield no items from EITHER parser, up "
            f"from {BASELINE_BOTH_BLIND}: "
            f"{[(r['form'], r['label']) for r in blind]}"
        )

    def test_neither_parser_crashes(self, measured):
        results, _present = measured
        errors = [(r["form"], r["label"], r["new_error"] or r["legacy_error"])
                  for r in results if r["new_error"] or r["legacy_error"]]
        assert not errors, f"parser raised on: {errors}"
