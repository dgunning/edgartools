"""Verify public discovery of effective XBRL mapping families.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1423
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import html

from edgar.documents.strategies.xbrl_extraction import XBRLExtractor
from edgar.xbrl.standardization import get_default_store, reverse_index
from edgar.xbrl.standardization.reverse_index import ReverseIndex

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def index():
    return ReverseIndex()


@pytest.fixture
def build_index(tmp_path):
    def build(entries, *, totals=None, labels=None):
        files = []
        for name, data in (
            ("mappings.json", entries),
            ("display.json", labels or {}),
            ("totals.json", {"totals": totals or {}}),
        ):
            path = tmp_path / name
            path.write_text(json.dumps(data), encoding="utf-8")
            files.append(str(path))
        return ReverseIndex(*files)

    return build


def test_members_match_effective_forward_lookup(build_index):
    entries = {
        "Zulu": {"standard_tags": ["Revenue", "OtherRevenue"], "ambiguous": True},
        "Component": {"standard_tags": ["Revenue", "OtherRevenue"], "confidence": 1.0, "is_total": True},
        "Alpha": {"standard_tags": ["Revenue"]},
        "CommonStockSharesAuthorized": {"standard_tags": ["Revenue"]},
    }
    index = build_index(entries, totals={"Revenue": ["Alpha", "Zulu", "CommonStockSharesAuthorized"]})
    expected = {}
    for key in sorted(entries):
        result = index.lookup(key)
        if result is not None and "Revenue" in result.standard_concepts:
            expected[key] = result
    assert tuple(expected) == ("Alpha", "Zulu")

    members = index.members_of("Revenue")
    assert isinstance(members, tuple)
    assert tuple(member.mapping_key for member in members) == tuple(expected)
    assert [member.result for member in members] == list(expected.values())
    assert members[1].result.standard_concepts == ["Revenue", "OtherRevenue"]
    assert members[1].result.is_ambiguous is True
    assert index.lookup("Component").standard_concepts == ["OtherRevenue"]


def test_shipped_revenue_members_respect_total_guard(index):
    keys = {member.mapping_key for member in index.members_of("Revenue")}
    assert "Revenues" in keys
    assert "SalesReturnsGoods" not in keys


def test_industry_changes_membership_and_preserves_provenance(build_index):
    index = build_index(
        {
            "Premiums": {
                "standard_tags": ["OtherRevenue"],
                "industry_overrides": {"Insur": {"standard_tags": ["Revenue", "InsuranceRevenue"], "confidence": 0.8}},
            },
            "Sales": {
                "standard_tags": ["Revenue"],
                "industry_overrides": {"Insur": {"standard_tags": ["OtherRevenue"]}},
            },
        }
    )
    separate_index = build_index({"Fees": {"standard_tags": ["Revenue"]}})

    assert [member.mapping_key for member in index.members_of("Revenue")] == ["Sales"]
    assert [member.mapping_key for member in index.members_of("Revenue", industry="Banks")] == ["Sales"]
    (member,) = index.members_of("Revenue", industry="Insur")
    assert member.mapping_key == "Premiums"
    assert member.result == index.lookup("Premiums", industry="Insur")
    assert member.result.standard_concepts == ["Revenue", "InsuranceRevenue"]
    assert member.result.applied_industry == "Insur"
    assert member.result.metadata_origins["confidence"] == "industry_override"
    assert index.members_of("InsuranceRevenue") == ()
    assert [member.mapping_key for member in separate_index.members_of("Revenue", industry="Insur")] == ["Fees"]
    assert [member.mapping_key for member in index.members_of("Revenue", industry="Insur")] == ["Premiums"]


def test_member_identity_preserves_distinct_keys(build_index):
    index = build_index({key: {"standard_tags": ["TradeReceivables"]} for key in ("us-gaap:Example", "ifrs-full_Example", "Example")})
    members = index.members_of("TradeReceivables")
    assert [(member.mapping_key, member.qualified_tag) for member in members] == [
        ("Example", None),
        ("ifrs-full_Example", "ifrs-full:Example"),
        ("us-gaap:Example", "us-gaap:Example"),
    ]


@pytest.mark.parametrize("value", [None, 42])
def test_non_string_identifier_raises(index, value):
    with pytest.raises(TypeError):
        index.members_of(value)


@pytest.mark.parametrize("value", ["", "Revenues", "NetIncomeLoss", "Total Sales"])
def test_unknown_identifier_raises(build_index, value):
    index = build_index({"Example": {"standard_tags": ["Revenue"]}}, labels={"Revenue": "Total Sales"})
    with pytest.raises(ValueError, match=r"(?i)standard concept"):
        index.members_of(value)


@pytest.mark.parametrize(
    "value, expected",
    [("Revenues", "Revenue"), ("NetIncomeLoss", "NetIncome"), ("TotalAssets", "Assets")],
)
def test_unknown_identifier_suggests_known_concepts(index, value, expected):
    with pytest.raises(ValueError, match=rf"Did you mean .*\b{expected}\b"):
        index.members_of(value)


def test_suggestions_include_registry_and_override_concepts(build_index):
    index = build_index(
        {"Example": {"industry_overrides": {"Insur": {"standard_tags": ["UnderwritingIncome"]}}}},
        labels={"RegistryOnly": "Registry Label"},
    )

    with pytest.raises(ValueError, match=r"Did you mean RegistryOnly"):
        index.members_of("RegistryOnl")
    with pytest.raises(ValueError, match=r"Did you mean UnderwritingIncome"):
        index.members_of("UnderwritingIncom")


def test_known_family_without_members_returns_empty_tuple(build_index):
    index = build_index({}, labels={"Revenue": "Total Sales"})
    assert index.members_of("Revenue") == ()


def test_mutating_member_result_does_not_affect_later_answers(build_index):
    index = build_index({"Example": {"standard_tags": ["Revenue"], "confidence": 0.8}})
    (member,) = index.members_of("Revenue")
    member.result.standard_concepts.append("Changed")
    member.result.display_names.clear()
    member.result.metadata_origins["confidence"] = "changed"

    assert index.lookup("Example").standard_concepts == ["Revenue"]
    (later,) = index.members_of("Revenue")
    assert later.result.standard_concepts == ["Revenue"]
    assert later.result.display_names == ["Revenue"]
    assert later.result.metadata_origins["confidence"] == "base"


def test_module_level_api_matches_class(build_index, monkeypatch):
    index = build_index(
        {
            "Premiums": {
                "standard_tags": ["OtherRevenue"],
                "industry_overrides": {"Insur": {"standard_tags": ["Revenue"]}},
            }
        }
    )
    monkeypatch.setattr(reverse_index, "_default_index", index)
    members = reverse_index.members_of("Revenue", industry="Insur")
    assert members == reverse_index.get_reverse_index().members_of("Revenue", industry="Insur")
    assert members
    assert all(isinstance(member, reverse_index.MappingMember) for member in members)


def test_legacy_store_still_returns_legacy_revenue_keys():
    assert get_default_store().get_company_concepts("Revenue") == {
        "us-gaap_OperatingRevenue",
        "us-gaap_Revenue",
        "us-gaap_Revenues",
        "us-gaap_SalesRevenueNet",
    }


def test_unitedhealth_2024_premiums_are_a_revenue_member(index):
    """UnitedHealth FY2024 10-K, accession 0000731766-25-000063, page 41.

    Consolidated Statements of Operations, Premiums, $308,810 million.
    https://www.sec.gov/Archives/edgar/data/731766/000073176625000063/unh-20241231.htm
    """
    fixture = Path(__file__).parents[1] / "fixtures/html/unh/10k/unh-10-k-2025-02-27.html"
    root = html.parse(str(fixture))
    elements = root.xpath('//*[@name="us-gaap:PremiumsEarnedNet" and @contextref="c-1"]')
    assert len(elements) == 1
    fact = XBRLExtractor().extract_fact(elements[0])
    assert fact is not None
    assert fact.context["entity"] == "0000731766"
    assert fact.context["start_date"] == "2024-01-01"
    assert fact.context["end_date"] == "2024-12-31"
    assert fact.unit == "USD"
    assert Decimal(fact.value) == Decimal("308810000000")

    result = index.lookup(fact.concept)
    assert result is not None
    assert result.mapping_key == "PremiumsEarnedNet"
    members = {member.mapping_key: member.result for member in index.members_of("Revenue")}
    assert members["PremiumsEarnedNet"] == result
