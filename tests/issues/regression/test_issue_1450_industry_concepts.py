"""Regression test for GitHub Issue #1450: core broker, insurer, BDC and utility line items had no standard concept.

Ten industry measures were unmapped: a broker-dealer's net revenue, investment banking
revenue, trading gains and securities borrowed; an insurer's future policy benefits and
policyholder funds; reverse repurchase (resale) assets; BDC paid-in-kind interest income;
and a utility's regulated and unregulated revenue components. Each now has its own standard
concept. None is merged into a total or a neighbouring measure: a component never resolves
to Revenue, resale assets are not repurchase obligations, and future policy benefits are
not policyholder funds.

The statement-format classifier the issue also proposes is out of scope here.

Filed values, from fixtures in tests/fixtures/xbrl:
- JPMorgan Chase FY2023 10-K, 0000019617-24-000225: total net revenue 158,104M, investment
  banking fees 6,519M, securities borrowed 200,436M at 2023-12-31.
- Golub Capital BDC 10-Q, quarter ended 2025-03-31, 0001476765-25-000040: payment-in-kind
  interest income 14,045,000.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1450
"""

import json
from pathlib import Path

import pytest

from edgar.financials import Financials
from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.core import ConceptMapper, MappingStore, standardize_statement
from edgar.xbrl.standardization.reverse_index import ReverseIndex
from edgar.xbrl.standardization.sections import get_section_for_concept, get_statement_for_concept

pytestmark = pytest.mark.regression

_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
FIXTURES = Path(__file__).parents[2] / "fixtures" / "xbrl"

# tag -> (standard concept, statement, is_total)
EXPECTED = {
    "RevenuesNetOfInterestExpense": ("NetRevenueAfterInterestExpense", "IncomeStatement", True),
    "InvestmentBankingRevenue": ("InvestmentBankingRevenue", "IncomeStatement", False),
    "TradingGainsLosses": ("TradingGainsLosses", "IncomeStatement", False),
    "InterestIncomeOperatingPaidInKind": ("InterestIncomePaidInKind", "IncomeStatement", False),
    "RegulatedOperatingRevenue": ("RegulatedOperatingRevenue", "IncomeStatement", False),
    "UnregulatedOperatingRevenue": ("UnregulatedOperatingRevenue", "IncomeStatement", False),
    "SecuritiesBorrowed": ("SecuritiesBorrowed", "BalanceSheet", False),
    "SecuritiesPurchasedUnderAgreementsToResell": ("ResaleAgreementAssets", "BalanceSheet", False),
    "FinancialAssetPurchasedUnderAgreementToResell": ("ResaleAgreementAssets", "BalanceSheet", False),
    "LiabilityForFuturePolicyBenefits": ("FuturePolicyBenefits", "BalanceSheet", False),
    "PolicyholderFunds": ("PolicyholderFunds", "BalanceSheet", False),
}
NEW_CONCEPTS = {concept for concept, _, _ in EXPECTED.values()}
STATEMENT_TYPES = ["BalanceSheet", "IncomeStatement", "CashFlowStatement", ""]


@pytest.fixture(scope="module")
def index():
    return ReverseIndex()


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_ten_new_concepts_none_reused():
    assert len(NEW_CONCEPTS) == 10
    other_entries = [v for k, v in GAAP_MAPPINGS.items() if k not in EXPECTED and isinstance(v, dict)]
    reused = {t for v in other_entries for t in v.get("standard_tags", [])} & NEW_CONCEPTS
    assert reused == set()


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_lookup(index, tag):
    concept, _, _ = EXPECTED[tag]
    result = index.lookup(f"us-gaap:{tag}")
    # Before the fix: None.
    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [DISPLAY_NAMES[concept]]
    assert result.is_ambiguous is False


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_entry_metadata_matches_its_concept(tag):
    concept, statement, is_total = EXPECTED[tag]
    entry = GAAP_MAPPINGS[tag]
    assert entry["standard_tags"] == [concept]
    assert entry["display_name"] == DISPLAY_NAMES[concept]
    assert entry["statement"] == statement == get_statement_for_concept(concept)
    assert entry["section"] == get_section_for_concept(concept, statement)
    assert entry["is_total"] is is_total
    assert entry["confidence"] == 0.9
    assert "industry_overrides" not in entry


def test_components_never_resolve_to_a_total(index):
    """A component or neighbouring measure keeps its own concept under every context."""
    contexts = [None, {"is_total": True}] + [
        {"statement_type": st, "section": sec}
        for st, sec in [("IncomeStatement", "Revenue"), ("IncomeStatement", "Banking Revenue"),
                        ("BalanceSheet", "Current Assets"), ("BalanceSheet", "Current Liabilities"),
                        ("BalanceSheet", "Non-Current Liabilities")]
    ]
    for tag, (concept, _, _) in EXPECTED.items():
        for context in contexts:
            assert index.get_standard_concept(f"us-gaap:{tag}", context) == concept, (tag, context)
    # The neighbours stay where they were.
    assert index.lookup("us-gaap:RegulatedAndUnregulatedOperatingRevenue").standard_concepts == ["Revenue"]
    assert index.lookup("us-gaap:SecuritiesSoldUnderAgreementsToRepurchase").standard_concepts == ["ShortTermDebt"]
    assert index.lookup("us-gaap:FederalFundsSoldAndSecuritiesPurchasedUnderAgreementsToResell") is None
    assert index.lookup("us-gaap:PaidInKindInterest").standard_concepts == ["OtherNonCashItemsCF"]


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
def test_standardization_preserves_filed_data(mapper, tag, statement_type):
    item = {
        "concept": f"us-gaap_{tag}",
        "label": "Filed disclosure label",
        "values": {"2025-12-31": -123_456},  # a negative result keeps its sign
        "statement_type": statement_type,
    }
    result = standardize_statement([item], mapper)
    assert len(result) == 1
    assert {key: value for key, value in result[0].items() if key != "standard_concept"} == item
    assert result[0]["standard_concept"] == EXPECTED[tag][0]


# --- statements from real filings ----------------------------------------------

def _frame(directory, statement):
    xbrl = XBRL.from_directory(FIXTURES / directory)
    frame = getattr(xbrl.statements, statement)().to_dataframe()
    return xbrl, frame[~frame["dimension"]]


def _value(frame, concept, period):
    rows = frame[frame["standard_concept"] == concept]
    assert len(rows) == 1, rows[["concept", "label"]]
    return rows.iloc[0][period]


def test_jpmorgan_fy2023_broker_lines():
    xbrl, income = _frame("jpm/10k_2024", "income_statement")
    # Before the fix: these rows had no standard concept.
    assert _value(income, "NetRevenueAfterInterestExpense", "2023-12-31 (FY)") == 158_104_000_000
    assert _value(income, "InvestmentBankingRevenue", "2023-12-31 (FY)") == 6_519_000_000
    _, balance = _frame("jpm/10k_2024", "balance_sheet")
    assert _value(balance, "SecuritiesBorrowed", "2023-12-31") == 200_436_000_000
    # get_revenue() reads the net-revenue element by name and is unchanged.
    assert Financials(xbrl).get_revenue() == 158_104_000_000


def test_golub_bdc_paid_in_kind_interest():
    _, income = _frame("gbdc", "income_statement")
    rows = income[income["standard_concept"] == "InterestIncomePaidInKind"]
    assert list(rows["concept"]) == ["us-gaap_InterestIncomeOperatingPaidInKind"]
    assert list(rows["2025-03-31 (Q2)"]) == [14_045_000]
