"""
Equity parts, dividends declared and share counts were mapped to totals or to
concepts they do not measure. CommonStockValue, the par value of common stock
used by 7,620 companies, resolved to CommonEquity, displayed as "Total
Stockholders' Equity", so a $694,000 par-value line read as the equity total on
Cato's balance sheet. Dividends declared resolved to the cash-flow concept
CommonDividendsPaid, and treasury share counts to the dollar concept
TreasuryShares.

The 39 rows follow the issue's table: 23 remap to the concept their FASB or
IFRS definition supports, and 16 with no fitting concept are removed.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1443
GitHub Issue: https://github.com/dgunning/edgartools/issues/1417
"""

import json
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.core import ConceptMapper, MappingStore, standardize_statement
from edgar.xbrl.standardization.exclusions import EXCLUDED_TAGS
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sections import get_section_for_concept, get_statement_for_concept
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES

EXPECTED = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "issue_1443_equity_expected.json").read_text(encoding="utf-8")
)
_STANDARDIZATION = Path(reverse_index_module.__file__).parent
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
FIXTURES = Path(__file__).parents[2] / "fixtures" / "xbrl"

# Pin the removals independently of the expected-mapping fixture.
DELETED_TAGS = {
    "CommonStockShareSubscribedButUnissuedSubscriptionsReceivable",
    "CommonStockValue",
    "CommonStockValueOutstanding",
    "DeferredCompensationEquity",
    "DividendsPayableAmountPerShare",
    "PreferredStockLiquidationPreferenceValue",
    "PreferredStockSharesIssued",
    "PreferredStockSharesOutstanding",
    "ReceivableFromOfficersAndDirectorsForIssuanceOfCapitalStock",
    "ReceivableFromShareholdersOrAffiliatesForIssuanceOfCapitalStock",
    "StockholdersEquityNoteSubscriptionsReceivable",
    "TreasuryStockCommonShares",
    "TreasuryStockDeferredEmployeeStockOwnershipPlan",
    "TreasuryStockShares",
    "UnearnedESOPShares",
    "AociIncludingPortionAttributableToNoncontrollingInterestTax",
}

INDUSTRIES = sorted({code for _, _, code in _FF48_SIC_RANGES})
STATEMENT_TYPES = ["BalanceSheet", "StatementOfEquity", "CashFlowStatement", ""]


def _tag(element):
    return element if element.startswith("ifrs-full_") else f"us-gaap:{element}"


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_expected_entries_are_the_issue_rows():
    assert len(EXPECTED) == 39
    assert {tag for tag, concepts in EXPECTED.items() if concepts is None} == DELETED_TAGS
    assert sum(concepts is not None for concepts in EXPECTED.values()) == 23
    assert len(INDUSTRIES) == 48


@pytest.mark.parametrize("tag", sorted(EXPECTED))
def test_corrected_entries(index, tag):
    expected = EXPECTED[tag]
    if expected is None:
        assert tag not in GAAP_MAPPINGS
    else:
        assert GAAP_MAPPINGS[tag]["standard_tags"] == expected
    result = index.lookup(_tag(tag))
    if expected is None:
        assert result is None
    else:
        assert result is not None
        assert result.standard_concepts == expected
        assert result.display_names == [DISPLAY_NAMES[expected[0]]]
        assert result.is_ambiguous is False


def test_only_preferred_share_counts_were_already_excluded():
    """Two removed rows were excluded before; the remapped ones must not be."""
    assert set(EXPECTED) & EXCLUDED_TAGS == {"PreferredStockSharesIssued", "PreferredStockSharesOutstanding"}


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("industry", INDUSTRIES)
def test_no_industry_brings_the_old_concept_back(index, tag, industry):
    expected = EXPECTED[tag]
    result = index.lookup(_tag(tag), industry=industry)
    if expected is None:
        assert result is None
    else:
        assert result is not None and result.standard_concepts == expected


def test_no_corrected_entry_keeps_an_industry_override():
    assert [tag for tag in EXPECTED if "industry_overrides" in GAAP_MAPPINGS.get(tag, {})] == []


@pytest.mark.parametrize(
    "tag", sorted(tag for tag, concepts in EXPECTED.items() if concepts and not tag.startswith("ifrs-full_"))
)
def test_corrected_entry_metadata_matches_its_concept(tag):
    concept = EXPECTED[tag][0]
    entry = GAAP_MAPPINGS[tag]
    statement = get_statement_for_concept(concept)
    assert entry["display_name"] == DISPLAY_NAMES[concept]
    assert entry["statement"] == statement
    assert entry["section"] == get_section_for_concept(concept, statement)
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9


@pytest.mark.parametrize("tag", sorted(EXPECTED))
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
def test_standardization_preserves_filed_data(mapper, tag, statement_type):
    item = {
        "concept": tag if tag.startswith("ifrs-full_") else f"us-gaap_{tag}",
        "label": "Filed disclosure label",
        "values": {"2023-12-31": 123_456},
        "statement_type": statement_type,
    }
    result = standardize_statement([item], mapper)
    assert len(result) == 1
    assert {key: value for key, value in result[0].items() if key != "standard_concept"} == item
    expected = EXPECTED[tag]
    if expected is None:
        assert "standard_concept" not in result[0]
    else:
        assert result[0]["standard_concept"] == expected[0]


def test_common_equity_no_longer_holds_parts_of_equity(index):
    members = {tag for tag, entry in index._index.items()
               if isinstance(entry, dict) and "CommonEquity" in entry.get("standard_tags", [])}
    assert not members & set(EXPECTED)


# --- statements from real filings ------------------------------------------------

def _frame(directory, statement):
    xbrl = XBRL.from_directory(FIXTURES / directory)
    frame = getattr(xbrl.statements, statement)().to_dataframe()
    return frame[~frame["dimension"]]


def test_cato_common_stock_is_not_labelled_total_equity():
    """Cato FY2023 10-K (0001562762-24-000065): common stock $694,000, total stockholders' equity $192,321,000 at Feb 3, 2024.

    The common stock row used to carry CommonEquity and the label "Total Stockholders' Equity", so the
    balance sheet showed two rows with that label.
    """
    frame = _frame("cato/10k_2023", "balance_sheet")
    common = frame[(frame["concept"] == "us-gaap_CommonStockValue") & (frame["label"] == "Common Stock")]
    assert len(common) == 1
    assert common["2024-02-03"].iloc[0] == 694_000
    assert common["standard_concept"].isna().all()

    totals = frame[frame["label"] == "Total Stockholders' Equity"]
    assert len(totals) == 1
    assert totals["concept"].iloc[0] == "us-gaap_StockholdersEquity"
    assert totals["2024-02-03"].iloc[0] == 192_321_000


def test_coca_cola_par_value_is_not_an_equity_total():
    """Coca-Cola FY2023 10-K (0000021344-24-000009): common stock $1,760M; equity attributable to shareowners $25,941M."""
    frame = _frame("ko/10k_2024", "balance_sheet")
    common = frame[frame["concept"] == "us-gaap_CommonStockValue"]
    assert set(common["2023-12-31"]) == {1_760_000_000}
    assert common["standard_concept"].isna().all()
    assert "CommonEquity" not in set(frame["standard_concept"].dropna())
    equity = frame[frame["standard_concept"] == "AllEquityBalance"]
    assert list(equity["2023-12-31"]) == [25_941_000_000]


def test_microsoft_dividends_declared_are_an_equity_change():
    """Microsoft FY2024 10-K (0000950170-24-087843): common stock cash dividends $22,296M on the statement of equity."""
    frame = _frame("msft/10k_2024", "statement_of_equity")
    dividends = frame[frame["concept"] == "us-gaap_DividendsCommonStockCash"]
    assert len(dividends) == 1
    assert dividends["2024-06-30 (FY)"].iloc[0] == 22_296_000_000
    assert dividends["standard_concept"].iloc[0] == "DividendsEquity"


def test_netflix_treasury_stock_value_is_treasury_shares():
    """Netflix FY2023 10-K (0001065280-24-000030): treasury stock at cost $6,922.2M at Dec 31, 2023 (was unmapped)."""
    frame = _frame("nflx/10k_2024", "balance_sheet")
    treasury = frame[frame["concept"] == "us-gaap_TreasuryStockCommonValue"]
    assert len(treasury) == 1
    assert treasury["2023-12-31"].iloc[0] == -6_922_200_000
    assert treasury["standard_concept"].iloc[0] == "TreasuryShares"
