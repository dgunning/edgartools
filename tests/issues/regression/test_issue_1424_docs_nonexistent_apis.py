"""
The docs named APIs that do not exist, and mislabeled two statement views.

Each of these raised on 5.60.0 the moment a reader ran it:

- ``xbrl.query().by_statement(...)``: the method is ``by_statement_type``.
- ``xbrl.query().by_dimensions({...})``: only ``by_dimension(axis, member)``
  exists, one axis per call, chained.
- ``Statement.get_concept_value(...)`` and ``.get_value(...)``: ``Statement``
  has no per-concept getter; values come from ``to_dataframe()``.
- ``for fact in xbrl.facts``: ``FactsView`` is not iterable. Beside it,
  ``xbrl.statements.get("Revenues")`` looks up a statement, not a concept,
  and answers ``None``.
- ``xbrl.facts.by_concept(...)``: the filters are ``FactQuery`` methods,
  reached through ``xbrl.facts.query()`` or ``xbrl.query()``.
- ``SynonymGroups.to_json()`` and ``.from_json()``: they are
  ``export_to_json()`` and ``from_file()``.

Two more were values rather than names, so nothing raised:

- ``menucat`` was documented as single letters (``S``, ``D``, ...). It carries
  the FilingSummary ``MenuCategory`` name, so ``calc[calc.menucat == 'S']``,
  the recipe in the shipped xbrl skill, matched no rows.
- financial-data.md said ``summary`` "matches SEC Viewer" and marked
  ``standard`` "(default)". ``summary`` drops every dimensional row, including
  the Products and Services lines on the face of Apple's income statement, and
  ``standard`` is the default only when a statement is printed:
  ``to_dataframe()`` returns ``detailed``. On NVIDIA's FY2026 10-K
  (0001045810-26-000021) that is 21, 29 and 45 rows, and ``to_dataframe()``
  returns the 45.

The corrected examples run here, as written in the docs, against committed
fixtures, and the touched pages are checked for calls that do not exist.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1424
"""

import re

import pytest
import yaml

from edgar.company_reports import TenK
from edgar.sgml.filing_summary import FilingSummary
from edgar.standardization.synonym_groups import SynonymGroups
from edgar.xbrl import XBRL
from edgar.xbrl.facts import FactQuery, FactsView
from edgar.xbrl.statements import Statement
from tests.paths import FIXTURES_DIR, REPO_ROOT

# NVIDIA FY2026 10-K, 0001045810-26-000021: the filing the issue measured.
NVDA_FY2026 = FIXTURES_DIR / "xbrl" / "nvda" / "10k_2026"
# Apple FY2023 10-K, 0000320193-23-000106: Products and Services on the face.
AAPL_FY2023 = FIXTURES_DIR / "xbrl" / "aapl" / "10k_2023"
# Microsoft FY2024 10-K, 0000950170-24-087843.
MSFT_FY2024 = FIXTURES_DIR / "xbrl" / "msft" / "10k_2024"
# Apple's 10-Q for the quarter ended 2025-03-29, 0000320193-25-000057.
AAPL_FILING_SUMMARY = FIXTURES_DIR / "attachments" / "aapl" / "20250329" / "FilingSummary.xml"

API_REFERENCE = "docs/api/xbrl.md"
QUERYING_GUIDE = "docs/xbrl-querying.md"
FINANCIAL_DATA_GUIDE = "docs/guides/financial-data.md"
SKILL = "edgar/ai/skills/xbrl/skill.yaml"

TOUCHED_PAGES = [
    API_REFERENCE,
    QUERYING_GUIDE,
    FINANCIAL_DATA_GUIDE,
    SKILL,
    "docs/concepts/data-objects.md",
    "docs/getting-xbrl.md",
    "docs/resources/troubleshooting.md",
    "docs/verification-guide.md",
    "docs/xbrl/concepts/dimension-handling.md",
    "docs/xbrl/getting-started/choosing-the-right-api.md",
    "edgar/standardization/README.md",
]

# A call a page made, and the class it has to exist on for the call to work.
# The pattern captures the attribute; an explicit attribute overrides it.
DOCUMENTED_CALLS = [
    (r"\.(by_statement|by_dimensions|by_period)\(", FactQuery, None),
    (r"\bquery\.(first|count)\(", FactQuery, None),
    (r"\.facts\s*\.(by_\w+)\(", FactsView, None),
    (r"for \w+ in \w+\.facts\s*:", FactsView, "__iter__"),
    (r"\.(get_concept_value|get_value)\(", Statement, None),
    (r"\b(?:synonyms|SynonymGroups)\.(to_json|from_json|to_dict)\(", SynonymGroups, None),
    (r"\.(period_end_date)\b", TenK, None),
]


def read(page):
    return (REPO_ROOT / page).read_text(encoding="utf-8")


def run_documented_block(page, marker, **names):
    """Execute, as written, the one ```python block on `page` containing `marker`."""
    blocks = [b for b in re.findall(r"```python\n(.*?)```", read(page), re.DOTALL) if marker in b]
    assert len(blocks) == 1, f"{page}: expected one python block containing {marker!r}, found {len(blocks)}"
    namespace = dict(names)
    exec(compile(blocks[0], page, "exec"), namespace)  # noqa: S102 - our own documentation
    return namespace


@pytest.fixture(scope="module")
def nvda():
    return XBRL.from_directory(NVDA_FY2026)


@pytest.fixture(scope="module")
def aapl():
    return XBRL.from_directory(AAPL_FY2023)


@pytest.mark.parametrize("page", TOUCHED_PAGES)
def test_pages_call_only_methods_that_exist(page):
    text = read(page)
    missing = set()
    for pattern, owner, attribute in DOCUMENTED_CALLS:
        for match in re.finditer(pattern, text):
            name = attribute or match.group(1)
            if not hasattr(owner, name):
                missing.add(f"{owner.__name__}.{name}")
    assert not missing, f"{page} calls what does not exist: {sorted(missing)}"


# --- Views: what each one is, and which is the default where ---------------------


def test_to_dataframe_defaults_to_detailed_and_printing_to_standard(nvda):
    income = nvda.statements.income_statement()

    rows = {view: len(income.to_dataframe(view=view)) for view in ("summary", "standard", "detailed")}
    assert rows == {"summary": 21, "standard": 29, "detailed": 45}
    assert list(income.to_dataframe()["label"]) == list(income.to_dataframe(view="detailed")["label"])
    assert len(income.render().rows) == len(income.render(view="standard").rows) == 29


def test_summary_drops_the_face_lines_standard_keeps(aapl):
    income = aapl.statements.income_statement()
    summary = income.to_dataframe(view="summary")
    standard = income.to_dataframe(view="standard")

    assert not summary["dimension"].any()
    face_products = standard[standard["dimension"] & (standard["label"] == "Products")]
    assert face_products["2023-09-30 (FY)"].tolist() == [298_085_000_000, 189_282_000_000]
    assert "Products" not in set(summary["label"])


def test_financial_data_guide_no_longer_calls_summary_the_sec_viewer():
    for line in read(FINANCIAL_DATA_GUIDE).splitlines():
        if "summary" in line.lower():
            assert "SEC Viewer" not in line, line


def test_financial_data_guide_names_the_to_dataframe_default():
    row = next(line for line in read(FINANCIAL_DATA_GUIDE).splitlines() if line.startswith("| `statement.to_dataframe()` |"))
    assert "detailed" in row, row


# --- Statement values: read from the DataFrame -----------------------------------


def test_reading_values_example(aapl):
    ns = run_documented_block(API_REFERENCE, "# Get specific values from the newest period", xbrl=aapl)

    assert ns["period"] == "2023-09-30 (FY)"
    assert ns["revenue"] == 383_285_000_000
    assert ns["net_income"] == 96_995_000_000


def test_statements_example_prints_filed_values(aapl, capsys):
    run_documented_block(API_REFERENCE, "def latest_value", xbrl=aapl)

    out = capsys.readouterr().out
    assert "Total Assets: 352583000000.0" in out
    assert "Revenue: 383285000000.0" in out


def test_research_and_development_example(aapl):
    ns = run_documented_block("docs/getting-xbrl.md", "def rnd(statement)", msft_xbrl=XBRL.from_directory(MSFT_FY2024), aapl_xbrl=aapl)

    assert ns["msft_rnd"] == 29_510_000_000
    assert ns["aapl_rnd"] == 29_915_000_000


@pytest.mark.parametrize(
    "fixture,concept,revenue",
    [
        ("aapl", "RevenueFromContractWithCustomerExcludingAssessedTax", 383_285_000_000),
        ("nvda", "Revenues", 215_938_000_000),
    ],
)
def test_troubleshooting_concept_fallback(fixture, concept, revenue, request):
    xbrl = request.getfixturevalue(fixture)
    ns = run_documented_block("docs/resources/troubleshooting.md", 'for concept in ["Revenues"', income_stmt=xbrl.statements.income_statement())

    assert ns["concept"] == concept
    assert ns["revenue"] == revenue


def test_segment_breakdown_is_the_detailed_view_not_a_statement_lookup(aapl):
    assert aapl.statements.get("Revenues") is None

    detailed = aapl.statements.income_statement(view="detailed").to_dataframe()
    assert detailed[detailed["label"] == "iPhone"]["2023-09-30 (FY)"].tolist() == [200_583_000_000]
    assert 'statements.get("Revenues")' not in read("docs/xbrl/getting-started/choosing-the-right-api.md")


# --- Fact queries ----------------------------------------------------------------


def test_fact_query_example(nvda):
    ns = run_documented_block(API_REFERENCE, "count = len(facts_list)", xbrl=nvda)

    facts = ns["facts_list"]
    assert ns["count"] == len(facts) > 0
    assert all(re.search("revenue", f["concept"], re.IGNORECASE) for f in facts)
    assert all(f["numeric_value"] >= 1_000_000 for f in facts)
    assert all(f["period_start"] >= "2023-01-01" for f in facts)
    assert 215_938_000_000 in {f["numeric_value"] for f in facts}


def test_facts_view_example(nvda):
    ns = run_documented_block(API_REFERENCE, "large_expenses = facts.query()", xbrl=nvda)

    assert len(ns["revenue_facts"]) > 0
    assert 215_938_000_000 in set(ns["revenue_ts"]["numeric_value"])
    assert not ns["pivot_df"].empty


def test_querying_guide_chains_by_statement_type(nvda):
    ns = run_documented_block(QUERYING_GUIDE, "complex_query = (xbrl.query()", xbrl=nvda)

    results = ns["results"]
    assert len(results) == 10
    for fact in results:
        assert "IncomeStatement" in fact["statement_types"]
        assert fact["numeric_value"] > 1_000_000


def test_querying_guide_chains_by_dimension(aapl):
    ns = run_documented_block(QUERYING_GUIDE, "multi_dim = (xbrl.query()", xbrl=aapl)

    products = ns["dimensional_query"].execute()
    revenue = {f["numeric_value"] for f in products if f["concept"] == "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"}
    assert 298_085_000_000 in revenue
    # Each by_dimension() narrows the query further.
    assert len(ns["multi_dim"].execute()) <= len(products)


# --- menucat ----------------------------------------------------------------------


def test_menucat_values_are_filing_summary_category_names():
    # XBRL.from_filing copies MenuCategory verbatim for every report with a role.
    summary = FilingSummary.parse(AAPL_FILING_SUMMARY.read_text(encoding="utf-8"))
    categories = {report.menu_category for report in summary.reports if report.role and report.menu_category}
    assert categories == {"Cover", "Details", "Notes", "Policies", "Statements", "Tables"}

    docstring = XBRL.calculation_linkbase.__doc__ or ""
    reference_row = next(line for line in read(API_REFERENCE).splitlines() if line.startswith("| `menucat` |"))
    for documented in (docstring, reference_row):
        assert all(f"`{name}`" in documented for name in categories)
        assert "`S`=" not in documented

    skill = yaml.safe_load(read(SKILL))
    recipe = next(p["code"] for p in skill["patterns"] if p["name"] == "Calculation Linkbase as DataFrame")
    filtered_on = re.findall(r"menucat == '([^']*)'", recipe)
    assert filtered_on == ["Statements"]


# --- SynonymGroups JSON ------------------------------------------------------------


def test_synonym_groups_json_example(tmp_path, monkeypatch):
    page = "edgar/standardization/README.md"
    monkeypatch.chdir(tmp_path)
    register = run_documented_block(page, "name='custom_capex'", SynonymGroups=SynonymGroups)
    ns = run_documented_block(page, "export_to_json", SynonymGroups=SynonymGroups, synonyms=register["synonyms"])

    assert "custom_capex" in ns["synonyms"]
    assert ns["data"]["synonyms"] == [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "CapitalExpenditures",
        "PurchaseOfPropertyPlantAndEquipment",
    ]
