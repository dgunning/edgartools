"""
Regression test for GitHub issue #1730: abstract status of imported concepts was
guessed from case-sensitive name patterns

A filing's own schema declares only its extension concepts, so the abstract
status of us-gaap/dei/srt concepts is guessed from the name. The guess only knew
``RollForward`` (us-gaap also spells it ``Rollforward``) and had no rule for
domain members, so 1,674 of the 5,369 abstract elements in us-gaap-2025.xsd
read as non-abstract. Separately, the schema parser read ``abstract="1"`` (a
valid xs:boolean) as False, and the name guess could override a declaration
the parser had actually read.

Ground truth, from the tracked fixture (read offline): IBM's FY2024 10-K,
accession 0000051143-25-000015, presents
``us-gaap_AllowanceForDoubtfulAccountsReceivableRollforward`` as the heading of
its allowance-for-credit-losses roll-forward; us-gaap-2025.xsd declares it
``abstract="true"``.

The name guess then gave way to the bundled FASB element table (#1728) for
us-gaap and srt concepts. Read by hand from us-gaap-2024.xsd
(https://xbrl.fasb.org/us-gaap/2024/elts/us-gaap-2024.xsd): ``AwardTypeAxis``,
``ShareBasedCompensationArrangementsByShareBasedPaymentAwardAwardTypeAndPlanNameDomain``
and ``TableTextBlock`` are all declared ``abstract='true'``. Microsoft's FY2024
10-K (accession 0000950170-24-087843) presents the first two, but they never
reach its element catalog, so they read as non-abstract before.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1730
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.abstract_detection import is_abstract_concept
from edgar.xbrl.parsers.concepts import get_standard_abstract
from edgar.xbrl.parsers.schema import SchemaParser

IBM_10K = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "ibm" / "10k_2024"
MSFT_10K = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "msft" / "10k_2024"


@pytest.mark.parametrize("concept", [
    "us-gaap_ShareBasedCompensationArrangementByShareBasedPaymentAwardOptionsOutstandingWeightedAverageExercisePriceRollforward",
    "us-gaap_AllowanceForDoubtfulAccountsReceivableRollforward",
    "us-gaap_CommonClassAMember",
    "us-gaap_IncreaseDecreaseInStockholdersEquityRollForward",
])
def test_imported_abstract_concepts_detected(concept):
    assert is_abstract_concept(concept) is True


def test_monetary_concepts_stay_non_abstract():
    assert is_abstract_concept("us-gaap_Revenues") is False
    assert is_abstract_concept("us-gaap_NetIncomeLoss") is False


def test_read_declaration_is_authoritative():
    # A declaration the parser read is the answer, whatever the name suggests
    assert is_abstract_concept("abc_DistributionsToMember", schema_abstract=False, declared=True) is False
    assert is_abstract_concept("abc_SegmentHeading", schema_abstract=True, declared=True) is True


def _parse(abstract_attr: str) -> bool:
    catalog = {}
    xsd = f"""<?xml version="1.0" encoding="utf-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:xbrli="http://www.xbrl.org/2003/instance"
           targetNamespace="http://example.com/abc">
  <xs:element id="abc_Heading" name="Heading" abstract="{abstract_attr}"
              substitutionGroup="xbrli:item" type="xbrli:stringItemType"
              xbrli:periodType="duration" nillable="true"/>
</xs:schema>"""
    SchemaParser(catalog).parse_schema_content(xsd)
    return catalog["abc_Heading"].abstract


@pytest.mark.parametrize("attr,expected", [("true", True), ("1", True), ("false", False), ("0", False)])
def test_schema_abstract_is_read_as_xs_boolean(attr, expected):
    assert _parse(attr) is expected


def test_ibm_rollforward_heading_is_abstract():
    xbrl = XBRL.from_directory(IBM_10K)
    statement = xbrl.statements["http://www.ibm.com/role/RevenueRecognitionTradeAllowanceforCreditLossesDetails"]
    df = statement.to_dataframe()
    row = df[df["concept"] == "us-gaap_AllowanceForDoubtfulAccountsReceivableRollforward"].iloc[0]
    assert bool(row["abstract"]) is True
    # The reportable lines under the heading keep their values and stay non-abstract
    assert not df[df["concept"] == "us-gaap_AllowanceForDoubtfulAccountsReceivableWriteOffs"]["abstract"].any()


@pytest.mark.parametrize("concept,expected", [
    ("us-gaap:AwardTypeAxis", True),
    ("us-gaap_TableTextBlock", True),
    ("us-gaap:Revenues", False),
    # Named like a heading, declared non-abstract: the table beats the name
    ("us-gaap_BusinessInterruptionInsuranceRecoveryStatementOfIncomeLineItems", False),
])
def test_standard_concept_abstract_comes_from_the_table(concept, expected):
    assert get_standard_abstract(concept) is expected
    assert is_abstract_concept(concept.replace(":", "_")) is expected


@pytest.mark.parametrize("concept", ["abc_CustomHeading", "dei_CoverAbstract", ""])
def test_concept_the_table_does_not_declare_is_unknown(concept):
    # Not in us-gaap or srt: None, so the caller falls back rather than reading "False"
    assert get_standard_abstract(concept) is None


def test_extension_and_dei_concepts_still_use_the_name_guess():
    assert is_abstract_concept("dei_CoverAbstract") is True
    assert is_abstract_concept("abc_SegmentReportingRollforward") is True
    assert is_abstract_concept("abc_SegmentRevenue") is False


def test_msft_axis_missing_from_catalog_is_abstract():
    xbrl = XBRL.from_directory(MSFT_10K)
    role = "http://www.microsoft.com/20240630/taxonomy/role/Role_DisclosureStockPlanActivityDetail"
    nodes = xbrl.presentation_trees[role].all_nodes
    for concept in ("us-gaap_AwardTypeAxis",
                    "us-gaap_ShareBasedCompensationArrangementsByShareBasedPaymentAwardAwardTypeAndPlanNameDomain"):
        assert concept not in xbrl.element_catalog
        assert nodes[concept].is_abstract is True


def test_calculation_linkbase_reads_the_same_rule():
    # calculation_linkbase() read the raw catalog flag, False for every imported concept
    calc = XBRL.from_directory(MSFT_10K).calculation_linkbase(include_abstract=True)
    revenue = calc[(calc.concept_taxonomy == "us-gaap") & (calc.concept == "RevenueFromContractWithCustomerExcludingAssessedTax")]
    assert len(revenue) > 0
    assert not revenue["is_abstract"].any()
