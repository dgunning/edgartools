"""Cash-payment components must not claim net cash-flow subtotals.

The classified names are IFRS elements. Correct IFRS namespaces are already
guarded; deleting polluted bare entries also protects bare and US-GAAP lookups.
The related monetary family is pinned without changing genuine activity totals.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1440
"""

import ast
import json
from pathlib import Path

import pytest

from edgar.xbrl import statements as statements_module
from edgar.xbrl import xbrl as xbrl_module
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.core import ConceptMapper, MappingStore, standardize_statement
from edgar.xbrl.standardization.reverse_index import get_reverse_index
from edgar.xbrl.standardization.sic_industry import _FF48_SIC_RANGES
from edgar.xbrl.statement_resolver import statement_registry

CLASSIFIED_PAYMENTS = (
    "IncomeTaxesPaidClassifiedAsOperatingActivities",
    "IncomeTaxesPaidRefundClassifiedAsOperatingActivities",
    "InterestPaidClassifiedAsOperatingActivities",
    "InterestPaidClassifiedAsFinancingActivities",
)
PAYMENT_FAMILY = (
    "IncomeTaxesPaid",
    "IncomeTaxesPaidClassifiedAsOperatingActivities",
    "IncomeTaxesPaidNet",
    "IncomeTaxesPaidRefund",
    "IncomeTaxesPaidRefundClassifiedAsFinancingActivities",
    "IncomeTaxesPaidRefundClassifiedAsInvestingActivities",
    "IncomeTaxesPaidRefundClassifiedAsOperatingActivities",
    "IncomeTaxesRefundClassifiedAsOperatingActivities",
    "InterestPaid",
    "InterestPaidCapitalized",
    "InterestPaidClassifiedAsFinancingActivities",
    "InterestPaidClassifiedAsInvestingActivities",
    "InterestPaidClassifiedAsOperatingActivities",
    "InterestPaidNet",
    "InterestPaidOnDepositLiabilitiesClassifiedAsOperatingActivities",
    "ProceedsFromIncomeTaxRefunds",
)
PREFIXES = ("", "us-gaap:", "us-gaap_", "ifrs-full:", "ifrs-full_", "ifrs:", "ifrs_")
INDUSTRIES = (None, *sorted({code for _, _, code in _FF48_SIC_RANGES}))
# Derive every typed form the shipped public statement catalogue can supply.
_PUBLIC_TREE = ast.parse(Path(xbrl_module.__file__).read_text(encoding="utf-8"))
_ALL_STATEMENTS = next(node for node in ast.walk(_PUBLIC_TREE) if isinstance(node, ast.FunctionDef) and node.name == "get_all_statements")
_LITERAL_TYPES = {
    node.value.value
    for node in ast.walk(_ALL_STATEMENTS)
    if isinstance(node, ast.Assign)
    and isinstance(node.value, ast.Constant)
    and isinstance(node.value.value, str)
    and any(isinstance(target, ast.Name) and target.id == "statement_type" for target in node.targets)
}
_CANONICAL_TYPES = set(statements_module.statement_to_concepts)
TYPED_STATEMENTS = tuple(sorted(set(statement_registry) | _CANONICAL_TYPES | _LITERAL_TYPES | {name + "Parenthetical" for name in _CANONICAL_TYPES}))
STATEMENT_TYPES = (
    *TYPED_STATEMENTS,
    *("http://example.com/role/" + name for name in TYPED_STATEMENTS),
    "http://example.com/role/FinancialStatement",
    "",
    None,
)
NET_TOTALS = (
    ("us-gaap:NetCashProvidedByUsedInOperatingActivities", "NetCashFromOperatingActivities", "Net Cash from Operating Activities"),
    ("us-gaap:NetCashProvidedByUsedInInvestingActivities", "NetCashFromInvestingActivities", "Net Cash from Investing Activities"),
    ("us-gaap:NetCashProvidedByUsedInFinancingActivities", "NetCashFromFinancingActivities", "Net Cash from Financing Activities"),
    ("ifrs-full:CashFlowsFromUsedInOperatingActivities", "NetCashFromOperatingActivities", "Net Cash from Operating Activities"),
    ("ifrs-full:CashFlowsFromUsedInInvestingActivities", "NetCashFromInvestingActivities", "Net Cash from Investing Activities"),
    ("ifrs-full:CashFlowsFromUsedInFinancingActivities", "NetCashFromFinancingActivities", "Net Cash from Financing Activities"),
)


@pytest.fixture(scope="module")
def index():
    return get_reverse_index()


@pytest.fixture(scope="module")
def mapper():
    return ConceptMapper(MappingStore(read_only=True))


def test_payment_family_and_industry_domain_are_complete():
    assert len(PAYMENT_FAMILY) == len(set(PAYMENT_FAMILY)) == 16
    assert set(CLASSIFIED_PAYMENTS) <= set(PAYMENT_FAMILY)
    assert len(CLASSIFIED_PAYMENTS) == 4
    assert len(INDUSTRIES) == 49
    assert len(PREFIXES) == 7


@pytest.mark.parametrize("tag", CLASSIFIED_PAYMENTS)
def test_classified_payment_has_no_stored_entry_or_overrides(tag):
    directory = Path(reverse_index_module.__file__).parent
    mappings = json.loads((directory / "gaap_mappings.json").read_text(encoding="utf-8"))
    assert tag not in mappings


@pytest.mark.parametrize("tag", PAYMENT_FAMILY)
@pytest.mark.parametrize("industry", INDUSTRIES)
def test_payment_family_remains_unmapped_in_each_namespace_and_industry(index, mapper, tag, industry):
    for prefix in PREFIXES:
        concept = f"{prefix}{tag}"
        assert index.lookup(concept, industry=industry) is None
        for statement_type in STATEMENT_TYPES:
            context = {"statement_type": statement_type, "industry": industry, "section": "Operating Activities"}
            assert index.get_standard_concept(concept, context, industry=industry) is None
            assert index.get_display_name(concept, context, industry=industry) is None
            assert mapper.mapping_store.get_standard_concept(concept, context) is None
            assert mapper.mapping_store.get_display_name(concept, context) is None
            assert mapper.map_concept(concept, "Cash paid component", context) is None
            rows = [
                {
                    "concept": concept,
                    "label": "Cash paid component",
                    "values": {"2025-12-31": value},
                    "statement_type": statement_type,
                    "calculation_parent": "us-gaap:NetCashProvidedByUsedInOperatingActivities",
                }
                for value in (123_456, -123_456, 0)
            ]
            assert standardize_statement(rows, mapper, industry=industry) == rows
            assert all("standard_concept" not in row for row in rows)


@pytest.mark.parametrize("concept, expected, display", NET_TOTALS)
@pytest.mark.parametrize("industry", INDUSTRIES)
def test_genuine_net_activity_totals_remain_mapped(index, concept, expected, display, industry):
    for statement_type in STATEMENT_TYPES:
        context = {"statement_type": statement_type, "industry": industry}
        assert index.get_standard_concept(concept, context, industry=industry) == expected
        assert index.get_display_name(concept, context, industry=industry) == display


# Exact IFRS taxonomy labels and labels retained in Apple FY2023, plus adversarial
# subtotal labels. These are API inputs, not new IFRS filing witnesses.
PAYMENT_LABELS = (
    "Cash paid for income taxes, net",
    "Cash paid for interest",
    "Income Taxes Paid, Net",
    "Income taxes paid (refund)",
    "Income taxes paid (refund), classified as financing activities",
    "Income taxes paid (refund), classified as investing activities",
    "Income taxes paid (refund), classified as operating activities",
    "Income taxes paid, classified as operating activities",
    "Income taxes refund, classified as operating activities",
    "Interest Paid, Excluding Capitalized Interest, Operating Activities",
    "Interest paid on deposit liabilities, classified as operating activities",
    "Interest paid, classified as financing activities",
    "Interest paid, classified as operating activities",
    "Net Cash from Financing Activities",
    "Net Cash from Operating Activities",
    "Total cash paid for taxes and interest",
)


@pytest.mark.parametrize("tag", CLASSIFIED_PAYMENTS)
@pytest.mark.parametrize("statement_type", STATEMENT_TYPES)
def test_payment_labels_cannot_infer_a_net_subtotal(mapper, tag, statement_type):
    for prefix in PREFIXES:
        concept = f"{prefix}{tag}"
        for label in PAYMENT_LABELS:
            # Clear negative cache so every label reaches the shipped store path.
            mapper._cache.clear()
            context = {"statement_type": statement_type, "section": "Operating Activities", "is_total": "total" in label.lower()}
            assert mapper.map_concept(concept, label, context) is None
            rows = [
                {
                    "concept": concept,
                    "label": label,
                    "statement_type": statement_type,
                    "values": {"2025-12-31": value},
                    "calculation_parent": "us-gaap:NetCashProvidedByUsedInOperatingActivities",
                }
                for value in (123_456, -123_456, 0)
            ]
            assert standardize_statement(rows, mapper) == rows
            assert all("standard_concept" not in row for row in rows)
