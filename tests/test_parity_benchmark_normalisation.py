"""The parity benchmark must not score a naming convention as a parser miss.

``parity_benchmark.normalise_new`` maps a new-parser section key to a canonical
item number so the two parsers can be compared. It originally matched only the
structural key spelling (``part_ii_item_7``) and returned None for everything
else — including the friendly names (``mda``, ``risk_factors``) the same parser
emits when a different detection strategy fires.

Both spellings are live on the corpus, so the benchmark under-counted the new
parser on every filing named the friendly way. On ``wfc/10k`` that reported ten
missing items — Items 1, 1A, 7, 8 among them — for a filing where
``TenK.items`` lists all 23 and ``tenk['Item 1']`` returns 46,618 characters.
The false reading reached ``BASELINE_GAPS`` and sat there for a week described
as "a live bug on a modern large-bank filing".

These tests are cheap and the harness is not otherwise unit-tested; the ratchet
exercises it end-to-end but takes ~150s and lives in the slow lane, so a
normalisation bug could not fail fast. A measurement harness that is wrong is
worse than no harness, because its output is trusted and acted on.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures" / "parser_corpus"))
import parity_benchmark  # noqa: E402

normalise_new = parity_benchmark.normalise_new
normalise_legacy = parity_benchmark.normalise_legacy


@pytest.mark.fast
class TestBothKeyVocabulariesResolve:
    """The parser names 10-K sections two ways; the benchmark must know both."""

    @pytest.mark.parametrize("key,expected", [
        # Friendly names — the ones that used to normalise to None.
        ("business", "1"),
        ("risk_factors", "1A"),
        ("unresolved_staff_comments", "1B"),
        ("cybersecurity", "1C"),
        ("properties", "2"),
        ("legal_proceedings", "3"),
        ("mda", "7"),
        ("market_risk", "7A"),
        ("financial_statements", "8"),
        ("controls_procedures", "9A"),
        # Structural names — what the regex always handled.
        ("part_i_item_1", "1"),
        ("part_ii_item_7a", "7A"),
        ("part_iv_item_15", "15"),
        ("item_1", "1"),
    ])
    def test_10k_keys(self, key, expected):
        assert normalise_new(key, "10-K") == expected

    def test_the_two_spellings_of_one_item_agree(self):
        """The whole point: same item, two keys, one answer."""
        assert normalise_new("mda", "10-K") == normalise_new("part_ii_item_7", "10-K") == "7"


@pytest.mark.fast
class TestNonItemsStayOut:
    """Legacy has no equivalent concept, so these must not enter the comparison."""

    @pytest.mark.parametrize("key", [
        "signatures", "Signatures", "part_iv_signatures", "part_ii_signatures",
        "cover", "toc", "exhibits", "part_i", "part_ii",
    ])
    def test_not_an_item(self, key):
        assert normalise_new(key, "10-K") is None
        assert normalise_new(key, "20-F") is None


@pytest.mark.fast
class TestEightKGranularity:
    """8-K is compared at the granularity legacy can also express.

    Legacy cannot say "Item 8.01" — it reports 'Item 8'. Comparing the new
    parser's precision against that would score a legacy *limitation* as a new
    parser miss, which is the same class of error as the friendly-name bug.
    """

    def test_subitems_compare_at_the_major_number(self):
        assert normalise_new("item_801", "8-K") == "8"
        assert normalise_new("item_502", "8-K") == "5"
        assert normalise_legacy("Item 8", "8-K") == "8"
        assert normalise_legacy("Item 8.01", "8-K") == "8"

    def test_the_precision_is_still_recoverable(self):
        assert parity_benchmark.subitem_of("item_801", "8-K") == "8.01"
        assert parity_benchmark.subitem_of("part_ii_item_7", "10-K") is None


@pytest.mark.fast
class TestTheCorpusHasNoUnresolvedKeys:
    """Every key the corpus produces is either an item or knowably not one.

    This is the check that would have caught the original bug. It reads the
    committed golden key list rather than re-parsing 115 fixtures, so it belongs
    in the fast lane; the ratchet covers the live parse.
    """

    # Section keys observed across the whole parity corpus (2026-08-14), with
    # the ones that are legitimately not items listed separately. Regenerate by
    # collecting doc.sections keys over parity_benchmark.build_corpus().
    OBSERVED_NON_ITEMS = {
        "10-K": {"Signatures", "part_iv_signatures"},
        "10-Q": {"part_ii_signatures"},
        "20-F": {"part_i", "part_ii", "part_iii", "signatures"},
        "8-K": {"signatures"},
    }

    OBSERVED_ITEM_KEYS = {
        "10-K": {"business", "risk_factors", "unresolved_staff_comments",
                 "cybersecurity", "properties", "legal_proceedings", "mda",
                 "market_risk", "financial_statements", "controls_procedures",
                 "part_i_item_4", "part_ii_item_5", "part_ii_item_9b",
                 "part_iii_item_10", "part_iv_item_15", "item_1", "item_7"},
        "10-Q": {"part_i_item_1", "part_ii_item_1a", "part_ii_item_6"},
        "20-F": {"item_1", "item_4a", "item_16g", "part_i_item_1",
                 "part_ii_item_16a", "part_iii_item_19", "Item 1"},
        "8-K": {"item_801", "item_502", "item_901"},
    }

    @pytest.mark.parametrize("form", ["10-K", "10-Q", "20-F", "8-K"])
    def test_every_item_key_resolves(self, form):
        unresolved = sorted(
            key for key in self.OBSERVED_ITEM_KEYS[form]
            if normalise_new(key, form) is None
        )
        assert not unresolved, (
            f"{form}: these section keys are items the parser emits, and the "
            f"benchmark scores them as misses: {unresolved}"
        )

    @pytest.mark.parametrize("form", ["10-K", "10-Q", "20-F", "8-K"])
    def test_every_non_item_key_is_excluded(self, form):
        leaked = sorted(
            key for key in self.OBSERVED_NON_ITEMS[form]
            if normalise_new(key, form) is not None
        )
        assert not leaked, f"{form}: non-item sections entering the comparison: {leaked}"
