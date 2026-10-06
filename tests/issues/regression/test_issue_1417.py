"""
Operating cash-flow lines were stored as the operating total, or as another
concept they are not. ``lookup()`` then labeled the detail row with that
concept. A null row means there is no fitting concept today, so ``lookup()``
returns ``None``.

This slice is the 67 operating rows. Later slices append rows to
``issue_1417_expected.json``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1435
GitHub Issue: https://github.com/dgunning/edgartools/issues/1417
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import get_reverse_index

EXPECTED = json.loads((Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1417_expected.json").read_text(encoding="utf-8"))
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))

# These 14 rows repeated the old concept in every industry override.
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
@pytest.mark.parametrize("industry", ["Banks", "BusSv", "Drugs", "Fin", "Insur", "Trans", "Hlth", "RlEst", "Oil"])
def test_no_industry_brings_the_old_concept_back(index, tag, industry):
    """The old answer was repeated in every industry override."""
    plain = index.lookup(tag)
    with_industry = index.lookup(tag, industry=industry)
    if plain is None:
        assert with_industry is None
    else:
        assert with_industry is not None
        assert with_industry.standard_concepts == plain.standard_concepts


def test_single_candidate_display_name_matches_the_catalog():
    """A stale display_name would still pass the concept check above."""
    for tag, concepts in EXPECTED.items():
        if not concepts or len(concepts) != 1:
            continue
        assert GAAP_MAPPINGS[tag]["display_name"] == DISPLAY_NAMES[concepts[0]], tag


def test_microsoft_cash_flow_has_one_operating_total():
    """Detail lines must not carry the operating total's concept."""
    fixture = Path(__file__).parents[2] / "fixtures" / "xbrl" / "msft" / "10k_2024"
    statement = XBRL.from_directory(fixture).statements["CashFlowStatement"]
    assert statement is not None
    frame = statement.render(standard=True).to_dataframe()
    assert int((frame["standard_concept"] == "NetCashFromOperatingActivities").sum()) == 1
