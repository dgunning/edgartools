"""
Securities were standardized as "Cash and Cash Equivalents" or "Total Assets".
These corrected mappings identify investments and leave the current
held-to-maturity credit-loss allowance unmapped. Offline filing fixtures pin
the reported cash, investment and asset values.

A follow-up corrects 16 more entries the reporter listed on 2026-10-07. Two
carrying values on the balance sheet (AvailableForSaleSecurities,
HeldToMaturitySecurities) become investments, resolved by section. The
measurement-basis, maturity-bucket and unrealized gain/loss disclosures, and the
mixed "Total investments" (us-gaap:Investments), have no standard concept. Before
it, Allstate's FY2025 cash group summed to $83,915M against $678M of filed cash.
The cash concept keeps "Cash and Cash Equivalents" even though CashAndCashEquivalents
(the cash-flow total) shares it: CashAndMarketableSecurities holds the plain cash
tags, CashAndCashEquivalentsAtCarryingValue among them (~6,700 companies), so a
"Marketable Securities" label would misname almost every company's cash line.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1436
GitHub Issue: https://github.com/dgunning/edgartools/issues/1417
"""

import json
from pathlib import Path

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.core import ConceptMapper, MappingStore, standardize_statement
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sections import get_section_for_concept
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES

EXPECTED = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1436_securities_not_cash_expected.json").read_text(encoding="utf-8")
)
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

ORIGINAL_TAGS = [
    "AvailableForSaleSecuritiesCurrent",
    "AvailableForSaleSecuritiesDebtSecurities",
    "AvailableForSaleSecuritiesEquitySecuritiesCurrent",
    "AvailableforsaleSecuritiesRestrictedNoncurrent",
    "DebtSecuritiesAvailableForSaleExcludingAccruedInterest",
    "DebtSecuritiesAvailableForSaleExcludingAccruedInterestCurrent",
    "DebtSecuritiesAvailableForSaleExcludingAccruedInterestNoncurrent",
    "DebtSecuritiesCurrent",
    "DebtSecuritiesHeldToMaturityAllowanceForCreditLossCurrent",
    "DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLoss",
    "DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossCurrent",
    "DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossNoncurrent",
    "DebtSecuritiesHeldToMaturityExcludingAccruedInterestAfterAllowanceForCreditLoss",
    "DebtSecuritiesHeldToMaturityExcludingAccruedInterestAfterAllowanceForCreditLossCurrent",
    "DebtSecuritiesHeldToMaturityExcludingAccruedInterestAfterAllowanceForCreditLossNoncurrent",
    "DebtSecuritiesNoncurrent",
    "EquitySecuritiesFvNi",
    "HeldToMaturitySecuritiesCurrent",
    "MarketableSecurities",
    "MarketableSecuritiesEquitySecuritiesCurrent",
    "MarketableSecuritiesFixedMaturitiesCurrent",
    "MarketableSecuritiesNoncurrent",
    "MarketableSecuritiesRestrictedNoncurrent",
    "OtherMarketableSecuritiesCurrent",
    "OtherShortTermInvestments",
    "TradingSecurities",
    "TradingSecuritiesDebt",
    "TradingSecuritiesEquity",
    "TradingSecuritiesOther",
]

# The reporter's 2026-10-07 comment on the issue: 16 more entries that led with the cash concept.
FOLLOWUP_TAGS = [
    "AvailableForSaleDebtSecuritiesAmortizedCostBasis",
    "AvailableForSaleSecurities",
    "AvailableForSaleSecuritiesAccumulatedGrossUnrealizedGainLossBeforeTax",
    "AvailableForSaleSecuritiesAmortizedCost",
    "AvailableForSaleSecuritiesDebtMaturitiesAfterFiveThroughTenYearsFairValue",
    "AvailableForSaleSecuritiesDebtMaturitiesAfterOneThroughFiveYearsFairValue",
    "AvailableForSaleSecuritiesDebtMaturitiesAfterTenYearsFairValue",
    "AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearFairValue",
    "AvailableForSaleSecuritiesDebtMaturitiesWithoutSingleMaturityDateFairValue",
    "AvailableForSaleSecuritiesFairValueDisclosure",
    "DebtSecuritiesAvailableForSaleAmortizedCostCurrent",
    "HeldToMaturitySecurities",
    "HeldToMaturitySecuritiesAccumulatedUnrecognizedHoldingGain",
    "HeldToMaturitySecuritiesAccumulatedUnrecognizedHoldingLoss",
    "HeldToMaturitySecuritiesFairValue",
    "Investments",
]

SECURITIES_TAGS = ORIGINAL_TAGS + FOLLOWUP_TAGS

INDUSTRIES = sorted({code for _, _, code in _FF48_SIC_RANGES})
STATEMENT_TYPES = ["BalanceSheet", "http://example.com/role/ConsolidatedBalanceSheets", ""]
PAIRED_TAGS = [tag for tag, concepts in EXPECTED.items() if concepts and len(concepts) == 2]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_expected_file_covers_the_corrected_entries():
    assert set(SECURITIES_TAGS) == set(EXPECTED)
    assert len(ORIGINAL_TAGS) == 29
    assert len(FOLLOWUP_TAGS) == 16
    assert len(SECURITIES_TAGS) == len(set(SECURITIES_TAGS)) == 45
    assert len(INDUSTRIES) == 48


@pytest.mark.parametrize("tag", SECURITIES_TAGS)
def test_corrected_entries(index, tag):
    expected = EXPECTED[tag]
    result = index.lookup(tag)
    if expected is None:
        assert result is None
        assert tag not in index._gaap_mappings
    else:
        assert result is not None and result.standard_concepts == expected
        assert result.display_names == [DISPLAY_NAMES[concept] for concept in expected]
        assert result.is_ambiguous is (len(expected) == 2)


@pytest.mark.parametrize("tag", SECURITIES_TAGS)
@pytest.mark.parametrize("industry", INDUSTRIES)
def test_no_industry_brings_the_old_concept_back(index, tag, industry):
    """Every industry must use the corrected mapping, including the deletion."""
    plain = index.lookup(tag)
    with_industry = index.lookup(tag, industry=industry)
    assert with_industry == plain
    if with_industry is not None:
        assert with_industry.standard_concepts == EXPECTED[tag]
    else:
        assert EXPECTED[tag] is None


def test_no_corrected_entry_keeps_an_industry_override():
    assert [tag for tag in SECURITIES_TAGS if "industry_overrides" in GAAP_MAPPINGS.get(tag, {})] == []


@pytest.mark.parametrize("tag", [tag for tag in SECURITIES_TAGS if EXPECTED[tag]])
def test_corrected_entry_metadata_matches_its_primary_concept(tag):
    """Stored metadata must describe the first candidate and preserve ambiguity."""
    concepts = EXPECTED[tag]
    entry = GAAP_MAPPINGS[tag]
    assert entry["display_name"] == DISPLAY_NAMES[concepts[0]]
    assert entry["statement"] == "BalanceSheet"
    assert entry["section"] == get_section_for_concept(concepts[0], "BalanceSheet")
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    if len(concepts) == 2:
        assert entry["ambiguous"] is True
    else:
        assert "ambiguous" not in entry


def test_corrected_securities_do_not_map_to_cash_or_total_assets(index):
    for tag in SECURITIES_TAGS:
        result = index.lookup(tag)
        if result is None:
            continue
        assert "CashAndMarketableSecurities" not in result.standard_concepts, tag
        assert "Assets" not in result.standard_concepts, tag
        assert set(result.standard_concepts) <= {"ShortTermInvestments", "LongtermInvestments"}, tag


def test_no_securities_entry_is_a_total():
    """A total flag on the held-to-maturity element made JPMorgan show two "Total Assets" rows."""
    assert [tag for tag in SECURITIES_TAGS if GAAP_MAPPINGS.get(tag, {}).get("is_total")] == []


@pytest.mark.parametrize(
    "tag, concept, display",
    [
        ("AvailableForSaleSecuritiesCurrent", "ShortTermInvestments", "Short-Term Investments"),
        ("DebtSecuritiesHeldToMaturityExcludingAccruedInterestAfterAllowanceForCreditLoss", "LongtermInvestments", "Long-Term Investments"),
        ("DebtSecuritiesNoncurrent", "LongtermInvestments", "Long-Term Investments"),
        ("OtherShortTermInvestments", "ShortTermInvestments", "Short-Term Investments"),
        ("TradingSecuritiesEquity", "ShortTermInvestments", "Short-Term Investments"),
    ],
)
def test_concept_follows_the_element_definition(index, tag, concept, display):
    """Current elements are short-term investments, noncurrent ones long-term (ASC 210-10-45-1, 320-10-45-2)."""
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]


def test_cash_concept_excludes_the_corrected_securities(index):
    """The corrected tags leave this concept; combined cash/investment tags remain."""
    members = {
        tag for tag, entry in index._index.items() if isinstance(entry, dict) and "CashAndMarketableSecurities" in entry.get("standard_tags", [])
    }
    assert members.isdisjoint(SECURITIES_TAGS)
    assert "CashAndCashEquivalentsAtCarryingValue" in members


@pytest.mark.parametrize("tag", SECURITIES_TAGS)
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
@pytest.mark.parametrize("section", [None, "Current Assets", "Non-Current Assets"])
def test_public_context_paths_exclude_cash_and_asset_totals(index, tag, statement_type, section):
    """All statement-type forms retain investment candidates and their labels."""
    context = {"statement_type": statement_type, "section": section}
    concept = index.get_standard_concept(tag, context)
    display = index.get_display_name(tag, context)
    if EXPECTED[tag] is None:
        assert concept is None
        assert display is None
    else:
        assert concept in EXPECTED[tag]
        assert display == DISPLAY_NAMES[concept]


@pytest.mark.parametrize("tag", PAIRED_TAGS)
@pytest.mark.parametrize(
    "section, concept",
    [("Current Assets", "ShortTermInvestments"), ("Non-Current Assets", "LongtermInvestments")],
)
def test_balance_sheet_sections_resolve_paired_investments(index, tag, section, concept):
    context = {"statement_type": "BalanceSheet", "section": section}
    assert index.get_standard_concept(tag, context) == concept
    assert index.get_display_name(tag, context) == DISPLAY_NAMES[concept]


@pytest.mark.parametrize("tag", SECURITIES_TAGS)
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
def test_standardization_preserves_filed_data_on_all_statement_type_paths(mapper, tag, statement_type):
    item = {
        "concept": f"us-gaap_{tag}",
        "label": "Filed securities label",
        "values": {"2023-12-31": 123_456},
        "statement_type": statement_type,
    }
    result = standardize_statement([item], mapper)
    assert len(result) == 1
    assert "standard_concept" not in item
    assert {key: value for key, value in result[0].items() if key != "standard_concept"} == item
    if EXPECTED[tag] is None:
        assert "standard_concept" not in result[0]
    else:
        assert result[0]["standard_concept"] in EXPECTED[tag]


def test_deleted_element_has_no_answer(index):
    """The allowance on current held-to-maturity securities fits no standard concept; silence, not a wrong one."""
    assert index.lookup("DebtSecuritiesHeldToMaturityAllowanceForCreditLossCurrent") is None
    assert index.lookup("NotAnElementInAnyTaxonomy") is None


FIXTURES = Path(__file__).parents[2] / "fixtures" / "xbrl"


def _balance_sheet(directory):
    xbrl = XBRL.from_directory(FIXTURES / directory)
    statement = xbrl.statements["BalanceSheet"]
    assert statement is not None
    frame = statement.render(standard=True).to_dataframe()
    return frame[~frame["dimension"]]


def _rows(frame, standard_concept, column):
    selected = frame[frame["standard_concept"] == standard_concept]
    return dict(zip(selected["concept"], selected[column], strict=True))


@pytest.fixture(scope="module")
def jpm_fy2023():
    return _balance_sheet("jpm/10k_2024")


@pytest.fixture(scope="module")
def aubn_fy2023():
    return _balance_sheet("aubn/10k_2023")


@pytest.fixture(scope="module")
def ko_fy2023():
    return _balance_sheet("ko/10k_2024")


def test_jpmorgan_securities_are_investments_and_total_assets_appears_once(jpm_fy2023):
    """JPMorgan FY2023 10-K, 0000019617-24-000225, balance sheet: AFS $201,704M, HTM $369,848M, total assets $3,875,393M."""
    assert _rows(jpm_fy2023, "LongtermInvestments", "2023-12-31") == {
        "us-gaap_DebtSecuritiesAvailableForSaleExcludingAccruedInterest": 201_704_000_000,
        "us-gaap_DebtSecuritiesHeldToMaturityExcludingAccruedInterestAfterAllowanceForCreditLoss": 369_848_000_000,
    }
    assert _rows(jpm_fy2023, "Assets", "2023-12-31") == {"us-gaap_Assets": 3_875_393_000_000}
    assert "us-gaap_DebtSecuritiesAvailableForSaleExcludingAccruedInterest" not in _rows(jpm_fy2023, "CashAndMarketableSecurities", "2023-12-31")


def test_auburn_national_cash_excludes_its_securities(aubn_fy2023):
    """Auburn National FY2023 10-K, 0001193125-24-067944: cash and due from banks $27,127K, bank deposits $12,830K, AFS securities $270,910K.

    Federal funds sold ($31,412K) joined the cash group in GH #1441, so the group now sums to the
    filed cash and cash equivalents of $71,369K.
    """
    cash = _rows(aubn_fy2023, "CashAndMarketableSecurities", "2023-12-31")
    assert cash == {
        "us-gaap_CashAndDueFromBanks": 27_127_000,
        "us-gaap_FederalFundsSold": 31_412_000,
        "us-gaap_InterestBearingDepositsInBanks": 12_830_000,
    }
    assert sum(cash.values()) == 71_369_000
    assert _rows(aubn_fy2023, "LongtermInvestments", "2023-12-31") == {"us-gaap_AvailableForSaleSecuritiesDebtSecurities": 270_910_000}


def test_coca_cola_short_term_investments_are_not_cash(ko_fy2023):
    """Coca-Cola FY2023 10-K, 0000021344-24-000009: short-term investments $2,997M and marketable securities $1,300M, both current."""
    assert _rows(ko_fy2023, "ShortTermInvestments", "2023-12-31") == {
        "us-gaap_OtherShortTermInvestments": 2_997_000_000,
        "us-gaap_MarketableSecurities": 1_300_000_000,
    }
    assert "us-gaap_MarketableSecurities" not in _rows(ko_fy2023, "CashAndMarketableSecurities", "2023-12-31")


# --- Follow-up: the reporter's 2026-10-07 entries and the cash label ---


def test_followup_lookups(index):
    """Each entry, spelled out independently of the expected-mapping fixture."""
    for tag in ("AvailableForSaleSecurities", "HeldToMaturitySecurities"):
        result = index.lookup(f"us-gaap:{tag}")
        assert result is not None, tag
        assert result.standard_concepts == ["LongtermInvestments", "ShortTermInvestments"], tag
        assert result.display_names == ["Long-Term Investments", "Short-Term Investments"], tag
        assert result.is_ambiguous is True, tag
    for tag in (
        "AvailableForSaleDebtSecuritiesAmortizedCostBasis",
        "AvailableForSaleSecuritiesAccumulatedGrossUnrealizedGainLossBeforeTax",
        "AvailableForSaleSecuritiesAmortizedCost",
        "AvailableForSaleSecuritiesDebtMaturitiesAfterFiveThroughTenYearsFairValue",
        "AvailableForSaleSecuritiesDebtMaturitiesAfterOneThroughFiveYearsFairValue",
        "AvailableForSaleSecuritiesDebtMaturitiesAfterTenYearsFairValue",
        "AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearFairValue",
        "AvailableForSaleSecuritiesDebtMaturitiesWithoutSingleMaturityDateFairValue",
        "AvailableForSaleSecuritiesFairValueDisclosure",
        "DebtSecuritiesAvailableForSaleAmortizedCostCurrent",
        "HeldToMaturitySecuritiesAccumulatedUnrecognizedHoldingGain",
        "HeldToMaturitySecuritiesAccumulatedUnrecognizedHoldingLoss",
        "HeldToMaturitySecuritiesFairValue",
        "Investments",
    ):
        assert index.lookup(f"us-gaap:{tag}") is None, tag
        assert tag not in GAAP_MAPPINGS, tag


@pytest.mark.parametrize("section, concept", [("Current Assets", "ShortTermInvestments"), ("Non-Current Assets", "LongtermInvestments")])
def test_held_to_maturity_securities_take_the_side_of_their_section(index, section, concept):
    context = {"statement_type": "BalanceSheet", "section": section}
    assert index.get_standard_concept("us-gaap_HeldToMaturitySecurities", context) == concept


def test_cash_concept_keeps_its_label(index):
    """The plain cash line keeps "Cash and Cash Equivalents" (decided on #1436, 2026-10-23).

    CashAndMarketableSecurities is where CashAndCashEquivalentsAtCarryingValue and the
    other plain cash tags land, so renaming it would misname almost every company's
    cash. Separating it from CashAndCashEquivalents means moving those tags, which is
    its own change.
    """
    assert DISPLAY_NAMES["CashAndMarketableSecurities"] == "Cash and Cash Equivalents"
    result = index.lookup("us-gaap:CashAndCashEquivalentsAtCarryingValue")
    assert result is not None
    assert result.standard_concepts == ["CashAndMarketableSecurities"]
    assert result.display_names == ["Cash and Cash Equivalents"]


def test_only_cash_entries_remain_on_the_cash_concept():
    """After the follow-up, exactly 22 entries lead with the cash concept, all labelled as cash."""
    led_by_cash = {
        tag: entry["display_name"]
        for tag, entry in GAAP_MAPPINGS.items()
        if isinstance(entry, dict) and entry.get("standard_tags", [None])[0] == "CashAndMarketableSecurities"
    }
    assert len(led_by_cash) == 22
    assert set(led_by_cash.values()) == {"Cash and Cash Equivalents"}


# Allstate's FY2025 10-K. The schema, presentation and label linkbases and the instance (13.5 MB)
# render the balance sheet; the calculation and definition linkbases are not needed. Without the
# label linkbase the rendered frame comes back with empty value cells.
ALL_10K_FOLDER = "https://www.sec.gov/Archives/edgar/data/899051/000089905126000031/"
ALL_10K_XBRL_FILES = ("all-20251231.xsd", "all-20251231_pre.xml", "all-20251231_lab.xml", "all-20251231_htm.xml")


@pytest.mark.vcr
def test_allstate_total_investments_are_not_cash(tmp_path):
    """Allstate FY2025 10-K, 0000899051-26-000031, statement of financial position at 2025-12-31.

    Filed: Total investments $83,237M and Cash $678M. Both rows carried CashAndMarketableSecurities,
    so the cash group summed to $83,915M. The mixed total now has no standard concept, and its
    components keep theirs.
    """
    for name in ALL_10K_XBRL_FILES:
        (tmp_path / name).write_text(download_file(ALL_10K_FOLDER + name), encoding="utf-8")
    statement = XBRL.from_directory(tmp_path).statements["BalanceSheet"]
    assert statement is not None
    frame = statement.render(standard=True).to_dataframe()
    frame = frame[~frame["dimension"]]

    assert _rows(frame, "CashAndMarketableSecurities", "2025-12-31") == {"us-gaap_Cash": 678_000_000}
    total = frame[frame["concept"] == "us-gaap_Investments"]
    assert total["2025-12-31"].tolist() == [83_237_000_000]
    assert total["standard_concept"].isna().all()
    assert _rows(frame, "LongtermInvestments", "2025-12-31") == {
        "us-gaap_DebtSecuritiesAvailableForSaleExcludingAccruedInterest": 59_115_000_000,
        "us-gaap_OtherInvestments": 1_114_000_000,
    }
