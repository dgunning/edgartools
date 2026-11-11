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

GitHub Issue: https://github.com/dgunning/edgartools/issues/1730
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.abstract_detection import is_abstract_concept
from edgar.xbrl.parsers.schema import SchemaParser

IBM_10K = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "ibm" / "10k_2024"


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
