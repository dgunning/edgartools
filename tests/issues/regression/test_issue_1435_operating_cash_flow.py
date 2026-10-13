"""
Operating cash-flow tags standardized as the operating total, or as another
concept they are not.

61 of these 67 tags mapped to ``NetCashFromOperatingActivities`` in
``gaap_mappings.json``, so ``ReverseIndex.lookup()`` gave a detail row the
section total's concept. Microsoft's FY2024 10-K (0000950170-24-087843) had
three operating rows with that concept, not one. Where a fact has only a
standard-role label, the Facts API replaces it with the display name, so a
detail fact read "Net Cash from Operating Activities".

The other 6 mapped to other wrong concepts: on Apple's FY2023 10-K
(0000320193-23-000106), dividends paid of $15,025M were
``DistributionsToMinorityInterests`` and share-based compensation of $10,833M
was the income-statement ``StockBasedCompensationExpense``.

``issue_1435_operating_cash_flow_expected.json`` holds the corrected concepts.
A null row means there is no fitting concept today, so ``lookup()`` returns
``None``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1435
GitHub Issue: https://github.com/dgunning/edgartools/issues/1417
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES

FIXTURES = Path(__file__).parents[2] / "fixtures"
EXPECTED = json.loads((FIXTURES / "standardization" / "issue_1435_operating_cash_flow_expected.json").read_text(encoding="utf-8"))
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
FAMA_FRENCH_48 = sorted({code for _, _, code in _FF48_SIC_RANGES})

# These 14 rows repeated the old concept in industry overrides, 47 codes in all.
HAD_OVERRIDES = [
    "CashProvidedByUsedInOperatingActivitiesDiscontinuedOperations",
    "FairValueOfAssetsAcquired",
    "GainLossOnSalesOfLoansNet",
    "IncreaseDecreaseInContractWithCustomerAsset",
    "IncreaseDecreaseInDeferredIncomeTaxes",
    "IncreaseDecreaseInInterestPayableNet",
    "NoncashOrPartNoncashAcquisitionFixedAssetsAcquired1",
    "OtherNoncashExpense",
    "OtherOperatingActivitiesCashFlowStatement",
    "PaymentsOfDividends",
    "ProceedsFromSaleOfMortgageLoansHeldForSale",
    "RightOfUseAssetObtainedInExchangeForOperatingLeaseLiability",
    "ShareBasedCompensation",
    "StockGrantedDuringPeriodValueSharebasedCompensation",
]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_corrected_entries(index, tag):
    expected = EXPECTED[tag]
    result = index.lookup(tag)
    if expected is None:
        assert result is None
    else:
        assert result is not None and result.standard_concepts == expected


@pytest.mark.parametrize("tag", HAD_OVERRIDES)
def test_no_industry_brings_the_old_concept_back(index, tag):
    """The old answer was repeated in industry overrides; every industry must now agree with the plain lookup."""
    assert len(FAMA_FRENCH_48) == 48
    plain = index.lookup(tag)
    expected = None if plain is None else plain.standard_concepts
    disagree = {}
    for industry in FAMA_FRENCH_48:
        with_industry = index.lookup(tag, industry=industry)
        got = None if with_industry is None else with_industry.standard_concepts
        if got != expected:
            disagree[industry] = got
    assert disagree == {}


def test_single_candidate_display_name_matches_the_catalog():
    """A stale display_name would still pass the concept check above."""
    for tag, concepts in EXPECTED.items():
        if not concepts or len(concepts) != 1:
            continue
        assert GAAP_MAPPINGS[tag]["display_name"] == DISPLAY_NAMES[concepts[0]], tag


def _xbrl(fixture):
    return XBRL.from_directory(FIXTURES / "xbrl" / fixture)


def _standardized_cash_flow(fixture):
    statement = _xbrl(fixture).statements["CashFlowStatement"]
    assert statement is not None
    return statement.render(standard=True).to_dataframe()


def test_microsoft_cash_flow_has_one_operating_total():
    """Microsoft FY2024 10-K (0000950170-24-087843), values checked against the filed cash flow statement."""
    frame = _standardized_cash_flow("msft/10k_2024")
    operating_total = frame[frame["standard_concept"] == "NetCashFromOperatingActivities"]
    assert operating_total["concept"].tolist() == ["us-gaap_NetCashProvidedByUsedInOperatingActivities"]
    rows = frame.set_index("concept")
    other_assets = rows.loc["us-gaap_IncreaseDecreaseInOtherNoncurrentAssets"]
    assert other_assets["2024-06-30"] == -6_817_000_000
    assert other_assets["standard_concept"] == "ChangeInOtherWorkingCapital"
    other_liabilities = rows.loc["us-gaap_IncreaseDecreaseInOtherNoncurrentLiabilities"]
    assert other_liabilities["2024-06-30"] == 749_000_000
    assert other_liabilities["standard_concept"] == "ChangeInOtherWorkingCapital"


def test_apple_fy2023_dividends_and_share_based_compensation():
    """Apple FY2023 10-K (0000320193-23-000106), values checked against the filed cash flow statement."""
    rows = _standardized_cash_flow("aapl/10k_2023").set_index("concept")
    dividends = rows.loc["us-gaap_PaymentsOfDividends"]
    assert dividends["2023-09-30"] == -15_025_000_000
    assert dividends["standard_concept"] == "CommonDividendsPaid"
    share_based = rows.loc["us-gaap_ShareBasedCompensation"]
    assert share_based["2023-09-30"] == 10_833_000_000
    assert share_based["standard_concept"] == "StockBasedCompensationCF"


def test_auburn_facts_are_not_labeled_as_the_operating_total():
    """Auburn National Bancorporation FY2023 10-K (0001193125-24-067944).

    Both facts have only standard-role labels ("Mortgage lending", "Proceeds
    from sale of loans"), and the Facts API shows the mapped display name in
    place of such a label. Both facts used to be labeled "Net Cash from
    Operating Activities". The second tag has no fitting concept now, so the
    filer's own label shows.
    """
    facts = _xbrl("aubn/10k_2023").facts.to_dataframe()
    fy2023 = facts[facts["period_end"] == "2023-12-31"].set_index("concept")
    gain_on_loans = fy2023.loc["us-gaap:GainLossOnSalesOfLoansNet"]
    assert gain_on_loans["numeric_value"] == 430_000
    assert gain_on_loans["label"] == "Gain/Loss on Asset Sales (CF)"
    loans_sold = fy2023.loc["us-gaap:ProceedsFromSaleOfMortgageLoansHeldForSale"]
    assert loans_sold["numeric_value"] == 4_174_000
    assert loans_sold["label"] == "Proceeds from sale of loans"
