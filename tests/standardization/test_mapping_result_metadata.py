"""Expose stored mapping annotations without changing accepted concepts.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1422

The contributor chose a NEW SEC-filing value assertion to meet the repository's
verification requirement, rather than relying on an existing assertion. UnitedHealth
Group FY2024 10-K, accession 0000731766-25-000063, filed 2025-02-27:
Consolidated Statements of Operations, page 41, Premiums = $308,810 million.
Checked directly against SEC on 2026-11-08:
https://www.sec.gov/Archives/edgar/data/731766/000073176625000063/unh-20241231.htm
The amount is filing evidence; the mapping confidence is a stored annotation,
not evidence that premiums are equivalent to the company's total revenue.

Stored mapping expectations were inspected at repository revision 8107376f.
"""

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import html

from edgar.documents.strategies.xbrl_extraction import XBRLExtractor
from edgar.xbrl.standardization.reverse_index import MappingResult, ReverseIndex

pytestmark = pytest.mark.fast

METADATA_FIELDS = ("confidence", "section", "statement", "is_total", "company_count")
BASE_METADATA = {
    "confidence": 0.5,
    "section": "Revenue",
    "statement": "IncomeStatement",
    "is_total": True,
    "company_count": 131,
}


@pytest.fixture(scope="module")
def index():
    return ReverseIndex()


@pytest.fixture
def custom_index(tmp_path):
    """Build isolated mappings without changing shipped data or singleton state."""

    def build(entries, totals=None):
        files = []
        for name, data in (
            ("mappings.json", entries),
            ("display.json", {"Revenue": "Total Revenue", "OtherRevenue": "Other Revenue"}),
            ("totals.json", {"totals": totals or {}}),
        ):
            path = tmp_path / name
            path.write_text(json.dumps(data), encoding="utf-8")
            files.append(str(path))
        return ReverseIndex(*files)

    return build


def assert_metadata(result, values, origins):
    assert result is not None
    assert {name: getattr(result, name) for name in METADATA_FIELDS} == values
    assert result.metadata_origins == origins


@pytest.mark.parametrize(
    "key,confidence,count",
    [
        ("Revenues", 1.0, 3110),
        ("PremiumsEarnedNet", 0.5, 131),
    ],
)
def test_shipped_metadata(index, key, confidence, count):
    result = index.lookup(f"us-gaap:{key}")
    assert_metadata(result, {**BASE_METADATA, "confidence": confidence, "company_count": count}, dict.fromkeys(METADATA_FIELDS, "base"))
    assert result.standard_concepts == ["Revenue"]
    assert result.display_names == ["Revenue"]
    assert result.mapping_key == key
    assert result.applied_industry is None


@pytest.mark.parametrize("tag", ["Revenues", "us-gaap:Revenues", "us-gaap_Revenues", "revenues"])
def test_mapping_key_is_stored_key(index, tag):
    assert index.lookup(tag).mapping_key == "Revenues"


@pytest.mark.parametrize(
    "metadata,origin",
    [
        ({}, "missing"),
        (dict.fromkeys(METADATA_FIELDS), "base"),
        ({"confidence": 0.0, "section": "", "statement": "", "is_total": False, "company_count": 0}, "base"),
    ],
)
def test_missing_null_zero_and_false_stay_distinct(custom_index, metadata, origin):
    index = custom_index({"Example": {"standard_tags": ["OtherRevenue"], **metadata}})
    result = index.lookup("Example")
    assert_metadata(result, {name: metadata.get(name) for name in METADATA_FIELDS}, dict.fromkeys(METADATA_FIELDS, origin))
    if metadata.get("is_total") is False:
        assert result.is_total is False
        assert result.company_count == 0
        assert result.confidence == 0.0


@pytest.mark.parametrize(
    "industry,override,expected,overridden",
    [
        (None, {"confidence": 0.9}, BASE_METADATA, ()),
        ("Banks", {"confidence": 0.9}, BASE_METADATA, ()),
        (
            "Insur",
            {"confidence": 0.9, "company_count": 0, "is_total": False},
            {**BASE_METADATA, "confidence": 0.9, "company_count": 0, "is_total": False},
            ("confidence", "company_count", "is_total"),
        ),
        ("Insur", {"confidence": None}, {**BASE_METADATA, "confidence": None}, ("confidence",)),
        ("Insur", {"standard_tags": ["OtherRevenue"]}, BASE_METADATA, ()),
    ],
)
def test_industry_provenance_is_field_wise(custom_index, industry, override, expected, overridden):
    index = custom_index(
        {
            "Example": {
                "standard_tags": ["OtherRevenue"],
                **BASE_METADATA,
                "industry_overrides": {"Insur": override},
            }
        }
    )
    result = index.lookup("Example", industry=industry)
    origins = dict.fromkeys(METADATA_FIELDS, "base")
    origins.update(dict.fromkeys(overridden, "industry_override"))
    assert_metadata(result, expected, origins)
    assert result.standard_concepts == ["OtherRevenue"]
    assert result.applied_industry == ("Insur" if industry == "Insur" else None)
    assert result.mapping_key == "Example"


def test_candidate_only_override_changes_candidates_without_relabeling_metadata(custom_index):
    index = custom_index(
        {
            "Example": {
                "standard_tags": ["Original"],
                **BASE_METADATA,
                "industry_overrides": {"Insur": {"standard_tags": ["OtherRevenue"]}},
            }
        }
    )
    assert index.lookup("Example").standard_concepts == ["Original"]
    result = index.lookup("Example", industry="Insur")
    assert result.standard_concepts == ["OtherRevenue"]
    assert_metadata(result, BASE_METADATA, dict.fromkeys(METADATA_FIELDS, "base"))
    assert result.applied_industry == "Insur"


def test_override_can_supply_metadata_missing_from_base(custom_index):
    index = custom_index(
        {
            "Example": {
                "standard_tags": ["OtherRevenue"],
                "industry_overrides": {"Insur": {"confidence": None}},
            }
        }
    )
    origins = dict.fromkeys(METADATA_FIELDS, "missing")
    origins["confidence"] = "industry_override"
    assert_metadata(index.lookup("Example", industry="Insur"), dict.fromkeys(METADATA_FIELDS), origins)


@pytest.mark.parametrize("tag", ["us-gaap:SalesAndMarketingExpense", "Unknown1422", "us-gaap:CommonStockSharesAuthorized"])
def test_rejected_and_unknown_tags_remain_none(index, tag):
    assert index.lookup(tag) is None


def test_annotations_and_overrides_cannot_bypass_closed_total_guard(custom_index):
    index = custom_index(
        {
            "Component": {
                "standard_tags": ["Revenue"],
                "confidence": 1.0,
                "is_total": True,
                "industry_overrides": {"Insur": {"confidence": 1.0, "is_total": True}},
            }
        },
        totals={"Revenue": ["Whole"]},
    )
    assert index.lookup("Component") is None
    assert index.lookup("Component", industry="Insur") is None


def test_metadata_describes_entry_after_partial_candidate_rejection(custom_index):
    index = custom_index(
        {
            "Component": {
                "standard_tags": ["Revenue", "OtherRevenue"],
                **BASE_METADATA,
            }
        },
        totals={"Revenue": ["Whole"]},
    )
    result = index.lookup("Component")
    assert result.standard_concepts == ["OtherRevenue"]
    assert result.display_names == ["Other Revenue"]
    assert_metadata(result, BASE_METADATA, dict.fromkeys(METADATA_FIELDS, "base"))


def test_six_argument_construction_and_serialization():
    result = MappingResult(["Revenue"], ["Total Revenue"], False, False, None, None)
    assert result.primary_concept == "Revenue"
    assert result.primary_display_name == "Total Revenue"
    serialized = asdict(result)
    assert serialized == {
        "standard_concepts": ["Revenue"],
        "display_names": ["Total Revenue"],
        "is_ambiguous": False,
        "is_deprecated": False,
        "deprecated_year": None,
        "comment": None,
        **dict.fromkeys(METADATA_FIELDS),
        "mapping_key": None,
        "applied_industry": None,
        "metadata_origins": {},
    }


def test_constructor_provenance_defaults_are_independent():
    first = MappingResult([], [], False, False, None, None)
    second = MappingResult([], [], False, False, None, None)
    first.metadata_origins["confidence"] = "changed"
    assert second.metadata_origins == {}


def test_lookup_provenance_is_independent(index):
    first = index.lookup("Revenues")
    second = index.lookup("Revenues")
    first.metadata_origins["confidence"] = "changed"
    assert second.metadata_origins == dict.fromkeys(METADATA_FIELDS, "base")
    assert index.lookup("Revenues").metadata_origins == dict.fromkeys(METADATA_FIELDS, "base")


def test_unitedhealth_2024_premiums_and_mapping_metadata(index):
    """Read a real filed amount before inspecting annotations for its source tag."""
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
    assert_metadata(result, BASE_METADATA, dict.fromkeys(METADATA_FIELDS, "base"))
    assert result.standard_concepts == ["Revenue"]
    assert result.mapping_key == "PremiumsEarnedNet"
