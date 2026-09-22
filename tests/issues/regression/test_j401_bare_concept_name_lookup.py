"""EntityFacts never indexed a concept's bare name, so most lookups reported that
present data did not exist.

bead edgartools-j401, GH #1202 (reported by UniversalDreams).

``_fact_index['by_concept']`` was keyed by the QUALIFIED name a fact is tagged with
(``us-gaap:StockholdersEquity``) and by the lowercased LABEL. The bare local name was
never a key, and ``get_annual_fact`` / ``get_fact`` / ``available_periods`` all look up
``concept`` then ``concept.lower()`` -- so a bare name could only ever match by
coincidence, when a concept happened to be labelled the same as it is named.

That coincidence is what made the bug look intermittent instead of systematic. In this
fixture it holds for **4 of 339 concepts**. The other 335 answered ``None`` and warned
"No fact found", which is the part that matters: the caller was told the data was
absent when it was present, correct, and internally consistent.

Ground truth is Snowflake's FY2025 company facts, the tracked fixture
``tests/fixtures/entity/snow_facts.json``, so this runs offline.
"""

import json
import warnings
from pathlib import Path

import pytest

from edgar.entity.parser import EntityFactsParser

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"

# Snowflake FY2025, as filed. Every one of these was unreachable by bare name.
ASSETS = 9_033_938_000
LIABILITIES = 6_027_295_000
EQUITY_PARENT = 2_999_929_000          # us-gaap:StockholdersEquity
MINORITY_INTEREST = 6_714_000          # us-gaap:MinorityInterest
EQUITY_INCLUDING_NCI = 3_006_643_000


@pytest.fixture(scope="module")
def facts():
    assert FIXTURE.exists(), f"missing fixture: {FIXTURE}"
    return EntityFactsParser.parse_company_facts(
        json.loads(FIXTURE.read_text("utf-8")))


def _annual(facts, concept):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fact = facts.get_annual_fact(concept)
    return fact, [str(w.message) for w in caught]


# --------------------------------------------------------------------------- #
# The reported defect
# --------------------------------------------------------------------------- #

def test_a_concept_whose_label_differs_from_its_name_is_found(facts):
    """The case in the report. us-gaap:StockholdersEquity is labelled
    "Stockholders' Equity Attributable to Parent", so neither the qualified-name key nor
    the lowercased-label key could match the bare name, and the lookup returned None
    while warning that no such concept existed."""
    fact, warned = _annual(facts, "StockholdersEquity")

    assert fact is not None, f"reported absent; warnings were {warned}"
    assert fact.numeric_value == EQUITY_PARENT
    assert fact.concept == "us-gaap:StockholdersEquity"
    assert not warned, "a concept that was found must not warn"


def test_the_balance_sheet_closes_across_newly_reachable_concepts(facts):
    """The reporter's argument, and the reason this is data loss rather than a missing-
    data edge case: the values are present, correct and internally consistent.

    Snowflake carries a non-controlling interest, so the identity is
    Assets - Liabilities = equity INCLUDING NCI -- not the parent-only figure. Three of
    the four concepts needed to show that were unreachable before this fix, so the
    check could not have been written against the old behaviour at all."""
    assets = facts.get_annual_fact("Assets").numeric_value
    liabilities = facts.get_annual_fact("Liabilities").numeric_value
    total_equity = facts.get_annual_fact(
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest").numeric_value
    parent_equity = facts.get_annual_fact("StockholdersEquity").numeric_value
    nci = facts.get_annual_fact("MinorityInterest").numeric_value

    assert assets == ASSETS
    assert liabilities == LIABILITIES
    assert assets - liabilities == total_equity == EQUITY_INCLUDING_NCI
    assert parent_equity + nci == total_equity


@pytest.mark.parametrize("concept, expected, label", [
    ("AccountsPayableCurrent", 169_767_000, "Accounts Payable, Current"),
    ("EntityPublicFloat", 42_300_000_000, "Entity Public Float"),
    ("MinorityInterest", MINORITY_INTEREST, None),
])
def test_named_concepts_resolve_to_their_filed_values(facts, concept, expected, label):
    """A spread of taxonomies -- us-gaap and dei -- all of which label their concepts
    differently from how they name them."""
    fact, _ = _annual(facts, concept)

    assert fact is not None
    assert fact.numeric_value == expected
    if label is not None:
        assert fact.label == label, "the label differs from the name; that is the point"


# --------------------------------------------------------------------------- #
# Controls: nothing that worked before may change
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("concept, expected", [
    ("Assets", ASSETS),
    ("Goodwill", 1_056_559_000),
    ("Depreciation", 85_600_000),
])
def test_the_coincidences_still_work_and_still_agree(facts, concept, expected):
    """These are the concepts that DID resolve before -- the ones labelled exactly as
    they are named. Four of the fixture's 339 concepts are in that class. Their answers
    must not move now that the bare name resolves by concept rather than by label."""
    fact, _ = _annual(facts, concept)

    assert fact is not None
    assert fact.numeric_value == expected


def test_the_qualified_name_still_works_and_agrees_with_the_bare_one(facts):
    qualified, _ = _annual(facts, "us-gaap:StockholdersEquity")
    bare, _ = _annual(facts, "StockholdersEquity")

    assert qualified is not None
    assert qualified.numeric_value == bare.numeric_value == EQUITY_PARENT


def test_label_lookup_still_works(facts):
    """The lowercased-label key is still there and still matched, after the bare name."""
    fact, _ = _annual(facts, "stockholders' equity attributable to parent")

    assert fact is not None
    assert fact.numeric_value == EQUITY_PARENT


def test_a_genuinely_absent_concept_still_says_so(facts):
    """The silence check, inverted. The old failure was a confident wrong answer -- a
    None plus a warning claiming the concept did not exist, for a concept that did. A
    concept that really is absent must still produce that warning, or fixing the false
    negative would have removed the true one."""
    fact, warned = _annual(facts, "NotARealConceptXYZ")

    assert fact is None
    assert warned, "an absent concept must still warn"
    assert "NotARealConceptXYZ" in warned[0]


# --------------------------------------------------------------------------- #
# The index itself
# --------------------------------------------------------------------------- #

def test_the_bare_name_key_holds_no_duplicates(facts):
    """The local name is only indexed when it differs from the qualified name. Without
    that guard, an unprefixed concept would be appended to the same list twice and every
    count over it would double."""
    index = facts._fact_index["by_concept"]
    rows = index["StockholdersEquity"]

    assert rows, "the bare name is not indexed at all"
    assert len(rows) == len({id(row) for row in rows})
    assert rows == index["us-gaap:StockholdersEquity"]


def test_most_concepts_could_not_be_reached_by_name_before_this(facts):
    """Documents the scale, and acts as a canary on the fixture. If this ratio moves, the
    fixture changed and the numbers pinned above want re-checking."""
    index = facts._fact_index["by_concept"]
    qualified = sorted(k for k in index if ":" in k)
    coincidences = [
        q for q in qualified
        if any((f.label or "").lower() == q.rsplit(":", 1)[-1].lower() for f in index[q])
    ]

    assert len(qualified) == 339
    assert len(coincidences) == 4, (
        "only these resolved by bare name before the fix, and only because their label "
        f"matches their name: {coincidences}")


def test_get_fact_and_available_periods_take_the_bare_name_too(facts):
    """The same two-line lookup appears at three call sites. Fixing the index fixes all
    three; these are the other two."""
    assert facts.get_fact("StockholdersEquity") is not None
    assert facts.available_periods("StockholdersEquity")


# --------------------------------------------------------------------------- #
# Indexing the bare name must not cost the caller the taxonomy.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("concept", [
    "revenue", "net_income", "total_assets", "stockholders_equity",
])
def test_tag_used_stays_qualified_now_that_bare_names_resolve(facts, concept):
    """get_concept() reports the fact's own tag, not the key that found it.

    This is the half of the bare-name fix that is easy to lose. get_concept() walks
    ``[concept, 'us-gaap:concept', 'ifrs-full:concept']`` and the BARE variant is tried
    first, so once the bare name became a key it started matching before either
    prefixed variant -- the same fact, but reported under a key that no longer says
    which taxonomy it came from.

    That is not cosmetic. For an IFRS filer it is the difference between
    'ifrs-full:Revenue' and a bare 'Revenue' that a caller cannot distinguish from a
    us-gaap tag, which is exactly the provenance GH #637 exists to guarantee (see
    test_issue_637_ifrs_concept_discovery.py, which caught this in CI and needs the
    network; this one is offline and fails for the same reason).
    """
    result = facts.get_concept(concept, return_metadata=True)

    assert result is not None, f"{concept} did not resolve at all"
    assert ":" in result["tag_used"], (
        f"{concept} reported tag_used={result['tag_used']!r} — the bare lookup key "
        "rather than the fact's qualified concept, so the taxonomy is gone"
    )
    assert result["tag_used"].endswith(result["tag_used"].rsplit(":", 1)[-1])


def test_tag_used_is_the_facts_own_concept_not_the_matched_key(facts):
    """The stronger statement: tag_used equals the concept the fact carries.

    Asserted against the fact reached independently by qualified name, so this pins
    the two to each other rather than to a hardcoded string.
    """
    result = facts.get_concept("stockholders_equity", return_metadata=True)
    fact = facts.get_fact("us-gaap:StockholdersEquity")

    assert result["tag_used"] == fact.concept == "us-gaap:StockholdersEquity"
    assert result["value"] == fact.numeric_value, (
        "the bare-name key and the qualified name must reach the same fact"
    )
