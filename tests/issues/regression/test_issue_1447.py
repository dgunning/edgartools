"""
Standard concepts for crypto assets at fair value (ASU 2023-08).

None of the crypto elements FASB added in the 2024 taxonomy had a standard concept, so
``lookup()`` returned ``None`` and Tesla's FY2025 "Digital assets" row ($1,008M,
``CryptoAssetFairValueNoncurrent``) carried no concept. EntityFacts gave the elements no
statement either, so the line was missing from Tesla's and Strategy's EntityFacts balance
sheets.

Eight monetary elements now map one to one to eight new concepts:

=================================================================  ==========================
Element (us-gaap)                                                  Standard concept
=================================================================  ==========================
CryptoAssetFairValue                                               CryptoAssets
CryptoAssetFairValueCurrent                                        CryptoAssetsCurrent
CryptoAssetFairValueNoncurrent                                     CryptoAssetsNoncurrent
CryptoAssetUnrealizedGainLossOperatingAndNonoperating              CryptoUnrealizedGainLoss
CryptoAssetRealizedAndUnrealizedGainLossOperatingAndNonoperating   CryptoGainLoss
PaymentForAcquisitionCryptoAsset                                   CryptoPurchases
ProceedsFromDisposalCryptoAsset                                    CryptoSaleProceeds
ProceedsFromCryptoAssetOperatingActivity                           CryptoConversionProceeds
=================================================================  ==========================

Every one of the eight FASB definitions excludes crypto held for platform users, and so does
each mapping's definition. The total, current and noncurrent balances stay three concepts
even when the values are equal (Tesla files $1,008M for both the total and the noncurrent
balance), and unrealized is not an alias of realized-and-unrealized.

Ground truth, read from SEC:
- Tesla FY2025 10-K, 0001628280-26-003952: Digital assets $1,008M (2025-12-31) and $1,076M
  (2024-12-31) on the balance sheet (R3); unrealized gain (loss) $-68M (2025) and $589M (2024).
- Strategy FY2025 10-K, 0001050446-26-000020: Digital assets $58,854,028K (R3, tagged
  CryptoAssetFairValue); Purchases of digital assets $(22,467,083)K in investing (R8).
- Canaan FY2025 20-F, 0001104659-26-043786: change in fair value of cryptocurrency
  $-11,428K in operating cash flows, filed under both the unrealized and the
  realized-and-unrealized element; Cryptocurrency $83,339K noncurrent.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1447
"""

import json
from pathlib import Path

import pytest

from edgar.entity.mappings_loader import get_primary_statement, load_virtual_trees
from edgar.httprequests import download_file
from edgar.standardization import SynonymGroups
from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sections import get_section_membership

_STANDARDIZATION = Path(reverse_index_module.__file__).parent
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
DISPLAY_NAMES = json.loads((_STANDARDIZATION / "display_names.json").read_text(encoding="utf-8"))

# element -> (concept, display name, statement, section)
CRYPTO = {
    "CryptoAssetFairValue": ("CryptoAssets", "Crypto Assets", "BalanceSheet", None),
    "CryptoAssetFairValueCurrent": ("CryptoAssetsCurrent", "Crypto Assets, Current", "BalanceSheet", "Current Assets"),
    "CryptoAssetFairValueNoncurrent": (
        "CryptoAssetsNoncurrent", "Crypto Assets, Noncurrent", "BalanceSheet", "Non-Current Assets"),
    "CryptoAssetUnrealizedGainLossOperatingAndNonoperating": (
        "CryptoUnrealizedGainLoss", "Crypto Assets, Unrealized Gain (Loss)", "IncomeStatement", None),
    "CryptoAssetRealizedAndUnrealizedGainLossOperatingAndNonoperating": (
        "CryptoGainLoss", "Crypto Assets, Realized and Unrealized Gain (Loss)", "IncomeStatement", None),
    "PaymentForAcquisitionCryptoAsset": (
        "CryptoPurchases", "Payments to Acquire Crypto Assets", "CashFlowStatement", "Investing Activities"),
    "ProceedsFromDisposalCryptoAsset": (
        "CryptoSaleProceeds", "Proceeds from Disposal of Crypto Assets", "CashFlowStatement", "Investing Activities"),
    "ProceedsFromCryptoAssetOperatingActivity": (
        "CryptoConversionProceeds", "Proceeds from Conversion of Crypto Consideration", "CashFlowStatement",
        "Operating Activities"),
}


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


# ---------------------------------------------------------------------------
# Lookups (offline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("element", sorted(CRYPTO))
@pytest.mark.parametrize("spelling", ["us-gaap:{}", "us-gaap_{}", "{}"])
def test_each_element_maps_to_its_own_concept(index, element, spelling):
    concept, display, _, _ = CRYPTO[element]
    result = index.lookup(spelling.format(element))

    assert result is not None
    assert result.standard_concepts == [concept]
    assert result.display_names == [display]
    assert result.is_ambiguous is False
    assert index.concept_to_display_name(concept) == display
    assert DISPLAY_NAMES[concept] == display


@pytest.mark.parametrize("element", sorted(CRYPTO))
def test_every_definition_excludes_platform_user_holdings(index, element):
    comment = index.lookup(f"us-gaap:{element}").comment
    assert comment.endswith("Excludes crypto assets held for platform users.")


def test_conversion_proceeds_are_the_near_immediate_conversion_of_ordinary_course_consideration(index):
    comment = index.lookup("us-gaap:ProceedsFromCryptoAssetOperatingActivity").comment
    assert "nearly immediate conversion" in comment
    assert "noncash consideration in the ordinary course of business" in comment


@pytest.mark.parametrize("element", sorted(CRYPTO))
def test_entry_shape_follows_the_hand_added_convention(element):
    concept, display, statement, section = CRYPTO[element]
    entry = GAAP_MAPPINGS[element]

    assert entry["standard_tags"] == [concept]
    assert entry["display_name"] == display
    assert entry["statement"] == statement
    assert entry["section"] == section
    assert entry["is_total"] is False
    assert entry["confidence"] == 0.9
    assert entry["company_count"] > 0
    # No invented generation statistics.
    for stat in ("occurrence_rate", "temporal_consistency", "years_present", "first_year", "last_year"):
        assert stat not in entry


def test_section_membership():
    sections = get_section_membership()
    for concept, _, statement, section in CRYPTO.values():
        assert sections.get_section(concept, statement) == section, concept
    assert sections.is_current("CryptoAssetsCurrent") is True
    assert sections.is_current("CryptoAssetsNoncurrent") is False
    assert sections.is_asset("CryptoAssetsNoncurrent") is True
    # The total carries no classification, so it claims neither side.
    assert sections.is_current("CryptoAssets") is None


# ---------------------------------------------------------------------------
# Distinctness (offline)
# ---------------------------------------------------------------------------

def test_eight_elements_eight_concepts(index):
    concepts = [index.lookup(f"us-gaap:{element}").primary_concept for element in CRYPTO]
    assert len(set(concepts)) == 8
    displays = [index.lookup(f"us-gaap:{element}").primary_display_name for element in CRYPTO]
    assert len(set(displays)) == 8


def test_total_current_and_noncurrent_stay_apart(index):
    total = index.lookup("CryptoAssetFairValue").standard_concepts
    current = index.lookup("CryptoAssetFairValueCurrent").standard_concepts
    noncurrent = index.lookup("CryptoAssetFairValueNoncurrent").standard_concepts
    assert total == ["CryptoAssets"]
    assert current == ["CryptoAssetsCurrent"]
    assert noncurrent == ["CryptoAssetsNoncurrent"]


def test_unrealized_is_not_an_alias_of_realized_and_unrealized(index):
    assert index.lookup("CryptoAssetUnrealizedGainLossOperatingAndNonoperating").standard_concepts == [
        "CryptoUnrealizedGainLoss"]
    assert index.lookup("CryptoAssetRealizedAndUnrealizedGainLossOperatingAndNonoperating").standard_concepts == [
        "CryptoGainLoss"]


@pytest.mark.parametrize("element, context", [
    # A total presented among noncurrent assets (Tesla's FY2025 note total equals its
    # noncurrent balance, $1,008M) and an unrealized result in operating cash flows (Canaan's
    # FY2025 $-11,428K equals its combined result) keep their own concepts.
    ("CryptoAssetFairValue", {"section": "Non-Current Assets"}),
    ("CryptoAssetFairValueCurrent", {"section": "Non-Current Assets"}),
    ("CryptoAssetUnrealizedGainLossOperatingAndNonoperating", {"section": "Operating Activities"}),
])
def test_context_never_moves_a_crypto_element_to_another_concept(index, element, context):
    """A presentation context (section) does not turn one crypto measure into its neighbour."""
    assert index.get_standard_concept(element, context=context) == CRYPTO[element][0]


# The 2024 and 2025 us-gaap taxonomies declare no platform-user crypto element (no element
# name contains "PlatformUser" or "Safeguard"; every crypto definition excludes platform-user
# holdings), so the negative controls are the neighbouring us-gaap crypto elements whose
# measures differ, and filer extensions for crypto that is not the issuer's own unrestricted
# holding (Coinbase FY2025: borrowed, held as collateral, held for operations).
NOT_MAPPED = [
    "us-gaap:CryptoAssetRealizedAndUnrealizedGainLossOperating",
    "us-gaap:CryptoAssetRealizedAndUnrealizedGainLossNonoperating",
    "us-gaap:CryptoAssetUnrealizedGainLossOperating",
    "us-gaap:CryptoAssetUnrealizedGainLossNonoperating",
    "us-gaap:CryptoAssetUnrealizedLossOperating",
    "us-gaap:CryptoAssetRealizedGainLossOperatingAndNonoperating",
    "us-gaap:CryptoAssetFairValueRestricted",
    "us-gaap:CryptoAssetFairValueUnrestricted",
    "us-gaap:CryptoAssetCost",
    "us-gaap:CryptoAssetPurchase",
    "us-gaap:CryptoAssetSale",
    "us-gaap:CryptoAssetCustomerReceipt",
    "us-gaap:CryptoAssetNumberOfUnits",
    "coin:CryptoAssetFairValueBorrowed",
    "coin:CryptoAssetFairValueHeldAsCollateral",
    "coin:CryptoAssetFairValueOperations",
    "can:CryptoAssetReceivableNonCurrent",
]


@pytest.mark.parametrize("tag", NOT_MAPPED)
def test_other_crypto_elements_take_none_of_the_eight(index, tag):
    result = index.lookup(tag)
    crypto_concepts = {concept for concept, *_ in CRYPTO.values()}
    assert result is None or not set(result.standard_concepts) & crypto_concepts


def test_no_other_key_resolves_to_a_crypto_concept():
    crypto_concepts = {concept for concept, *_ in CRYPTO.values()}
    keys = {key for key, entry in GAAP_MAPPINGS.items()
            if isinstance(entry, dict) and set(entry.get("standard_tags", [])) & crypto_concepts}
    assert keys == set(CRYPTO)


# ---------------------------------------------------------------------------
# Synonym groups (offline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, element", [
    ("crypto_assets", "CryptoAssetFairValue"),
    ("crypto_assets_current", "CryptoAssetFairValueCurrent"),
    ("crypto_assets_noncurrent", "CryptoAssetFairValueNoncurrent"),
])
def test_balance_groups_are_singletons(name, element):
    group = SynonymGroups().get_group(name)
    assert group.synonyms == [element]
    assert group.category == "balance_sheet"
    assert "platform users" in group.description


def test_no_group_for_the_results_and_cash_flows():
    synonyms = SynonymGroups()
    for element in list(CRYPTO)[3:]:
        assert synonyms.identify_concepts(element) == [], element


# ---------------------------------------------------------------------------
# EntityFacts (offline)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("element", sorted(CRYPTO))
def test_entity_facts_gives_each_element_its_statement(element):
    assert get_primary_statement(element) == CRYPTO[element][2]


@pytest.mark.parametrize("element, statement, parent, label", [
    ("CryptoAssetFairValueCurrent", "BalanceSheet", "AssetsCurrentAbstract", "Crypto Assets, Current"),
    ("CryptoAssetFairValueNoncurrent", "BalanceSheet", "AssetsAbstract", "Crypto Assets, Noncurrent"),
    ("CryptoAssetFairValue", "BalanceSheet", "AssetsAbstract", "Crypto Assets"),
    ("CryptoAssetUnrealizedGainLossOperatingAndNonoperating", "IncomeStatement", "IncomeStatementAbstract",
     "Crypto Assets, Unrealized Gain (Loss)"),
    ("CryptoAssetRealizedAndUnrealizedGainLossOperatingAndNonoperating", "IncomeStatement",
     "IncomeStatementAbstract", "Crypto Assets, Realized and Unrealized Gain (Loss)"),
    ("PaymentForAcquisitionCryptoAsset", "CashFlowStatement", "NetCashProvidedByUsedInInvestingActivitiesAbstract",
     "Payments to Acquire Crypto Assets"),
    ("ProceedsFromDisposalCryptoAsset", "CashFlowStatement", "NetCashProvidedByUsedInInvestingActivitiesAbstract",
     "Proceeds from Disposal of Crypto Assets"),
    ("ProceedsFromCryptoAssetOperatingActivity", "CashFlowStatement",
     "NetCashProvidedByUsedInOperatingActivitiesAbstract", "Proceeds from Conversion of Crypto Consideration"),
])
def test_entity_facts_tree_places_each_element(element, statement, parent, label):
    nodes = load_virtual_trees()[statement]["nodes"]
    assert nodes[element]["parent"] == parent
    assert nodes[element]["label"] == label
    assert element in nodes[parent]["children"]
    assert nodes[element]["is_total"] is False
    # Below the 0.3 threshold: the row is built only for a company that reports it.
    assert nodes[element]["occurrence_rate"] < 0.3


# ---------------------------------------------------------------------------
# Filed statements (network, cassettes)
# ---------------------------------------------------------------------------

def _statement_frame(tmp_path, folder, names, statement):
    for name in names:
        (tmp_path / name).write_text(download_file(folder + name), encoding="utf-8")
    rendered = XBRL.from_directory(tmp_path).statements[statement]
    assert rendered is not None
    frame = rendered.render(standard=True).to_dataframe()
    return frame[~frame["dimension"]]


def _rows(frame, standard_concept, column):
    selected = frame[frame["standard_concept"] == standard_concept]
    return dict(zip(selected["concept"], selected[column], strict=True))


TSLA_FOLDER = "https://www.sec.gov/Archives/edgar/data/1318605/000162828026003952/"
TSLA_FILES = ("tsla-20251231.xsd", "tsla-20251231_pre.xml", "tsla-20251231_lab.xml", "tsla-20251231_cal.xml",
              "tsla-20251231_htm.xml")
MSTR_FOLDER = "https://www.sec.gov/Archives/edgar/data/1050446/000105044626000020/"
MSTR_FILES = ("mstr-20251231.xsd", "mstr-20251231_pre.xml", "mstr-20251231_lab.xml", "mstr-20251231_cal.xml",
              "mstr-20251231_htm.xml")
CAN_FOLDER = "https://www.sec.gov/Archives/edgar/data/1780652/000110465926043786/"
CAN_FILES = ("can-20251231.xsd", "can-20251231_pre.xml", "can-20251231_lab.xml", "can-20251231_cal.xml",
             "can-20251231x20f_htm.xml")


@pytest.mark.network
@pytest.mark.vcr
def test_tesla_digital_assets_are_noncurrent_crypto_assets(tmp_path):
    """Tesla FY2025 10-K, 0001628280-26-003952, balance sheet (R3): Digital assets $1,008M
    at 2025-12-31 and $1,076M at 2024-12-31, tagged CryptoAssetFairValueNoncurrent."""
    frame = _statement_frame(tmp_path, TSLA_FOLDER, TSLA_FILES, "BalanceSheet")

    element = "us-gaap_CryptoAssetFairValueNoncurrent"
    assert _rows(frame, "CryptoAssetsNoncurrent", "2025-12-31") == {element: 1_008_000_000}
    assert _rows(frame, "CryptoAssetsNoncurrent", "2024-12-31") == {element: 1_076_000_000}
    row = frame[frame["concept"] == element].iloc[0]
    assert row["label"] == "Digital assets"
    # The note-level total of the same amount is not on the face, and nothing else took a crypto concept.
    assert _rows(frame, "CryptoAssets", "2025-12-31") == {}


@pytest.mark.network
@pytest.mark.vcr
def test_tesla_unrealized_result_and_equal_total_stay_distinct(tmp_path):
    """Tesla FY2025 10-K: CryptoAssetFairValue and CryptoAssetFairValueNoncurrent are both
    $1,008M at 2025-12-31; the unrealized gain (loss) is $-68M (2025) and $589M (2024)."""
    for name in TSLA_FILES:
        (tmp_path / name).write_text(download_file(TSLA_FOLDER + name), encoding="utf-8")
    facts = XBRL.from_directory(tmp_path).facts.to_dataframe()
    dims = [c for c in facts.columns if c.startswith("dim_")]
    plain = facts[facts[dims].isna().all(axis=1)] if dims else facts

    def values(element, column):
        rows = plain[plain["concept"] == f"us-gaap:{element}"]
        return set(zip(rows[column], rows["numeric_value"], strict=True))

    assert ("2025-12-31", 1_008_000_000) in values("CryptoAssetFairValue", "period_instant")
    assert ("2025-12-31", 1_008_000_000) in values("CryptoAssetFairValueNoncurrent", "period_instant")
    unrealized = values("CryptoAssetUnrealizedGainLossOperatingAndNonoperating", "period_end")
    assert unrealized == {("2025-12-31", -68_000_000), ("2024-12-31", 589_000_000)}

    index = get_reverse_index()
    assert index.lookup("us-gaap:CryptoAssetFairValue").standard_concepts == ["CryptoAssets"]
    assert index.lookup("us-gaap:CryptoAssetFairValueNoncurrent").standard_concepts == ["CryptoAssetsNoncurrent"]


@pytest.mark.network
@pytest.mark.vcr
def test_strategy_digital_assets_and_purchases(tmp_path):
    """Strategy FY2025 10-K, 0001050446-26-000020: Digital assets $58,854,028K (R3, the
    unclassified CryptoAssetFairValue); Purchases of digital assets $(22,467,083)K in
    investing activities (R8)."""
    balance = _statement_frame(tmp_path, MSTR_FOLDER, MSTR_FILES, "BalanceSheet")
    assert _rows(balance, "CryptoAssets", "2025-12-31") == {"us-gaap_CryptoAssetFairValue": 58_854_028_000}
    assert balance[balance["concept"] == "us-gaap_CryptoAssetFairValue"].iloc[0]["label"] == "Digital assets"

    cash_flow = XBRL.from_directory(tmp_path).statements["CashFlowStatement"].render(standard=True).to_dataframe()
    cash_flow = cash_flow[~cash_flow["dimension"]]
    purchases = _rows(cash_flow, "CryptoPurchases", "2025-12-31")
    assert set(purchases) == {"us-gaap_PaymentForAcquisitionCryptoAsset"}
    assert abs(purchases["us-gaap_PaymentForAcquisitionCryptoAsset"]) == 22_467_083_000
    row = cash_flow[cash_flow["concept"] == "us-gaap_PaymentForAcquisitionCryptoAsset"].iloc[0]
    assert row["label"] == "Purchases of digital assets"


@pytest.mark.network
@pytest.mark.vcr
def test_canaan_unrealized_change_in_operating_cash_flows(tmp_path):
    """Canaan FY2025 20-F, 0001104659-26-043786: Change in fair value of cryptocurrency, $11,428K
    added back in operating activities (the element's filed value is $-11,428K, equal to its
    realized-and-unrealized total); Cryptocurrency $83,339K noncurrent."""
    for name in CAN_FILES:
        (tmp_path / name).write_text(download_file(CAN_FOLDER + name), encoding="utf-8")
    xbrl = XBRL.from_directory(tmp_path)

    cash_flow = xbrl.statements["CashFlowStatement"].render(standard=True).to_dataframe()
    cash_flow = cash_flow[~cash_flow["dimension"]]
    element = "us-gaap_CryptoAssetUnrealizedGainLossOperatingAndNonoperating"
    unrealized = _rows(cash_flow, "CryptoUnrealizedGainLoss", "2025-12-31")
    assert set(unrealized) == {element}
    assert abs(unrealized[element]) == 11_428_000
    assert cash_flow[cash_flow["concept"] == element].iloc[0]["label"] == "Change in fair value of cryptocurrency"

    balance = xbrl.statements["BalanceSheet"].render(standard=True).to_dataframe()
    balance = balance[~balance["dimension"]]
    assert _rows(balance, "CryptoAssetsNoncurrent", "2025-12-31") == {
        "us-gaap_CryptoAssetFairValueNoncurrent": 83_339_000}
    # Canaan's own crypto receivables are not crypto assets at fair value.
    assert _rows(balance, "CryptoAssetsCurrent", "2025-12-31") == {}


@pytest.mark.network
@pytest.mark.vcr
def test_tesla_entity_facts_balance_sheet_shows_the_crypto_line():
    from edgar import Company

    frame = Company("TSLA").get_facts().balance_sheet(periods=2, annual=True, as_dataframe=True)
    assert frame.loc["CryptoAssetFairValueNoncurrent", "label"] == "Crypto Assets, Noncurrent"
    assert frame.loc["CryptoAssetFairValueNoncurrent", "FY 2025"] == 1_008_000_000


@pytest.mark.network
@pytest.mark.vcr
def test_strategy_entity_facts_shows_crypto_balance_and_purchases():
    from edgar import Company

    facts = Company("MSTR").get_facts()
    balance = facts.balance_sheet(periods=2, annual=True, as_dataframe=True)
    assert balance.loc["CryptoAssetFairValue", "label"] == "Crypto Assets"
    assert balance.loc["CryptoAssetFairValue", "FY 2025"] == 58_854_028_000
    cash_flow = facts.cash_flow_statement(periods=2, annual=True, as_dataframe=True)
    assert cash_flow.loc["PaymentForAcquisitionCryptoAsset", "label"] == "Payments to Acquire Crypto Assets"
    assert cash_flow.loc["PaymentForAcquisitionCryptoAsset", "FY 2025"] == 22_467_083_000
