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

import pytest

from edgar.xbrl.standardization.reverse_index import ReverseIndex

pytestmark = pytest.mark.fast


# The tags from the #914 report + follow-up sampling, all fuzzy-matched at
# confidence 0.307-0.319 onto canonical totals.
LOW_CONFIDENCE_TOTAL_COLLISIONS = [
    # tag, must NOT resolve to
    ("us-gaap_DebtSecuritiesHeldToMaturityExcludingAccruedInterestAfterAllowanceForCreditLoss", "Assets"),
    ("us-gaap_BankOwnedLifeInsurance", "Assets"),
    ("us-gaap_AccruedInvestmentIncomeReceivable", "Assets"),
    ("us-gaap_CashCashEquivalentsAndFederalFundsSold", "Assets"),
    ("us-gaap_UnearnedPremiums", "Liabilities"),
    ("us-gaap_SubordinatedDebt", "Liabilities"),
    ("us-gaap_AdvancesFromFederalHomeLoanBanks", "Liabilities"),
    ("us-gaap_SecuredDebt", "Liabilities"),
    ("us-gaap_SecuritiesSoldUnderAgreementsToRepurchase", "Liabilities"),
    ("us-gaap_OtherBorrowings", "Liabilities"),
]


@pytest.mark.parametrize("tag,total_concept", LOW_CONFIDENCE_TOTAL_COLLISIONS)
def test_low_confidence_line_items_do_not_resolve_as_totals(tag, total_concept):
    idx = ReverseIndex()
    assert idx.get_standard_concept(tag) != total_concept


def test_ifrs_line_item_does_not_resolve_via_gaap_total():
    """ifrs-full_ tags resolve against the GAAP index by bare name (#914)."""
    idx = ReverseIndex()
    assert idx.get_standard_concept("ifrs-full_IntangibleAssetsAndGoodwill") != (
        "NonCurrentAssetsTotal"
    )


# Canonical mappings must be untouched by the guard.


def test_canonical_assets_tag_still_resolves():
    idx = ReverseIndex()
    assert idx.get_standard_concept("us-gaap_Assets") == "Assets"
    assert idx.get_standard_concept("us-gaap_AssetsCurrent") == "CurrentAssetsTotal"
    assert idx.get_standard_concept("us-gaap_Liabilities") == "Liabilities"


def test_assetsnet_at_exact_floor_still_resolves():
    """AssetsNet maps to Assets at exactly confidence 0.5 - on the floor, kept."""
    idx = ReverseIndex()
    assert idx.get_standard_concept("us-gaap_AssetsNet") == "Assets"


def test_mid_band_tag_still_resolves():
    """CommonStocksIncludingAdditionalPaidInCapital sits at exactly 0.5 and
    resolves to CommonEquity; the guard must not touch it."""
    idx = ReverseIndex()
    assert idx.get_standard_concept(
        "us-gaap_CommonStocksIncludingAdditionalPaidInCapital"
    ) == "CommonEquity"


def test_non_total_low_confidence_mapping_survives():
    """Low-confidence mappings whose candidates are NOT totals are out of
    scope for this guard and keep resolving."""
    idx = ReverseIndex()
    # AdministrativeFeesExpense -> TotalOperatingExpenses IS in scope...
    assert idx.get_standard_concept("us-gaap_AdministrativeFeesExpense") != (
        "TotalOperatingExpenses"
    )
