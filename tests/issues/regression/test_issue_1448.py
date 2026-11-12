"""
Standard concepts for cash income taxes by jurisdiction (ASU 2023-09), PR A of #1448.

The nine jurisdictional cash-tax elements FASB added in the 2024 taxonomy had no standard
concept, so ServiceNow's FY2025 "Federal", "State" and "Foreign" rows under "Income taxes
paid, net of refunds" carried none. They now map one to one to nine new concepts:

==============================================  ==============================
Element (us-gaap)                               Standard concept
==============================================  ==============================
IncomeTaxPaidFederalAfterRefundReceived         IncomeTaxesPaidFederal
IncomeTaxPaidStateAndLocalAfterRefundReceived   IncomeTaxesPaidStateLocal
IncomeTaxPaidForeignAfterRefundReceived         IncomeTaxesPaidForeign
IncomeTaxPaidFederalBeforeRefundReceived        IncomeTaxesPaidFederalGross
IncomeTaxPaidStateAndLocalBeforeRefundReceived  IncomeTaxesPaidStateLocalGross
IncomeTaxPaidForeignBeforeRefundReceived        IncomeTaxesPaidForeignGross
ProceedsFromIncomeTaxRefundFederal              IncomeTaxRefundsFederal
ProceedsFromIncomeTaxRefundStateAndLocal        IncomeTaxRefundsStateLocal
ProceedsFromIncomeTaxRefundForeign              IncomeTaxRefundsForeign
==============================================  ==============================

"Federal" is the federal or national jurisdiction, not only the United States. All nine are
components of cash taxes paid, never income tax expense (#1440). The aggregates
IncomeTaxesPaid, IncomeTaxesPaidNet and ProceedsFromIncomeTaxRefunds stay unmapped; the #1858
synonym groups ``income_taxes_paid`` and ``income_taxes_paid_gross`` reach the first two.
A jurisdiction member (a state or a country on IncomeTaxAuthorityAxis) is already inside its
jurisdiction's total, so dimensioned rows take no concept and nothing is counted twice.

Ground truth, read from SEC:
- ServiceNow FY2025 10-K, 0001373715-26-000007 (R8): income taxes paid, net of refunds
  $46M federal + $83M state + $154M foreign = $283M. New Jersey $15M is inside the $83M;
  India $38M, Brazil $34M, Ireland $29M and the Netherlands $22M are inside the $154M.
- Allegro MicroSystems FY2026 10-K, 0001193125-26-233537 (income taxes narrative): federal
  refund $30,889K, net foreign payments $3,324K, net state payments $484K; net income taxes
  refunded $27,081K, and IncomeTaxesPaidNet is $-27,081K for the year.
- NVIDIA FY2026 10-K, 0001045810-26-000021 (tracked fixture): federal $16,755M; California
  $1,049M and other states $1,041M; Israel $1,287M and other foreign $156M; total $20,288M.
- e.l.f. Beauty FY2026 (companyfacts fixture, 0001600033-26-000020): federal $14,440K, state
  and local $3,491K, foreign $3,430K; IncomeTaxesPaidNet $21,361K.

PR B of #1448 maps, definition only, the four 2023-taxonomy elements that split the change in
cash by continuing and discontinued operations (prefix
CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecrease):

============================================================================  ==================================
Suffix                                                                        Standard concept
============================================================================  ==================================
IncludingExchangeRateEffectContinuingOperations                               NetChangeInCashContinuingOps
ExcludingExchangeRateEffectContinuingOperations                               NetChangeInCashContinuingOpsExFX
IncludingExchangeRateEffectDisposalGroupIncludingDiscontinuedOperations       NetChangeInCashDiscontinuedOps
ExcludingExchangeRateEffectDisposalGroupIncludingDiscontinuedOperations       NetChangeInCashDiscontinuedOpsExFX
============================================================================  ==================================

None of them is NetChangeInCash: a continuing-operations row is never the whole change in cash,
even when the filer reports no discontinued row. Nothing is summed or derived.

Ground truth, read from SEC:
- Conagra FY2026 10-K, 0001104659-26-083905 (R8), year ended 2025-05-25: net change in cash
  including held-for-sale balances $-11.0M, "Less: net change in cash balances classified as
  assets held for sale" $-1.3M, net change in cash (continuing-tagged) $-9.7M. The disposal
  groups are held for sale, not discontinued operations, so the $-1.3M row gets a
  "discontinued operations" concept from its element alone; the maintainer accepted that.
- DXC FY2026 10-K, 0001688568-26-000022 (R8): the only net-change row is continuing-tagged,
  $-59M (FY2026), $572M (FY2025), $-634M (FY2024), and it stays a component.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1448
"""

import json
from pathlib import Path

import pytest

from edgar.entity.mappings_loader import get_primary_statement, load_virtual_trees
from edgar.entity.parser import EntityFactsParser
from edgar.httprequests import download_file
from edgar.standardization import SynonymGroups
from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import get_reverse_index

pytestmark = pytest.mark.regression

_STANDARDIZATION = Path(reverse_index_module.__file__).parent
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# element -> (concept, display name)
CASH_TAXES = {
    "IncomeTaxPaidFederalAfterRefundReceived": (
        "IncomeTaxesPaidFederal", "Income Taxes Paid, Federal, Net of Refunds"),
    "IncomeTaxPaidStateAndLocalAfterRefundReceived": (
        "IncomeTaxesPaidStateLocal", "Income Taxes Paid, State and Local, Net of Refunds"),
    "IncomeTaxPaidForeignAfterRefundReceived": (
        "IncomeTaxesPaidForeign", "Income Taxes Paid, Foreign, Net of Refunds"),
    "IncomeTaxPaidFederalBeforeRefundReceived": (
        "IncomeTaxesPaidFederalGross", "Income Taxes Paid, Federal, Before Refunds"),
    "IncomeTaxPaidStateAndLocalBeforeRefundReceived": (
        "IncomeTaxesPaidStateLocalGross", "Income Taxes Paid, State and Local, Before Refunds"),
    "IncomeTaxPaidForeignBeforeRefundReceived": (
        "IncomeTaxesPaidForeignGross", "Income Taxes Paid, Foreign, Before Refunds"),
    "ProceedsFromIncomeTaxRefundFederal": (
        "IncomeTaxRefundsFederal", "Income Tax Refunds Received, Federal"),
    "ProceedsFromIncomeTaxRefundStateAndLocal": (
        "IncomeTaxRefundsStateLocal", "Income Tax Refunds Received, State and Local"),
    "ProceedsFromIncomeTaxRefundForeign": (
        "IncomeTaxRefundsForeign", "Income Tax Refunds Received, Foreign"),
}
NEW_CONCEPTS = {concept for concept, _ in CASH_TAXES.values()}
FEDERAL = [element for element in CASH_TAXES if "Federal" in element]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


# ---------------------------------------------------------------------------
# Lookups and entry shape (offline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("element", sorted(CASH_TAXES))
@pytest.mark.parametrize("spelling", ["us-gaap:{}", "us-gaap_{}", "{}"])
def test_each_element_maps_to_its_own_concept(index, element, spelling):
    concept, display = CASH_TAXES[element]
    result = index.lookup(spelling.format(element))

    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]
    assert result.is_ambiguous is False
    assert DISPLAY_NAMES[concept] == display


@pytest.mark.parametrize("element", sorted(CASH_TAXES))
def test_entry_shape_follows_the_hand_added_convention(element):
    concept, display = CASH_TAXES[element]
    entry = GAAP_MAPPINGS[element]

    assert entry["standard_tags"] == [concept]
    assert entry["display_name"] == display
    assert entry["statement"] == "CashFlowStatement"
    # Supplemental cash-flow disclosures: no operating/investing/financing section.
    assert entry["section"] is None
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    assert entry["company_count"] > 0
    for stat in ("occurrence_rate", "temporal_consistency", "years_present", "first_year", "last_year"):
        assert stat not in entry


@pytest.mark.parametrize("element", sorted(CASH_TAXES))
def test_every_definition_says_it_is_not_tax_expense(index, element):
    comment = index.lookup(f"us-gaap:{element}").comment
    assert "not income tax expense" in comment or "not a tax benefit or negative tax expense" in comment


@pytest.mark.parametrize("element", FEDERAL)
def test_federal_means_federal_or_national(index, element):
    assert "federal or national tax jurisdiction (not only the United States)" in index.lookup(element).comment


@pytest.mark.parametrize("element", sorted(CASH_TAXES))
@pytest.mark.parametrize("context", ["CashFlowStatement", "IncomeStatement", "BalanceSheet"])
def test_context_never_moves_an_element_to_another_concept(index, element, context):
    assert index.get_standard_concept(element, context=context) == CASH_TAXES[element][0]


def test_nine_elements_nine_concepts():
    assert len(NEW_CONCEPTS) == 9
    keys = {key for key, entry in GAAP_MAPPINGS.items()
            if isinstance(entry, dict) and set(entry.get("standard_tags", [])) & NEW_CONCEPTS}
    assert keys == set(CASH_TAXES)


# ---------------------------------------------------------------------------
# #1440 and #1858 protections (offline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("aggregate", ["IncomeTaxesPaid", "IncomeTaxesPaidNet", "ProceedsFromIncomeTaxRefunds"])
def test_aggregates_stay_unmapped(index, aggregate):
    assert index.lookup(f"us-gaap:{aggregate}") is None
    assert aggregate not in GAAP_MAPPINGS


def test_aggregates_are_still_reached_through_the_1858_groups():
    groups = SynonymGroups()
    assert groups.get_synonyms("income_taxes_paid") == ["IncomeTaxesPaidNet"]
    assert groups.get_synonyms("income_taxes_paid_gross") == ["IncomeTaxesPaid"]
    for element in CASH_TAXES:
        # A jurisdiction component is never a synonym of the whole.
        assert groups.identify_concepts(element) == [], element


def test_no_element_maps_to_tax_expense():
    for concept in ("IncomeTaxes", "CurrentIncomeTaxExpense", "DeferredIncomeTaxExpense"):
        assert concept not in NEW_CONCEPTS
        members = {key for key, entry in GAAP_MAPPINGS.items()
                   if isinstance(entry, dict) and concept in entry.get("standard_tags", [])}
        assert not members & set(CASH_TAXES), concept


@pytest.mark.parametrize("tag", [
    # Jurisdiction enumerations carry sets of jurisdictions, not cash amounts.
    "us-gaap:IncomeTaxPaidAfterRefundReceivedForeignJurisdictionExtensibleEnumeration",
    "us-gaap:IncomeTaxPaidAfterRefundReceivedStateAndLocalJurisdictionsExtensibleEnumeration",
    # Rate reconciliation and current expense by jurisdiction are accrual measures.
    "us-gaap:IncomeTaxReconciliationForeignIncomeTaxRateDifferential",
    "us-gaap:IncomeTaxReconciliationStateAndLocalIncomeTaxes",
    "us-gaap:EffectiveIncomeTaxRateReconciliationForeignIncomeTaxRateDifferential",
    "us-gaap:CurrentFederalTaxExpenseBenefit",
    "us-gaap:CurrentStateAndLocalTaxExpenseBenefit",
    "us-gaap:CurrentForeignTaxExpenseBenefit",
])
def test_neighbouring_tax_elements_take_none_of_the_nine(index, tag):
    result = index.lookup(tag)
    assert result is None or not set(result.standard_concepts) & NEW_CONCEPTS


# ---------------------------------------------------------------------------
# A tracked filing (offline): NVIDIA FY2026 10-K, 0001045810-26-000021
# ---------------------------------------------------------------------------

NVDA_ROLE = "http://www.nvidia.com/role/IncomeTaxesIncomeTaxPaidDetails"


@pytest.fixture(scope="module")
def nvda_xbrl():
    return XBRL.from_directory(FIXTURES / "xbrl" / "nvda" / "10k_2026")


def test_nvidia_jurisdiction_rows_take_the_new_concepts(nvda_xbrl):
    frame = nvda_xbrl.statements[NVDA_ROLE].render(standard=True).to_dataframe()
    plain = frame[~frame["dimension"]]
    concepts = dict(zip(plain["concept"], plain["standard_concept"], strict=True))

    assert concepts["us-gaap_IncomeTaxPaidFederalAfterRefundReceived"] == "IncomeTaxesPaidFederal"
    assert concepts["us-gaap_IncomeTaxPaidStateAndLocalAfterRefundReceived"] == "IncomeTaxesPaidStateLocal"
    assert concepts["us-gaap_IncomeTaxPaidForeignAfterRefundReceived"] == "IncomeTaxesPaidForeign"
    federal = plain[plain["concept"] == "us-gaap_IncomeTaxPaidFederalAfterRefundReceived"].iloc[0]
    assert federal["2026-01-25"] == 16_755_000_000
    total = plain[plain["concept"] == "us-gaap_IncomeTaxesPaidNet"].iloc[0]
    assert total["2026-01-25"] == 20_288_000_000
    assert total["standard_concept"] != total["standard_concept"]  # NaN: the aggregate stays unmapped

    # California, Israel and the "Other" members are inside their jurisdiction totals.
    dimensioned = frame[frame["dimension"]]
    assert len(dimensioned) == 4
    assert dimensioned["standard_concept"].isna().all()


def test_nvidia_jurisdictions_add_up_to_the_total_without_double_counting(nvda_xbrl):
    facts = nvda_xbrl.facts.to_dataframe()
    year = facts[facts["period_end"] == "2026-01-25"]
    paid = year[year["concept"].isin([f"us-gaap:{e}" for e in CASH_TAXES])]
    # The only undimensioned component is federal; state and foreign are filed by member.
    assert paid["numeric_value"].sum() == 16_755_000_000 + 1_049_000_000 + 1_041_000_000 \
        + 1_287_000_000 + 156_000_000 == 20_288_000_000
    total = year[year["concept"] == "us-gaap:IncomeTaxesPaidNet"]["numeric_value"]
    assert list(total) == [20_288_000_000]


# ---------------------------------------------------------------------------
# EntityFacts (offline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("element", sorted(CASH_TAXES))
def test_entity_facts_gives_each_element_the_cash_flow_statement(element):
    assert get_primary_statement(element) == "CashFlowStatement"


@pytest.mark.parametrize("element", sorted(CASH_TAXES))
def test_entity_facts_tree_places_each_element_beside_taxes_paid(element):
    nodes = load_virtual_trees()["CashFlowStatement"]["nodes"]
    parent = "SupplementalCashFlowInformationAbstract"
    assert nodes[element]["parent"] == parent
    assert nodes[element]["label"] == CASH_TAXES[element][1]
    assert element in nodes[parent]["children"]
    assert nodes[element]["is_total"] is False
    # Below the 0.3 threshold: the row is built only for a company that reports it.
    assert nodes[element]["occurrence_rate"] < 0.3


def test_elf_entity_facts_cash_flow_shows_the_jurisdiction_rows():
    raw = json.loads((FIXTURES / "entity" / "elf_facts.json").read_text("utf-8"))
    facts = EntityFactsParser.parse_company_facts(raw)
    frame = facts.cash_flow_statement(periods=2, annual=True, as_dataframe=True)

    rows = {
        "IncomeTaxPaidFederalAfterRefundReceived": 14_440_000,
        "IncomeTaxPaidStateAndLocalAfterRefundReceived": 3_491_000,
        "IncomeTaxPaidForeignAfterRefundReceived": 3_430_000,
    }
    for element, value in rows.items():
        assert frame.loc[element, "label"] == CASH_TAXES[element][1]
        assert frame.loc[element, "FY 2026"] == value
    assert frame.loc["IncomeTaxesPaidNet", "FY 2026"] == sum(rows.values()) == 21_361_000


# ---------------------------------------------------------------------------
# Filed statements (network, cassettes)
# ---------------------------------------------------------------------------

def _xbrl(tmp_path, folder, names):
    for name in names:
        (tmp_path / name).write_text(download_file(folder + name), encoding="utf-8")
    return XBRL.from_directory(tmp_path)


NOW_FOLDER = "https://www.sec.gov/Archives/edgar/data/1373715/000137371526000007/"
NOW_FILES = ("now-20251231.xsd", "now-20251231_pre.xml", "now-20251231_lab.xml", "now-20251231_cal.xml",
             "now-20251231_def.xml", "now-20251231_htm.xml")
ALGM_FOLDER = "https://www.sec.gov/Archives/edgar/data/866291/000119312526233537/"
ALGM_FILES = ("algm-20260327.xsd", "algm-20260327_htm.xml")
ALGM_ROLE = "http://www.allegromicro.com/20260327/taxonomy/role/IncomeTaxesNarrativeDetails"


@pytest.mark.network
@pytest.mark.vcr
def test_servicenow_cash_taxes_by_jurisdiction(tmp_path):
    """ServiceNow FY2025 10-K, 0001373715-26-000007, cash flow statement (R8): income taxes
    paid, net of refunds, $46M federal + $83M state + $154M foreign = $283M."""
    xbrl = _xbrl(tmp_path, NOW_FOLDER, NOW_FILES)
    frame = xbrl.statements["CashFlowStatement"].render(standard=True).to_dataframe()
    plain = frame[~frame["dimension"]]

    by_concept = {}
    for concept in ("IncomeTaxesPaidFederal", "IncomeTaxesPaidStateLocal", "IncomeTaxesPaidForeign"):
        rows = plain[plain["standard_concept"] == concept]
        assert len(rows) == 1, concept
        by_concept[concept] = rows.iloc[0]["2025-12-31"]
    assert by_concept == {"IncomeTaxesPaidFederal": 46_000_000, "IncomeTaxesPaidStateLocal": 83_000_000,
                          "IncomeTaxesPaidForeign": 154_000_000}
    total = plain[plain["concept"] == "us-gaap_IncomeTaxesPaidNet"]
    assert set(total["2025-12-31"]) == {283_000_000}
    assert sum(by_concept.values()) == 283_000_000
    assert total["standard_concept"].isna().all()

    # New Jersey ($15M) and the four countries are inside the state and foreign totals.
    dimensioned = frame[frame["dimension"] & frame["concept"].str.contains("IncomeTaxPaid")]
    details = dict(zip(dimensioned["label"], dimensioned["2025-12-31"], strict=True))
    assert details["New Jersey"] == 15_000_000
    assert {details[c] for c in ("India", "Brazil", "Ireland", "Netherlands")} == {
        38_000_000, 34_000_000, 29_000_000, 22_000_000}
    assert dimensioned["standard_concept"].isna().all()


@pytest.mark.network
@pytest.mark.vcr
def test_allegro_federal_refund_and_a_net_refund_year(tmp_path):
    """Allegro MicroSystems FY2026 10-K, 0001193125-26-233537: federal refund $30,889K, net
    foreign payments $3,324K, net state payments $484K; net income taxes refunded $27,081K."""
    xbrl = _xbrl(tmp_path, ALGM_FOLDER, ALGM_FILES)
    frame = xbrl.statements[ALGM_ROLE].render(standard=True).to_dataframe()
    plain = frame[~frame["dimension"]]

    def row(concept):
        rows = plain[plain["concept"] == concept]
        assert len(rows) == 1, concept
        return rows.iloc[0]

    refund = row("us-gaap_ProceedsFromIncomeTaxRefundFederal")
    assert refund["standard_concept"] == "IncomeTaxRefundsFederal"
    assert refund["2026-03-27"] == 30_889_000
    assert row("us-gaap_IncomeTaxPaidForeignAfterRefundReceived")["standard_concept"] == "IncomeTaxesPaidForeign"
    assert row("us-gaap_IncomeTaxPaidForeignAfterRefundReceived")["2026-03-27"] == 3_324_000
    assert row("us-gaap_IncomeTaxPaidStateAndLocalAfterRefundReceived")["2026-03-27"] == 484_000
    net_refunded = row("us-gaap_ProceedsFromIncomeTaxRefunds")
    assert net_refunded["2026-03-27"] == 30_889_000 - 3_324_000 - 484_000 == 27_081_000
    assert net_refunded["standard_concept"] != net_refunded["standard_concept"]  # NaN: stays unmapped

    # Refunds exceeded payments, so the year's net taxes paid is negative.
    facts = xbrl.facts.to_dataframe()
    net = facts[(facts["concept"] == "us-gaap:IncomeTaxesPaidNet") & (facts["period_end"] == "2026-03-27")]
    assert list(net["numeric_value"]) == [-27_081_000]


# ===========================================================================
# PR B: the change in cash split by continuing and discontinued operations
# ===========================================================================

CHANGE = "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecrease"
# element -> (concept, display name)
CASH_CHANGE = {
    CHANGE + "IncludingExchangeRateEffectContinuingOperations": (
        "NetChangeInCashContinuingOps", "Net Change in Cash, Continuing Operations, Including FX Effect"),
    CHANGE + "ExcludingExchangeRateEffectContinuingOperations": (
        "NetChangeInCashContinuingOpsExFX", "Net Change in Cash, Continuing Operations, Excluding FX Effect"),
    CHANGE + "IncludingExchangeRateEffectDisposalGroupIncludingDiscontinuedOperations": (
        "NetChangeInCashDiscontinuedOps", "Net Change in Cash, Discontinued Operations, Including FX Effect"),
    CHANGE + "ExcludingExchangeRateEffectDisposalGroupIncludingDiscontinuedOperations": (
        "NetChangeInCashDiscontinuedOpsExFX", "Net Change in Cash, Discontinued Operations, Excluding FX Effect"),
}
CHANGE_CONCEPTS = {concept for concept, _ in CASH_CHANGE.values()}
# The whole change in cash: the only elements that are NetChangeInCash, before and after.
WHOLE_CHANGE = {
    "CashAndCashEquivalentsPeriodIncreaseDecrease",
    CHANGE + "ExcludingExchangeRateEffect",
    CHANGE + "IncludingExchangeRateEffect",
    "IncreaseDecreaseInCashAndCashEquivalents",
    "IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges",
    "ifrs-full_IncreaseDecreaseInCashAndCashEquivalents",
}


@pytest.mark.parametrize("element", sorted(CASH_CHANGE))
@pytest.mark.parametrize("spelling", ["us-gaap:{}", "us-gaap_{}", "{}"])
def test_each_cash_change_element_maps_to_its_own_concept(index, element, spelling):
    concept, display = CASH_CHANGE[element]
    result = index.lookup(spelling.format(element))

    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]
    assert result.is_ambiguous is False
    assert DISPLAY_NAMES[concept] == display


@pytest.mark.parametrize("element", sorted(CASH_CHANGE))
def test_cash_change_entries_follow_the_hand_added_convention(element):
    concept, display = CASH_CHANGE[element]
    entry = GAAP_MAPPINGS[element]

    assert entry["standard_tags"] == [concept]
    assert entry["display_name"] == display
    assert entry["statement"] == "CashFlowStatement"
    assert entry["section"] is None
    # A component of the change in cash, never the total.
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    assert entry["company_count"] > 0
    for stat in ("occurrence_rate", "temporal_consistency", "years_present", "first_year", "last_year"):
        assert stat not in entry


@pytest.mark.parametrize("element", sorted(CASH_CHANGE))
@pytest.mark.parametrize("context", ["CashFlowStatement", "IncomeStatement", "BalanceSheet"])
def test_no_cash_change_component_is_ever_net_change_in_cash(index, element, context):
    assert index.get_standard_concept(element, context=context) == CASH_CHANGE[element][0]
    assert "NetChangeInCash" not in index.lookup(element).standard_concepts


def test_net_change_in_cash_keeps_exactly_the_whole_change_elements():
    members = {key for key, entry in GAAP_MAPPINGS.items()
               if isinstance(entry, dict) and "NetChangeInCash" in entry.get("standard_tags", [])}
    assert members == WHOLE_CHANGE
    totals = json.loads((_STANDARDIZATION / "total_membership.json").read_text(encoding="utf-8"))
    # The #1444 closed membership of the total lists none of the four either.
    assert not set(totals["totals"]["NetChangeInCash"]) & set(CASH_CHANGE)
    assert not CHANGE_CONCEPTS & set(totals["totals"])


def test_four_elements_four_concepts():
    assert len(CHANGE_CONCEPTS) == 4
    keys = {key for key, entry in GAAP_MAPPINGS.items()
            if isinstance(entry, dict) and set(entry.get("standard_tags", [])) & CHANGE_CONCEPTS}
    assert keys == set(CASH_CHANGE)


@pytest.mark.parametrize("element", sorted(CASH_CHANGE))
def test_cash_change_definitions_keep_scope_and_fx_basis(index, element):
    comment = index.lookup(element).comment
    suffix = element.removeprefix(CHANGE)
    if suffix.endswith("ContinuingOperations"):
        assert "attributable to continuing operations" in comment
        assert "never the entity's total change in cash (NetChangeInCash)" in comment
    else:
        assert "attributable to discontinued operations" in comment
        assert "held-for-sale disposal group that is not a discontinued operation" in comment
    basis = "including" if suffix.startswith("Including") else "excluding"
    assert f"{basis} the effect of exchange rate changes" in comment


@pytest.mark.parametrize("element", sorted(CASH_CHANGE))
def test_entity_facts_gives_each_cash_change_element_its_own_row(element):
    assert get_primary_statement(element) == "CashFlowStatement"
    nodes = load_virtual_trees()["CashFlowStatement"]["nodes"]
    children = nodes["StatementOfCashFlowsAbstract"]["children"]
    assert children.index(element) > children.index(CHANGE + "IncludingExchangeRateEffect")
    assert nodes[element]["label"] == CASH_CHANGE[element][1]
    assert nodes[element]["is_total"] is False
    assert nodes[element]["occurrence_rate"] < 0.3


def test_conagra_entity_facts_shows_the_split_beside_the_whole():
    """Conagra FY2026 10-K, 0001104659-26-083905, via trimmed SEC company facts: for the year
    ended 2025-05-25, $-11.0M total, $-1.3M held for sale, $-9.7M continuing-tagged."""
    raw = json.loads((FIXTURES / "issues" / "regression" / "issue_1448"
                      / "conagra_cash_change_companyfacts.json").read_text("utf-8"))
    facts = EntityFactsParser.parse_company_facts(raw)
    frame = facts.cash_flow_statement(periods=3, annual=True, as_dataframe=True)

    whole = CHANGE + "IncludingExchangeRateEffect"
    continuing = CHANGE + "IncludingExchangeRateEffectContinuingOperations"
    disposal = CHANGE + "IncludingExchangeRateEffectDisposalGroupIncludingDiscontinuedOperations"
    assert frame.loc[whole, "FY 2025"] == -11_000_000
    assert frame.loc[continuing, "FY 2025"] == -9_700_000
    assert frame.loc[disposal, "FY 2025"] == -1_300_000
    assert frame.loc[continuing, "label"] == CASH_CHANGE[continuing][1]
    assert frame.loc[disposal, "label"] == CASH_CHANGE[disposal][1]
    assert not frame.loc[continuing, "is_total"]
    # The whole row is still the whole, and keeps its own value.
    assert frame.loc[whole, "FY 2026"] == 150_000_000
    assert frame.loc[whole, "FY 2025"] - frame.loc[disposal, "FY 2025"] == frame.loc[continuing, "FY 2025"]


CAG_FOLDER = "https://www.sec.gov/Archives/edgar/data/23217/000110465926083905/"
# No calculation or definition linkbase: the statement needs presentation and labels only.
CAG_FILES = ("tmb-20260531.xsd", "tmb-20260531x10k_htm.xml", "tmb-20260531_pre.xml", "tmb-20260531_lab.xml")
DXC_FOLDER = "https://www.sec.gov/Archives/edgar/data/1688568/000168856826000022/"
DXC_FILES = ("dxc-20260331.xsd", "dxc-20260331_htm.xml", "dxc-20260331_pre.xml", "dxc-20260331_lab.xml")


def _change_rows(xbrl):
    """Undimensioned cash flow rows, and the change-in-cash rows among them by element."""
    frame = xbrl.statements["CashFlowStatement"].render(standard=True).to_dataframe()
    plain = frame[~frame["dimension"]]
    rows = plain[plain["concept"].str.startswith("us-gaap_" + CHANGE)]
    return plain, {concept.removeprefix("us-gaap_" + CHANGE): row
                   for concept, row in zip(rows["concept"], rows.to_dict("records"), strict=True)}


@pytest.mark.network
@pytest.mark.vcr
def test_conagra_continuing_and_held_for_sale_rows_stay_components(tmp_path):
    """Conagra FY2026 10-K, 0001104659-26-083905 (R8), year ended 2025-05-25: total $-11.0M,
    held for sale $-1.3M, continuing-tagged $-9.7M; FY2026 total and continuing both $150.0M."""
    plain, rows = _change_rows(_xbrl(tmp_path, CAG_FOLDER, CAG_FILES))
    assert set(rows) == {"IncludingExchangeRateEffect", "IncludingExchangeRateEffectContinuingOperations",
                         "IncludingExchangeRateEffectDisposalGroupIncludingDiscontinuedOperations"}

    whole = rows["IncludingExchangeRateEffect"]
    continuing = rows["IncludingExchangeRateEffectContinuingOperations"]
    disposal = rows["IncludingExchangeRateEffectDisposalGroupIncludingDiscontinuedOperations"]
    assert whole["standard_concept"] == "NetChangeInCash"
    assert continuing["standard_concept"] == "NetChangeInCashContinuingOps"
    # Accepted risk: these disposal groups are held for sale, not discontinued operations.
    assert disposal["standard_concept"] == "NetChangeInCashDiscontinuedOps"

    assert (whole["2025-05-25"], disposal["2025-05-25"], continuing["2025-05-25"]) == (
        -11_000_000, -1_300_000, -9_700_000)
    assert whole["2025-05-25"] - disposal["2025-05-25"] == continuing["2025-05-25"]
    assert whole["2026-05-31"] == continuing["2026-05-31"] == 150_000_000
    # Exactly one row is the whole change in cash.
    assert (plain["standard_concept"] == "NetChangeInCash").sum() == 1


@pytest.mark.network
@pytest.mark.vcr
def test_dxc_continuing_only_row_is_not_promoted_to_the_whole(tmp_path):
    """DXC FY2026 10-K, 0001688568-26-000022 (R8): the only net-change row is
    continuing-tagged, $-59M (FY2026), $572M (FY2025), $-634M (FY2024)."""
    plain, rows = _change_rows(_xbrl(tmp_path, DXC_FOLDER, DXC_FILES))
    assert list(rows) == ["IncludingExchangeRateEffectContinuingOperations"]

    row = rows["IncludingExchangeRateEffectContinuingOperations"]
    assert row["standard_concept"] == "NetChangeInCashContinuingOps"
    assert (row["2026-03-31"], row["2025-03-31"], row["2024-03-31"]) == (-59_000_000, 572_000_000, -634_000_000)
    # No row is promoted to the whole change in cash.
    assert not (plain["standard_concept"] == "NetChangeInCash").any()
