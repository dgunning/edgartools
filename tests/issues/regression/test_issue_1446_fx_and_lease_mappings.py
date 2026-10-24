"""
Two user-visible items from the mapping clean-up issue.

The IFRS exchange-rate effect on cash (``EffectOfExchangeRateChangesOnCashAndCashEquivalents``,
683 companies, bare and ``ifrs-full_`` keys) was standardized as "Net Change in Cash", while
the us-gaap ``EffectOfExchangeRateOn*`` elements are "Effect of Exchange Rate on Cash". On
Opera's FY2025 20-F the $1,944K exchange-rate row was the only ``NetChangeInCash`` row, beside
a filed net change of $26,724K. Both keys now take ``ForeignExchangeEffectOnCash``, so the
row no longer passes for the net change.

The operating-lease commitment concepts were fed only by the superseded ASC 840
``OperatingLeasesFutureMinimumPaymentsDue*`` elements (13 filers in SEC's CY2024Q4I frame).
The six ASC 842 lessee maturity elements that correspond one to one (next twelve months,
years two to five, after year five; 2,589 to 3,762 filers each) now feed the same concepts.
Finance-lease and lessor maturity elements, the remainder-of-year bucket, the rolling
variants and the undiscounted total have no matching concept and stay unmapped.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1446
"""

import json
from pathlib import Path

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import get_reverse_index

EXPECTED = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1446_fx_and_lease_mappings_expected.json").read_text(
        encoding="utf-8"
    )
)
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

# Each ASC 842 lessee element and the ASC 840 element whose concept it takes.
ASC_840_COUNTERPART = {
    "LesseeOperatingLeaseLiabilityPaymentsDueNextTwelveMonths": "OperatingLeasesFutureMinimumPaymentsDueCurrent",
    "LesseeOperatingLeaseLiabilityPaymentsDueYearTwo": "OperatingLeasesFutureMinimumPaymentsDueInTwoYears",
    "LesseeOperatingLeaseLiabilityPaymentsDueYearThree": "OperatingLeasesFutureMinimumPaymentsDueInThreeYears",
    "LesseeOperatingLeaseLiabilityPaymentsDueYearFour": "OperatingLeasesFutureMinimumPaymentsDueInFourYears",
    "LesseeOperatingLeaseLiabilityPaymentsDueYearFive": "OperatingLeasesFutureMinimumPaymentsDueInFiveYears",
    "LesseeOperatingLeaseLiabilityPaymentsDueAfterYearFive": "OperatingLeasesFutureMinimumPaymentsDueThereafter",
}
FX_TAGS = ["EffectOfExchangeRateChangesOnCashAndCashEquivalents", "ifrs-full_EffectOfExchangeRateChangesOnCashAndCashEquivalents"]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


def test_expected_file_covers_the_changed_keys():
    assert set(EXPECTED) == set(FX_TAGS) | set(ASC_840_COUNTERPART)
    assert len(EXPECTED) == 8


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_corrected_entries(index, tag):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == EXPECTED[tag]
    assert result.display_names == [DISPLAY_NAMES[concept] for concept in EXPECTED[tag]]
    assert result.is_ambiguous is False
    assert "industry_overrides" not in GAAP_MAPPINGS[tag]


@pytest.mark.parametrize(
    "tag",
    [
        "ifrs-full:EffectOfExchangeRateChangesOnCashAndCashEquivalents",
        "ifrs:EffectOfExchangeRateChangesOnCashAndCashEquivalents",
        "EffectOfExchangeRateChangesOnCashAndCashEquivalents",
        "us-gaap:EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
)
def test_every_spelling_of_the_exchange_rate_effect_is_the_fx_concept(index, tag):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == ["ForeignExchangeEffectOnCash"]
    assert result.display_names == ["Effect of Exchange Rate on Cash"]


@pytest.mark.parametrize(
    "tag",
    [
        "ifrs-full:IncreaseDecreaseInCashAndCashEquivalents",
        "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
    ],
)
def test_the_net_change_keeps_its_concept(index, tag):
    """The real net-change totals still resolve to NetChangeInCash; only the FX row left it."""
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == ["NetChangeInCash"]
    assert result.display_names == ["Net Change in Cash"]


def test_remapped_fx_entry_metadata_matches_the_us_gaap_fx_entries():
    entry = GAAP_MAPPINGS["EffectOfExchangeRateChangesOnCashAndCashEquivalents"]
    sibling = GAAP_MAPPINGS["EffectOfExchangeRateOnCashAndCashEquivalents"]
    for field in ("display_name", "statement", "section", "is_total"):
        assert entry[field] == sibling[field], field
    assert entry["display_name"] == "Effect of Exchange Rate on Cash"
    assert entry["section"] == "Cash Flow Totals"
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    # The ifrs-full_ key keeps the shape of every other ifrs-full_ entry.
    assert GAAP_MAPPINGS["ifrs-full_EffectOfExchangeRateChangesOnCashAndCashEquivalents"] == {
        "standard_tags": ["ForeignExchangeEffectOnCash"]
    }


@pytest.mark.parametrize("tag", sorted(ASC_840_COUNTERPART))
def test_asc_842_element_takes_its_asc_840_counterparts_concept(index, tag):
    entry = GAAP_MAPPINGS[tag]
    counterpart = GAAP_MAPPINGS[ASC_840_COUNTERPART[tag]]
    assert entry["standard_tags"] == counterpart["standard_tags"]
    for field in ("display_name", "statement", "section"):
        assert entry[field] == counterpart[field], field
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    assert index.lookup(f"us-gaap:{tag}") == index.lookup(tag)


@pytest.mark.parametrize(
    "tag",
    [
        "LesseeOperatingLeaseLiabilityPaymentsDue",
        "LesseeOperatingLeaseLiabilityPaymentsRemainderOfFiscalYear",
        "LesseeOperatingLeaseLiabilityPaymentsDueNextRollingTwelveMonths",
        "LesseeOperatingLeaseLiabilityUndiscountedExcessAmount",
        "FinanceLeaseLiabilityPaymentsDueNextTwelveMonths",
        "FinanceLeaseLiabilityPaymentsDueAfterYearFive",
        "LessorOperatingLeasePaymentsToBeReceivedNextTwelveMonths",
        "LessorOperatingLeasePaymentsToBeReceivedThereafter",
    ],
)
def test_lease_elements_without_a_matching_concept_stay_unmapped(index, tag):
    """No finance-lease, lessor, remainder-of-year or total commitment concept exists."""
    assert index.lookup(tag) is None


def test_no_other_concept_label_changed(index):
    assert index.concept_to_display_name("NetChangeInCash") == "Net Change in Cash"
    assert index.concept_to_display_name("ForeignExchangeEffectOnCash") == "Effect of Exchange Rate on Cash"
    for concept in ("Year1", "Year2", "Year3", "Year4", "Year5", "AfterYear5"):
        name = f"OperatingLeaseCommitment{concept}"
        assert index.concept_to_display_name(name) == DISPLAY_NAMES[name]


def _rows(frame, standard_concept, column):
    selected = frame[frame["standard_concept"] == standard_concept]
    return dict(zip(selected["concept"], selected[column], strict=True))


def _statement_frame(tmp_path, folder, names, statement):
    for name in names:
        (tmp_path / name).write_text(download_file(folder + name), encoding="utf-8")
    rendered = XBRL.from_directory(tmp_path).statements[statement]
    assert rendered is not None
    frame = rendered.render(standard=True).to_dataframe()
    return frame[~frame["dimension"]]


# Opera's FY2025 20-F (IFRS). The schema embeds the presentation and label linkbases.
OPRA_20F_FOLDER = "https://www.sec.gov/Archives/edgar/data/1737450/000173745026000005/"
OPRA_20F_XBRL_FILES = ("opra-20251231.xsd", "opra-20251231_htm.xml")


@pytest.mark.vcr
def test_opera_exchange_rate_effect_is_not_the_net_change_in_cash(tmp_path):
    """Opera Ltd FY2025 20-F, 0001737450-26-000005, cash flow statement.

    Filed: net change in cash and cash equivalents $26,724K (before the exchange-rate effect),
    effect of exchange rate changes $1,944K ($-2,785K in 2024), cash at end of period
    $155,466K. The $1,944K row was the statement's only "Net Change in Cash".
    """
    frame = _statement_frame(tmp_path, OPRA_20F_FOLDER, OPRA_20F_XBRL_FILES, "CashFlowStatement")

    fx = "ifrs-full_EffectOfExchangeRateChangesOnCashAndCashEquivalents"
    assert _rows(frame, "ForeignExchangeEffectOnCash", "2025-12-31") == {fx: 1_944_000}
    assert _rows(frame, "ForeignExchangeEffectOnCash", "2024-12-31") == {fx: -2_785_000}
    assert fx not in _rows(frame, "NetChangeInCash", "2025-12-31")
    before = frame[frame["concept"] == "ifrs-full_IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges"]
    assert before["2025-12-31"].tolist() == [26_724_000]


# FreightCar America's FY2025 10-K (US GAAP, ASC 842 lessee).
RAIL_10K_FOLDER = "https://www.sec.gov/Archives/edgar/data/1320854/000119312526098668/"
RAIL_10K_XBRL_FILES = ("rail-20251231.xsd", "rail-20251231_htm.xml")
RAIL_LEASE_ROLE = "http://www.freightcaramerica.com/20251231/taxonomy/role/DisclosureLeasesAggregateFutureOperatingLeasePaymentsDetails"


@pytest.mark.vcr
def test_freightcar_operating_lease_maturities_are_commitments(tmp_path):
    """FreightCar America FY2025 10-K, 0001193125-26-098668, Leases (Aggregate Future
    Operating Lease Payments) at 2025-12-31.

    Filed: 2026 $6,609K, 2027 $6,436K, 2028 $6,263K, 2029 $5,800K, 2030 $5,890K,
    thereafter $58,960K, total lease payments $89,958K. None had a standard concept.
    """
    frame = _statement_frame(tmp_path, RAIL_10K_FOLDER, RAIL_10K_XBRL_FILES, RAIL_LEASE_ROLE)

    expected = {
        "OperatingLeaseCommitmentYear1": ("us-gaap_LesseeOperatingLeaseLiabilityPaymentsDueNextTwelveMonths", 6_609_000),
        "OperatingLeaseCommitmentYear2": ("us-gaap_LesseeOperatingLeaseLiabilityPaymentsDueYearTwo", 6_436_000),
        "OperatingLeaseCommitmentYear3": ("us-gaap_LesseeOperatingLeaseLiabilityPaymentsDueYearThree", 6_263_000),
        "OperatingLeaseCommitmentYear4": ("us-gaap_LesseeOperatingLeaseLiabilityPaymentsDueYearFour", 5_800_000),
        "OperatingLeaseCommitmentYear5": ("us-gaap_LesseeOperatingLeaseLiabilityPaymentsDueYearFive", 5_890_000),
        "OperatingLeaseCommitmentAfterYear5": ("us-gaap_LesseeOperatingLeaseLiabilityPaymentsDueAfterYearFive", 58_960_000),
    }
    for concept, (element, value) in expected.items():
        assert _rows(frame, concept, "2025-12-31") == {element: value}, concept
    total = frame[frame["concept"] == "us-gaap_LesseeOperatingLeaseLiabilityPaymentsDue"]
    assert total["2025-12-31"].tolist() == [89_958_000]
    assert total["standard_concept"].isna().all()
