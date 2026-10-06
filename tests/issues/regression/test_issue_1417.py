"""
Assets held for sale, contract assets, restricted cash and receivable allowances were filed under
catch-all "Other" buckets or under the wrong receivable concept. ``lookup()`` then showed a
disposal group's cash, goodwill and inventory, and every held-for-sale loan category, as "Other
Non-Operating Current Assets", and contract assets as "Other Operating Current Assets". IBM's
FY2024 balance sheet put $900 million of short-term financing receivables held for sale in that
bucket.

This slice is the 51 rows of #1438 PR-6a (49 distinct elements; two elements have two rows each).
A null row is a deleted entry: no concept fits, so ``lookup()`` returns ``None``. Later slices
append rows to ``issue_1417_expected.json``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1438
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

# These 7 rows repeated the old concept in every industry override.
HAD_OVERRIDES = [
    "AccountsReceivableRelatedPartiesCurrent",
    "AssetsHeldForSaleNotPartOfDisposalGroup",
    "ContractWithCustomerAssetNetCurrent",
    "ContractWithCustomerAssetNetNoncurrent",
    "LoansReceivableHeldForSaleNetNotPartOfDisposalGroup",
    "RestrictedCashAndCashEquivalentsNoncurrent",
    "RestrictedCashEquivalentsCurrent",
]


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


def _members(index, concept):
    return {tag for tag, entry in index._index.items() if isinstance(entry, dict) and concept in entry.get("standard_tags", [])}


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


def test_no_corrected_entry_keeps_an_industry_override():
    """The guard above samples nine industries; an override left in any other would hide there."""
    assert [tag for tag in EXPECTED if "industry_overrides" in GAAP_MAPPINGS.get(tag, {})] == []


def test_single_candidate_display_name_matches_the_catalog():
    """A stale display_name would still pass the concept check above."""
    for tag, concepts in EXPECTED.items():
        if not concepts or len(concepts) != 1:
            continue
        assert GAAP_MAPPINGS[tag]["display_name"] == DISPLAY_NAMES[concepts[0]], tag


@pytest.mark.parametrize(
    "tag, concept, display",
    [
        ("AssetsHeldForSaleNotPartOfDisposalGroup", "AssetsHeldForSale", "Assets Held for Sale"),
        ("DisposalGroupIncludingDiscontinuedOperationGoodwillCurrent", "AssetsHeldForSale", "Assets Held for Sale"),
        ("LoansHeldForSaleMortgages", "AssetsHeldForSale", "Assets Held for Sale"),
        ("ContractWithCustomerAssetNetCurrent", "ContractAssets", "Contract Assets"),
        ("ContractWithCustomerAssetNetNoncurrent", "ContractAssets", "Contract Assets"),
        ("RestrictedCashEquivalentsCurrent", "RestrictedCashCurrent", "Restricted Cash, Current"),
        ("RestrictedCashEquivalentsNoncurrent", "RestrictedCashNonCurrent", "Restricted Cash, Non-Current"),
        ("AllowanceForNotesAndLoansReceivableCurrent", "AllowanceForDoubtfulAccounts", "Allowance for Doubtful Accounts"),
        ("AllowanceForNotesAndLoansReceivableNoncurrent", "LoanLossReserve", "Allowance for Loan and Lease Losses"),
        ("NotesAndLoansReceivableGrossNoncurrent", "NotesReceivableNonCurrent", "Notes Receivable, Non-Current"),
        ("ContractReceivableRetainageDueOneYearOrLess", "TradeReceivables", "Accounts Receivable"),
    ],
)
def test_concept_follows_the_element_definition(index, tag, concept, display):
    result = index.lookup(tag)
    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]


def test_pledged_finance_receivables_have_no_standard_concept(index):
    """Receivables pledged as collateral are a disclosure about how an asset is encumbered, not trade receivables."""
    assert index.lookup("PledgedAssetsSeparatelyReportedFinanceReceivablesPledgedAsCollateralAtFairValue") is None


def test_held_for_sale_is_not_filed_as_other_current_assets(index):
    """Every element named for a held-for-sale loan category or disposal group left the other-assets bucket."""
    other = _members(index, "OtherNonOperatingCurrentAssets")
    held = {tag for tag in EXPECTED if EXPECTED[tag] == ["AssetsHeldForSale"]}
    assert len(held) == 28
    assert held.isdisjoint(other)
    assert held <= _members(index, "AssetsHeldForSale")


@pytest.fixture(scope="module")
def ibm_fy2024():
    return XBRL.from_directory(Path(__file__).parents[2] / "fixtures" / "xbrl" / "ibm" / "10k_2024")


def test_ibm_receivables_held_for_sale_are_assets_held_for_sale(ibm_fy2024):
    """IBM FY2024 10-K, 0000051143-25-000015: "Held for sale" under short-term financing receivables, $900M (2023: $692M)."""
    frame = ibm_fy2024.statements["BalanceSheet"].render(standard=True).to_dataframe()
    rows = frame[(frame["concept"] == "us-gaap_TradeAndLoansReceivablesHeldForSaleNetNotPartOfDisposalGroup") & ~frame["dimension"]]
    assert len(rows) == 1
    assert rows["2024-12-31"].iloc[0] == 900_000_000
    assert rows["2023-12-31"].iloc[0] == 692_000_000
    assert rows["standard_concept"].iloc[0] == "AssetsHeldForSale"
