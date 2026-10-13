"""
Investing and financing cash-flow lines carried their section total's concept.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1435

``gaap_mappings.json`` mapped 75 investing and financing tags (dividends paid,
debt proceeds and repayments, investment purchases and proceeds, the "Other"
residual lines, discontinued-operations subtotals, and a few equity-statement
and noncash elements) to ``NetCashFromInvestingActivities``,
``NetCashFromFinancingActivities`` or ``NetChangeInCash``, and 27 of them
repeated that answer in every industry override. A standardized cash flow then
had two to five rows under one section-total concept. On Apple's FY2023 10-K
(accession 0000320193-23-000106) the investing "Other" line, $(1,337)M, sat
beside the $3,705M total, so grouping the statement by ``standard_concept``
gave $2,368M of investing cash; the financing "Other" line, $(581)M, made
financing $(109,069)M instead of $(108,488)M.

The expected table lists each corrected tag's concepts. ``null`` means no
standard concept fits today: the entry is deleted and ``lookup()`` returns
``None``. ``PaymentsRelatedToTaxWithholdingForShareBasedCompensation`` is also
in ``exclusions.py``, so ``lookup()`` returned ``None`` before the fix too; its
deletion is checked in the loaded mappings. The row-by-row rationale is in
https://github.com/dgunning/edgartools/issues/1417#issuecomment-6014320363.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES

_FIXTURES = Path(__file__).parents[2] / "fixtures"
EXPECTED = json.loads((_FIXTURES / "standardization" / "issue_1435_investing_financing_expected.json").read_text(encoding="utf-8"))
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
FAMA_FRENCH_48 = sorted({code for _, _, code in _FF48_SIC_RANGES})

# These 27 rows repeated the old concept in every industry override, 46 codes in all.
HAD_OVERRIDES = [
    "CashAcquiredFromAcquisition",
    "CashProvidedByUsedInFinancingActivitiesDiscontinuedOperations",
    "CashProvidedByUsedInInvestingActivitiesDiscontinuedOperations",
    "PaymentsForProceedsFromInvestments",
    "PaymentsForProceedsFromLoansReceivable",
    "PaymentsForProceedsFromOtherInvestingActivities",
    "PaymentsForProceedsFromProductiveAssets",
    "PaymentsOfDividendsCommonStock",
    "PaymentsOfOrdinaryDividends",
    "PaymentsToAcquireLoansReceivable",
    "PaymentsToAcquireMachineryAndEquipment",
    "ProceedsFromContributionsFromParent",
    "ProceedsFromDebtNetOfIssuanceCosts",
    "ProceedsFromIssuanceInitialPublicOffering",
    "ProceedsFromIssuanceOfPrivatePlacement",
    "ProceedsFromPaymentsForOtherFinancingActivities",
    "ProceedsFromPaymentsToMinorityShareholders",
    "ProceedsFromRepaymentsOfLinesOfCredit",
    "ProceedsFromRepaymentsOfOtherDebt",
    "ProceedsFromRepaymentsOfRelatedPartyDebt",
    "ProceedsFromRepaymentsOfShortTermDebt",
    "ProceedsFromSaleAndMaturityOfOtherInvestments",
    "ProceedsFromSaleMaturityAndCollectionsOfInvestments",
    "ProceedsFromSaleOfEquityMethodInvestments",
    "ProceedsFromSaleOfRealEstateHeldforinvestment",
    "ProceedsFromSalesOfBusinessAffiliateAndProductiveAssets",
    "StockIssuedDuringPeriodSharesAcquisitions",
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
        assert tag not in index._gaap_mappings
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
    """A stale display_name would rename the concept everywhere and still pass the table."""
    for tag, concepts in EXPECTED.items():
        if concepts and len(concepts) == 1:
            assert GAAP_MAPPINGS[tag]["display_name"] == DISPLAY_NAMES[concepts[0]], tag


def test_apple_section_totals_match_the_filing():
    """Apple FY2023 10-K (0000320193-23-000106), values checked against the filed cash flow statement."""
    statement = XBRL.from_directory(_FIXTURES / "xbrl" / "aapl" / "10k_2023").statements["CashFlowStatement"]
    assert statement is not None
    frame = statement.render(standard=True).to_dataframe()
    totals = frame.groupby("standard_concept")["2023-09-30"].sum()
    assert totals["NetCashFromInvestingActivities"] == 3_705_000_000
    assert totals["NetCashFromFinancingActivities"] == -108_488_000_000
    rows = frame.set_index("concept")
    other_investing = rows.loc["us-gaap_PaymentsForProceedsFromOtherInvestingActivities"]
    assert other_investing["2023-09-30"] == -1_337_000_000
    assert pd.isna(other_investing["standard_concept"])
    other_financing = rows.loc["us-gaap_ProceedsFromPaymentsForOtherFinancingActivities"]
    assert other_financing["2023-09-30"] == -581_000_000
    assert pd.isna(other_financing["standard_concept"])
