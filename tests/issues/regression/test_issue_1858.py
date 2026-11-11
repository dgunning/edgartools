"""Concept access for cash interest paid and cash income taxes paid.

The synonym registry had no group for the cash-paid disclosures, so
``identify_concepts('InterestPaidNet')`` returned ``[]`` and
``EntityFacts.get_concept('interest_paid')`` warned "Unknown concept" and
returned None. Four groups now exist, one per tag and measurement basis:

- ``interest_paid`` = ``InterestPaidNet`` (net of capitalized interest)
- ``interest_paid_gross`` = ``InterestPaid`` (including capitalized interest)
- ``income_taxes_paid`` = ``IncomeTaxesPaidNet`` (net of refunds)
- ``income_taxes_paid_gross`` = ``IncomeTaxesPaid`` (before refunds)

Net and gross are different measures, so neither group falls back to the other.
``get_concept(..., return_metadata=True)`` reports the basis from the group
definition (``SynonymGroup.basis``).

Ground truth, read from SEC companyfacts and the frames API:

- Oracle FY2026 10-K, accession 0001193125-26-277521, 2025-06-01..2026-05-31:
  InterestPaidNet 3,896,000,000; IncomeTaxesPaidNet 3,704,000,000;
  IncomeTaxesPaid 3,704,000,000; no InterestPaid.
- Johnson & Johnson FY2025 10-K, accession 0000200406-26-000016,
  2024-12-30..2025-12-28: InterestPaidNet 1,863,000,000 and InterestPaid
  1,977,000,000 (net and gross differ by 114,000,000).
- Boeing FY2025 10-K, accession 0001628280-26-004357: InterestPaid
  2,630,000,000 and no InterestPaidNet (a gross-only filer).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1858
"""
import warnings
from datetime import date

import pytest

from edgar.entity.entity_facts import EntityFacts
from edgar.entity.models import FinancialFact
from edgar.exceptions import ValidationError
from edgar.standardization import SynonymGroup, SynonymGroups, get_synonym_groups

pytestmark = pytest.mark.regression

NEW_GROUPS = {
    "interest_paid": ("InterestPaidNet", "net"),
    "interest_paid_gross": ("InterestPaid", "gross"),
    "income_taxes_paid": ("IncomeTaxesPaidNet", "net"),
    "income_taxes_paid_gross": ("IncomeTaxesPaid", "gross"),
}


def _concept(facts, name, period=None, return_metadata=True):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return facts.get_concept(name, period=period, return_metadata=return_metadata)


# --------------------------------------------------------------------------- #
# Offline: the registry
# --------------------------------------------------------------------------- #

@pytest.mark.fast
@pytest.mark.parametrize("group_name,tag_basis", sorted(NEW_GROUPS.items()))
def test_each_group_holds_exactly_its_one_tag_with_its_basis(group_name, tag_basis):
    tag, basis = tag_basis
    group = get_synonym_groups().get_group(group_name)
    assert group is not None, f"{group_name} is not registered"
    assert group.synonyms == [tag]
    assert group.basis == basis
    assert group.category == "cash_flow"


@pytest.mark.fast
@pytest.mark.parametrize("group_name,tag_basis", sorted(NEW_GROUPS.items()))
def test_identify_concepts_names_exactly_one_group_per_tag(group_name, tag_basis):
    """identify_concepts() and get_concept() agree: each tag maps to its own group only."""
    tag, _ = tag_basis
    groups = get_synonym_groups()
    for spelling in (tag, f"us-gaap:{tag}", f"us-gaap_{tag}"):
        assert [info.name for info in groups.identify_concepts(spelling)] == [group_name]


@pytest.mark.fast
def test_gross_and_net_are_not_synonyms_of_each_other():
    groups = get_synonym_groups()
    assert "InterestPaid" not in groups.get_synonyms("interest_paid")
    assert "InterestPaidNet" not in groups.get_synonyms("interest_paid_gross")
    assert "IncomeTaxesPaid" not in groups.get_synonyms("income_taxes_paid")
    assert "IncomeTaxesPaidNet" not in groups.get_synonyms("income_taxes_paid_gross")


@pytest.mark.fast
def test_cash_paid_tags_stay_out_of_the_accrual_expense_groups():
    """#1440/#1442 separated cash paid from expense; the new groups must not undo it."""
    groups = get_synonym_groups()
    for tag in ("InterestPaidNet", "InterestPaid"):
        assert tag not in groups.get_synonyms("interest_expense")
    for tag in ("IncomeTaxesPaidNet", "IncomeTaxesPaid"):
        assert tag not in groups.get_synonyms("income_tax_expense")


@pytest.mark.fast
def test_groups_without_a_basis_keep_none_and_their_serialized_shape():
    group = get_synonym_groups().get_group("dividends_paid")
    assert group.basis is None
    assert "basis" not in group.to_dict()


@pytest.mark.fast
def test_basis_round_trips_through_to_dict_and_register_group():
    group = get_synonym_groups().get_group("income_taxes_paid_gross")
    data = group.to_dict()
    assert data["basis"] == "gross"
    assert SynonymGroup.from_dict(data).basis == "gross"

    custom = SynonymGroups(load_builtin=False)
    registered = custom.register_group("my_interest", ["InterestPaidNet"], basis="net")
    assert registered.basis == "net"


@pytest.mark.fast
def test_an_unknown_basis_is_rejected_with_a_useful_error():
    # ValidationError IS-A ValueError, so either except clause catches it.
    with pytest.raises(ValidationError, match="basis must be one of 'net', 'gross' or None, got 'netto'"):
        SynonymGroup(name="bad", synonyms=["InterestPaidNet"], basis="netto")


# --------------------------------------------------------------------------- #
# Offline: get_concept() on synthetic facts — basis metadata, no fallback
# --------------------------------------------------------------------------- #

def _fact(concept, value):
    return FinancialFact(
        concept=f"us-gaap:{concept}",
        taxonomy="us-gaap",
        label=concept,
        value=value,
        numeric_value=float(value),
        unit="USD",
        period_type="duration",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        fiscal_year=2025,
        fiscal_period="FY",
        accession="0001234567-26-000001",
        filing_date=date(2026, 2, 1),
        form_type="10-K",
    )


@pytest.fixture
def gross_only_facts():
    """A filer that tags only the gross measures (Boeing's shape for interest)."""
    return EntityFacts(cik=123456, name="Gross Only Co", facts=[
        _fact("InterestPaid", 2_630_000_000),
        _fact("IncomeTaxesPaid", 400_000_000),
    ])


@pytest.mark.fast
def test_net_group_does_not_fall_back_to_the_gross_tag(gross_only_facts):
    # Silence check: the net group returns None rather than the gross value,
    # with or without metadata.
    assert _concept(gross_only_facts, "interest_paid", return_metadata=False) is None
    assert _concept(gross_only_facts, "interest_paid") is None
    assert _concept(gross_only_facts, "income_taxes_paid", period="2025-FY") is None

    gross = _concept(gross_only_facts, "interest_paid_gross")
    assert gross["value"] == 2_630_000_000
    assert gross["tag_used"] == "us-gaap:InterestPaid"
    assert gross["basis"] == "gross"


@pytest.mark.fast
def test_existing_groups_do_not_gain_a_basis_key():
    facts = EntityFacts(cik=123456, name="Div Co", facts=[_fact("PaymentsOfDividends", 5_000_000)])
    result = _concept(facts, "dividends_paid")
    assert result["value"] == 5_000_000
    assert "basis" not in result


# --------------------------------------------------------------------------- #
# Network (cassettes): real filers
# --------------------------------------------------------------------------- #

@pytest.mark.network
@pytest.mark.vcr
def test_oracle_fy2026_cash_interest_and_taxes_paid():
    """The documented example in edgar/standardization/README.md, run as written."""
    from edgar import Company

    facts = Company("ORCL").get_facts()
    cash_interest = facts.get_concept("interest_paid", period="2026-FY", return_metadata=True)
    cash_taxes = facts.get_concept("income_taxes_paid", period="2026-FY", return_metadata=True)

    assert cash_interest["value"] == 3_896_000_000
    assert cash_interest["tag_used"] == "us-gaap:InterestPaidNet"
    assert cash_interest["basis"] == "net"
    assert cash_interest["period_end"] == date(2026, 5, 31)
    assert cash_interest["unit"] == "USD"

    assert cash_taxes["value"] == 3_704_000_000
    assert cash_taxes["tag_used"] == "us-gaap:IncomeTaxesPaidNet"
    assert cash_taxes["basis"] == "net"

    gross_taxes = facts.get_concept("income_taxes_paid_gross", period="2026-FY", return_metadata=True)
    assert gross_taxes["value"] == 3_704_000_000
    assert gross_taxes["tag_used"] == "us-gaap:IncomeTaxesPaid"
    assert gross_taxes["basis"] == "gross"

    # Oracle tags no InterestPaid: the gross group is empty, not the net value.
    assert _concept(facts, "interest_paid_gross", period="2026-FY") is None


@pytest.mark.network
@pytest.mark.vcr
def test_johnson_and_johnson_fy2025_net_and_gross_interest_differ():
    from edgar import Company

    facts = Company("JNJ").get_facts()
    net = _concept(facts, "interest_paid", period="2025-FY")
    gross = _concept(facts, "interest_paid_gross", period="2025-FY")
    assert (net["value"], net["tag_used"], net["basis"]) == (1_863_000_000, "us-gaap:InterestPaidNet", "net")
    assert (gross["value"], gross["tag_used"], gross["basis"]) == (1_977_000_000, "us-gaap:InterestPaid", "gross")
    assert net["period_end"] == gross["period_end"] == date(2025, 12, 28)


@pytest.mark.network
@pytest.mark.vcr
def test_boeing_fy2025_interest_paid_is_none_where_only_gross_is_reported():
    from edgar import Company

    facts = Company("BA").get_facts()
    assert _concept(facts, "interest_paid", period="2025-FY") is None
    gross = _concept(facts, "interest_paid_gross", period="2025-FY")
    assert gross["value"] == 2_630_000_000
    assert gross["tag_used"] == "us-gaap:InterestPaid"
    assert gross["basis"] == "gross"
