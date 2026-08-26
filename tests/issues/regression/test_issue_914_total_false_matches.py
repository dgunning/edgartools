"""
Regression tests for GitHub issue #914.

Line-item tags whose only mapping is a low-confidence fuzzy match onto a
canonical total concept (Assets, Liabilities, CommonEquity, ...) must not
resolve as that total. On a bank balance sheet this made
``standard_concept == 'Assets'`` return three rows: the real TOTAL ASSETS
line plus DebtSecuritiesHeldToMaturity... and BankOwnedLifeInsurance,
whose values are line items in the tens of billions, not the total.

Root cause (per the #914 thread): ``gaap_mappings.json`` carries 59 entries
at confidence < 0.5 whose standard_tags are canonical totals. The generator
is upstream and hand-edits do not survive regeneration, so the authority
judgement belongs in the consumer: ``ReverseIndex.lookup`` suppresses
mappings whose confidence sits below the low-confidence floor when every
candidate concept is a Total concept. The distribution measured in #914 is
cleanly bimodal - colliding rows all sit at 0.307-0.319, nothing between
0.5 and 0.9 collided - so a 0.5 floor clears every reproducible case while
the middle band (harmless, context-disambiguated) is untouched.
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl.standardization.reverse_index import ReverseIndex

pytestmark = pytest.mark.fast


# The tags from the #914 report + follow-up sampling, all fuzzy-matched at
# confidence 0.307-0.319 onto canonical totals.
LOW_CONFIDENCE_TOTAL_COLLISIONS = [
    "us-gaap_DebtSecuritiesHeldToMaturityExcludingAccruedInterestAfterAllowanceForCreditLoss",
    "us-gaap_BankOwnedLifeInsurance",
    "us-gaap_AccruedInvestmentIncomeReceivable",
    "us-gaap_CashCashEquivalentsAndFederalFundsSold",
    "us-gaap_UnearnedPremiums",
    "us-gaap_SubordinatedDebt",
    "us-gaap_AdvancesFromFederalHomeLoanBanks",
    "us-gaap_SecuredDebt",
    "us-gaap_SecuritiesSoldUnderAgreementsToRepurchase",
    "us-gaap_OtherBorrowings",
]


@pytest.mark.parametrize("tag", LOW_CONFIDENCE_TOTAL_COLLISIONS)
def test_low_confidence_line_items_are_not_standardized(tag):
    idx = ReverseIndex()
    assert idx.get_standard_concept(tag) is None


@pytest.mark.parametrize(
    ("tag", "industry"),
    [
        ("us-gaap_SubordinatedDebt", "Banks"),
        ("us-gaap_SecuredDebt", "Banks"),
        ("us-gaap_SecuredDebt", "Fin"),
        ("us-gaap_SecuredDebt", "RlEst"),
        ("us-gaap_UnearnedPremiums", "Insur"),
        ("ifrs-full_IntangibleAssetsAndGoodwill", "Chips"),
    ],
)
def test_industry_override_cannot_resurrect_suppressed_total_mapping(tag, industry):
    """Using override confidence instead of base confidence returns a false total."""
    idx = ReverseIndex()
    assert idx.get_standard_concept(tag, industry=industry) is None


def test_ifrs_line_item_does_not_resolve_via_gaap_total():
    """ifrs-full_ tags resolve against the GAAP index by bare name (#914)."""
    idx = ReverseIndex()
    assert idx.get_standard_concept("ifrs-full_IntangibleAssetsAndGoodwill") is None


# Canonical mappings must be untouched by the guard.


def test_canonical_assets_tag_still_resolves():
    idx = ReverseIndex()
    assert idx.get_standard_concept("us-gaap_Assets") == "Assets"
    assert idx.get_standard_concept("us-gaap_AssetsCurrent") == "CurrentAssetsTotal"
    assert idx.get_standard_concept("us-gaap_Liabilities") == "Liabilities"


def test_low_confidence_canonical_self_match_survives():
    """Removing the self-match exemption suppresses this canonical total."""
    idx = ReverseIndex()
    assert idx.get_standard_concept("us-gaap_LiabilitiesAndEquity") == "LiabilitiesAndEquity"


def test_assetsnet_at_exact_floor_still_resolves():
    """AssetsNet maps to Assets at exactly confidence 0.5 - on the floor, kept."""
    idx = ReverseIndex()
    assert idx.get_standard_concept("us-gaap_AssetsNet") == "Assets"


def test_mid_band_tag_still_resolves():
    """CommonStocksIncludingAdditionalPaidInCapital sits at exactly 0.5 and
    resolves to CommonEquity; the guard must not touch it."""
    idx = ReverseIndex()
    assert idx.get_standard_concept("us-gaap_CommonStocksIncludingAdditionalPaidInCapital") == "CommonEquity"


def test_non_total_low_confidence_mapping_survives():
    """Low-confidence mappings whose candidates are NOT totals are out of
    scope for this guard and keep resolving."""
    idx = ReverseIndex()
    assert idx.get_standard_concept("us-gaap_AccountsReceivableGrossNoncurrent") == ("OtherOperatingNonCurrentAssets")


def test_all_shipped_low_confidence_total_mappings_follow_the_guard():
    """The generated mapping data must not introduce an unrecognised total id."""
    data_dir = Path(__file__).parents[3] / "edgar" / "xbrl" / "standardization"
    mappings = json.loads((data_dir / "gaap_mappings.json").read_text(encoding="utf-8"))
    display_names = json.loads((data_dir / "display_names.json").read_text(encoding="utf-8"))
    idx = ReverseIndex()

    guarded_tags = []
    for tag, entry in mappings.items():
        if tag == "_metadata" or entry.get("confidence", 1.0) >= 0.5:
            continue
        standard_tags = entry.get("standard_tags", [])
        if standard_tags and all(display_names.get(candidate, "").startswith("Total ") for candidate in standard_tags):
            guarded_tags.append(tag)

    assert guarded_tags
    for tag in guarded_tags:
        expected = tag if mappings[tag]["standard_tags"] == [tag] else None
        assert idx.get_standard_concept(tag) == expected
