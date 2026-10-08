"""Synonym groups and legacy labels grouped parts, totals and other measures under one name.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1442

``EntityFacts.get_concept("operating_lease_liability")`` asks for ONE number across a
group of tags. With no period given it returns the most recent fact among every tag in
the group, so a group that lists a part (the current portion of a lease liability) next
to the whole (the total) answers with whichever was filed last, with nothing to say
which one you got.

On Snowflake's tracked company-facts fixture the shipped group returned the 10-Q current
portion, $37,098,000 (period ended 2025-04-30), instead of the total lease liability of
$413,741,000 from the FY2025 10-K (0001640147-25-000052). Both are real; only one is what
the caller asked for.

This change removes 18 group members that are a part of the concept the group is named
for, a larger total that contains it, or a different measure, plus 3 tags from legacy
display labels in ``concept_mappings.json``. The tests below pin the removals, the
members that must survive, and the one place a user can see a legacy label
(``_label_to_concept``).

Ground truth is the tracked fixture ``tests/fixtures/entity/snow_facts.json``, so this
runs offline.
"""

import json
import warnings
from pathlib import Path

import pytest

import edgar.earnings as earnings
from edgar.entity.parser import EntityFactsParser
from edgar.standardization.synonym_groups import get_synonym_groups

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "snow_facts.json"
CONCEPT_MAPPINGS = Path(earnings.__file__).parent / "xbrl" / "standardization" / "concept_mappings.json"

# (group, removed member). 18 rows. Each is a part of the concept the group is named for
# (5), a larger total that contains it (4), or a different measure (9).
REMOVED_MEMBERS = [
    ("operating_expenses", "CostsAndExpenses"),
    ("sga_expense", "SellingAndMarketingExpense"),
    ("sga_expense", "SellingExpense"),
    ("interest_expense", "InterestIncomeExpenseNet"),
    ("income_tax_expense", "IncomeTaxesPaidNet"),
    ("cash_and_equivalents", "CashCashEquivalentsAndShortTermInvestments"),
    ("cash_and_equivalents", "CashEquivalentsAtCarryingValue"),
    ("prepaid_expenses", "PrepaidExpenseAndOtherAssetsCurrent"),
    ("property_plant_equipment", "PropertyPlantAndEquipmentGross"),
    ("intangible_assets", "IntangibleAssetsNetIncludingGoodwill"),
    ("common_shares_outstanding", "WeightedAverageNumberOfSharesOutstandingBasic"),
    ("dividends_paid", "DividendsPaid"),
    ("share_repurchases", "StockRepurchasedDuringPeriodValue"),
    ("operating_lease_payments", "LesseeOperatingLeaseLiabilityPaymentsDue"),
    ("operating_lease_payments", "OperatingLeasesFutureMinimumPaymentsDue"),
    ("operating_lease_liability", "OperatingLeaseLiabilityCurrent"),
    ("operating_lease_liability", "OperatingLeaseLiabilityNoncurrent"),
    ("operating_lease_right_of_use_asset", "RightOfUseAssetObtainedInExchangeForOperatingLeaseLiability"),
]

# Every touched group, in priority order, as shipped. Lists only what is left.
GROUP_MEMBERS = {
    "cash_and_equivalents": ["CashAndCashEquivalentsAtCarryingValue", "Cash"],
    "common_shares_outstanding": ["CommonStockSharesOutstanding", "NumberOfSharesOutstanding"],
    "dividends_paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "income_tax_expense": ["IncomeTaxExpenseBenefit", "IncomeTaxExpenseContinuingOperations"],
    "intangible_assets": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
    "interest_expense": ["InterestExpense", "InterestAndDebtExpense", "InterestExpenseOperating", "InterestExpenseNonoperating"],
    "operating_expenses": ["OperatingExpenses", "OperatingCostsAndExpenses", "NoninterestExpense"],
    "operating_lease_liability": ["OperatingLeaseLiability"],
    "operating_lease_payments": ["OperatingLeasePayments", "PaymentsForOperatingLeases"],
    "operating_lease_right_of_use_asset": ["OperatingLeaseRightOfUseAsset"],
    "prepaid_expenses": ["PrepaidExpenseCurrent", "PrepaidExpense"],
    "property_plant_equipment": ["PropertyPlantAndEquipmentNet", "FixedAssets"],
    "sga_expense": ["SellingGeneralAndAdministrativeExpense", "GeneralAndAdministrativeExpense", "AdministrativeExpense"],
    "share_repurchases": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"],
}

# (legacy display label, removed tag, tags that must remain, in order). 3 rows.
REMOVED_LABEL_TAGS = [
    ("Interest Expense", "us-gaap_InterestIncomeExpenseNet", ["us-gaap_InterestAndDebtExpense", "us-gaap_InterestExpense"]),
    (
        "Intangible Assets",
        "us-gaap_IntangibleAssetsNetIncludingGoodwill",
        ["us-gaap_IntangibleAssetsNetExcludingGoodwill", "us-gaap_FiniteLivedIntangibleAssetsNet"],
    ),
    (
        "Total Stockholders' Equity",
        "us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ["us-gaap_EquityAttributableToParent", "us-gaap_StockholdersEquity", "us-gaap_StockholdersEquityAttributableToParent"],
    ),
]


@pytest.fixture(scope="module")
def facts():
    assert FIXTURE.exists(), f"missing fixture: {FIXTURE}"
    return EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))


@pytest.fixture(scope="module")
def groups():
    return get_synonym_groups()


@pytest.fixture(scope="module")
def label_map():
    return json.loads(CONCEPT_MAPPINGS.read_text("utf-8"))


def _concept(facts, name, period=None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return facts.get_concept(name, period=period, return_metadata=True)


# --------------------------------------------------------------------------- #
# Ground truth: the reported behaviour, on real Snowflake values
# --------------------------------------------------------------------------- #


def test_total_operating_lease_liability_is_the_10k_total_not_a_10q_part(facts):
    """FY2025 10-K (0001640147-25-000052): total operating lease liability $413,741,000.
    Before, the answer was the 10-Q's current portion, $37,098,000 at 2025-04-30."""
    result = _concept(facts, "operating_lease_liability")
    assert result is not None
    assert result["value"] == 413_741_000
    assert result["tag_used"] == "us-gaap:OperatingLeaseLiability"
    assert str(result["period_end"]) == "2025-01-31"


def test_the_current_portion_is_no_longer_reachable_through_the_total_group(facts):
    """A 10-Q period has the current portion filed but no total. The group is for the
    total, so the answer is None rather than the $37,098,000 part."""
    assert _concept(facts, "operating_lease_liability", period="2026-Q1") is None
    assert facts.discover_concept_tags("operating_lease_liability") == ["OperatingLeaseLiability"]


def test_operating_lease_payments_group_only_reports_payments_made(facts):
    """LesseeOperatingLeaseLiabilityPaymentsDue is the schedule of future payments, a
    different measure from cash paid in the period."""
    assert facts.discover_concept_tags("operating_lease_payments") == ["OperatingLeasePayments"]


def test_tag_discovery_no_longer_lists_removed_members(facts):
    """What Snowflake files under each touched group, after the change."""
    assert facts.discover_concept_tags("cash_and_equivalents") == ["CashAndCashEquivalentsAtCarryingValue"]
    assert facts.discover_concept_tags("income_tax_expense") == ["IncomeTaxExpenseBenefit"]
    assert facts.discover_concept_tags("property_plant_equipment") == ["PropertyPlantAndEquipmentNet"]
    assert facts.discover_concept_tags("sga_expense") == ["GeneralAndAdministrativeExpense"]
    assert facts.discover_concept_tags("operating_lease_right_of_use_asset") == ["OperatingLeaseRightOfUseAsset"]


# --------------------------------------------------------------------------- #
# Silence check: no concept fits, so the answer is None, not a near miss
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("group", ["prepaid_expenses", "common_shares_outstanding"])
def test_group_with_no_matching_tag_answers_none_not_a_different_measure(facts, group):
    """Snowflake files only the combined PrepaidExpenseAndOtherAssetsCurrent and weighted
    average shares (no CommonStockSharesOutstanding). Those used to be returned for these
    groups as if they were the answer: $211,234,000 of prepaids and other assets for
    FY2025, and 332,707,000 weighted average shares for a share count. Now: None."""
    assert facts.discover_concept_tags(group) == []
    assert _concept(facts, group) is None
    assert _concept(facts, group, period="2025-FY") is None


# --------------------------------------------------------------------------- #
# The removals, one row each
# --------------------------------------------------------------------------- #


def test_the_removal_table_covers_18_members_of_14_groups():
    assert len(REMOVED_MEMBERS) == 18
    assert len({group for group, _ in REMOVED_MEMBERS}) == 14
    assert set(GROUP_MEMBERS) == {group for group, _ in REMOVED_MEMBERS}


@pytest.mark.parametrize("group,member", REMOVED_MEMBERS)
def test_removed_member_is_gone_from_its_group(groups, group, member):
    assert member not in groups.get_synonyms(group)


@pytest.mark.parametrize("group,member", REMOVED_MEMBERS)
def test_removed_member_no_longer_identifies_as_that_group(groups, group, member):
    info = groups.identify_concept(member)
    assert info is None or info.name != group


@pytest.mark.parametrize("group,expected", sorted(GROUP_MEMBERS.items()))
def test_touched_group_keeps_exactly_its_remaining_members_in_order(groups, group, expected):
    assert groups.get_synonyms(group) == expected


# --------------------------------------------------------------------------- #
# Legacy labels in concept_mappings.json
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("label,removed,remaining", REMOVED_LABEL_TAGS)
def test_legacy_label_lost_exactly_one_tag_and_kept_its_siblings(label_map, label, removed, remaining):
    assert removed not in label_map[label]
    assert label_map[label] == remaining


def test_intangible_assets_label_no_longer_resolves_to_goodwill_plus_intangibles():
    """The one user-visible effect: earnings uses the FIRST tag listed under a label.
    "Intangible Assets" used to resolve to IntangibleAssetsNetIncludingGoodwill, which
    includes goodwill. Goodwill has its own label."""
    assert earnings._label_to_concept("Intangible Assets") == "us-gaap:IntangibleAssetsNetExcludingGoodwill"
    assert earnings._label_to_concept("Goodwill") == "us-gaap:Goodwill"


def test_first_tag_for_the_other_two_touched_labels_is_unchanged():
    """The two removals that sat behind the first tag change nothing a caller can see."""
    assert earnings._label_to_concept("Interest Expense") == "us-gaap:InterestAndDebtExpense"
    assert earnings._label_to_concept("Total Stockholders' Equity") == "us-gaap:EquityAttributableToParent"
