"""
Regression tests for edgartools-gnx5 (GH #914): line-item tags resolved to
`Total*` standard concepts, so a standardized statement returned several rows
all claiming to be the same total.

`us-gaap:BankOwnedLifeInsurance` resolved to "Total Assets" at confidence 0.319.
On Citizens Financial's balance sheet three rows claimed to be total assets, and
taking the first gave $7.9B against the filed $226.4B.

WHY NOT A CONFIDENCE THRESHOLD. The bead proposed one, and measuring the index
says it would be destructive. Confidence is not bimodal over the index as a
whole — 1,504 entries sit at exactly 0.5 and 564 at 0.4, so a 0.5 cut discards
about a third of all mappings. Worse, *within* the entries that claim a total,
0.5 does not separate right from wrong: `MembersEquity` and `PartnersCapital`
(the total equity of an LLC and of a partnership), `AssetsNet` (funds) and
`BenefitsLossesAndExpenses` (insurers) sit at 0.5 alongside the bogus AOCI
entries. A threshold would strip the totals of exactly the non-corporate filers.

So the guard is semantic rather than numeric: **a tag whose entry says it is not
a total must not resolve to a Total concept.** `is_total` states what the entry
means, and it separates the two groups exactly — every canonical total carries
`is_total=True` at confidence 1.0. A MISSING `is_total` is left alone, because
those are the IFRS entries, which are correct totals carrying no such metadata.

Measured: 74 tag spellings stopped resolving to a total they are not, and no
mapping resolved to anything different. Nothing was rewritten, only withdrawn.

THE SECOND HALF, cross-taxonomy leakage. `_normalize_tag` stripped `ifrs-full_`
and retried against the index, which is keyed on bare US-GAAP names — so an IFRS
tag with no entry of its own answered with a GAAP concept that merely shares the
name. `ifrs-full:IntangibleAssetsAndGoodwill` came back as "Total Non-Current
Assets" that way. IFRS entries are stored WITH their prefix (161 of them), so
the strip-and-retry could only ever cross taxonomies. The prefix spelling is
still canonicalised, so `ifrs-full:Assets` and `ifrs-full_Assets` both resolve.

WHAT THIS DOES NOT FIX. Entries marked `is_total=True` that are fuzzy matches
remain wrong — `DebtSecuritiesHeldToMaturityExcludingAccruedInterestAfterAllowanceForCreditLoss`
still resolves to "Total Assets" at confidence 0.309, so CFG still shows two
rows claiming total assets rather than three. That is a data defect in the
generated `gaap_mappings.json` and belongs upstream in edgar-storage; no
consumer-side rule separates it from `MembersEquity` without discarding
legitimate totals.
"""

import pytest

from edgar.xbrl.standardization import MappingStore
from edgar.xbrl.standardization.reverse_index import (
    _denotes_total,
    get_reverse_index,
)


@pytest.fixture(scope="module")
def store():
    return MappingStore()


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


def test_the_reported_tag_no_longer_claims_to_be_total_assets(store):
    """`us-gaap:BankOwnedLifeInsurance` -> 'Total Assets' at confidence 0.319."""
    assert store.get_standard_concept("us-gaap_BankOwnedLifeInsurance") is None


@pytest.mark.parametrize(
    "tag, expected",
    [
        ("us-gaap_Assets", "Total Assets"),
        ("us-gaap_Liabilities", "Total Liabilities"),
        ("us-gaap_AssetsCurrent", "Total Current Assets"),
        ("us-gaap_LiabilitiesCurrent", "Total Current Liabilities"),
        ("us-gaap_LiabilitiesAndStockholdersEquity", "Total Liabilities and Equity"),
        # The totals a confidence threshold would have destroyed: these are the
        # total equity of a partnership, an LLC and a fund respectively.
        ("us-gaap_PartnersCapital", "Total Stockholders' Equity"),
        ("us-gaap_MembersEquity", "Total Stockholders' Equity"),
        ("us-gaap_AssetsNet", "Total Assets"),
    ],
)
def test_real_totals_still_resolve(store, tag, expected):
    assert store.get_standard_concept(tag) == expected


def test_no_non_total_entry_resolves_to_a_total(index):
    """The invariant, over every entry in the index."""
    offenders = []
    for tag, entry in index._index.items():
        if not isinstance(entry, dict) or entry.get("is_total") is not False:
            continue
        resolved = index.get_display_name(tag)
        if _denotes_total(resolved):
            offenders.append((tag, resolved))

    assert offenders == []


class TestIfrsTagsDoNotFallBackToGaap:
    """An IFRS tag must answer from IFRS entries or not at all."""

    def test_the_reported_leak(self, store):
        # Resolved to "Total Non-Current Assets" via the GAAP entry of the same
        # bare name, a concept it has nothing to do with.
        assert store.get_standard_concept("ifrs-full_IntangibleAssetsAndGoodwill") is None

    @pytest.mark.parametrize(
        "tag, expected",
        [
            ("ifrs-full_Assets", "Total Assets"),
            ("ifrs-full_Liabilities", "Total Liabilities"),
            ("ifrs-full_CurrentAssets", "Total Current Assets"),
            ("ifrs-full_Revenue", "Revenue"),
        ],
    )
    def test_ifrs_entries_still_resolve(self, store, tag, expected):
        assert store.get_standard_concept(tag) == expected

    @pytest.mark.parametrize(
        "tag", ["ifrs-full:Assets", "ifrs-full:Liabilities", "ifrs-full:CurrentAssets"]
    )
    def test_the_colon_spelling_resolves_too(self, store, tag):
        """
        The index is keyed on `ifrs-full_`, and the colon form used to resolve
        only by accident, through the GAAP fallback this change removes. The
        separator is canonicalised so it keeps working on its own merits.
        """
        underscore = tag.replace("ifrs-full:", "ifrs-full_")
        assert store.get_standard_concept(tag) == store.get_standard_concept(underscore)
        assert store.get_standard_concept(tag) is not None


def test_a_gaap_tag_is_unaffected_by_the_ifrs_rule(store):
    """Both GAAP prefix spellings still strip and resolve as before."""
    assert store.get_standard_concept("us-gaap:Assets") == "Total Assets"
    assert store.get_standard_concept("Assets") == "Total Assets"
