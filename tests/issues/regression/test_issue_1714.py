"""Examples in the XBRL AI skill raised, returned zero rows or filtered nothing.

``edgar/ai/skills/xbrl/skill.yaml`` and ``sharp-edges.yaml`` taught ``xbrl.fiscal_year`` and
``xbrl.statements.names`` (``AttributeError``), ``get_facts_by_concept("Assets", exact=True)``
and ``facts_history("Revenue")`` (0 rows: exact matching needs the filed QName with its
prefix), ``fact['unit']`` (``KeyError``: the key is ``unit_ref``), a ``dimensions`` key that
does not exist (so ``not f.get('dimensions')`` kept every fact), and ``fact['period_end']``
on instant facts (which carry ``period_instant``).

The corrected code is executed here as written in the two files, against Apple's FY2023
10-K XBRL (tracked fixture).

Ground truth: Apple FY2023 10-K, accession 0000320193-23-000106, balance sheet: total
assets $352,583 million at 2023-09-30 and $352,755 million at 2022-09-24 (tagged
us-gaap:Assets 352583000000 and 352755000000); net sales $383,285 million for the
year (us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1714
"""
import contextlib
import io
import re
import types

import pytest
import yaml

from edgar.financials import Financials
from edgar.xbrl import XBRL
from tests.paths import FIXTURES_DIR, REPO_ROOT

AAPL_FY2023 = FIXTURES_DIR / "xbrl" / "aapl" / "10k_2023"
SKILL = REPO_ROOT / "edgar/ai/skills/xbrl/skill.yaml"
EDGES = REPO_ROOT / "edgar/ai/skills/xbrl/sharp-edges.yaml"
REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"


@pytest.fixture(scope="module")
def xbrl():
    return XBRL.from_directory(AAPL_FY2023)


def pattern(name):
    return next(p["code"] for p in yaml.safe_load(SKILL.read_text(encoding="utf-8"))["patterns"]
                if p["name"] == name)


def edge(edge_id):
    return next(e["solution"] for e in yaml.safe_load(EDGES.read_text(encoding="utf-8"))["sharp_edges"]
                if e["id"] == edge_id)


def run(code, xbrl):
    filing = types.SimpleNamespace(xbrl=lambda: xbrl)
    company = types.SimpleNamespace(get_filings=lambda form: [filing],
                                    get_financials=lambda: Financials(xbrl))
    ns = {"xbrl": xbrl, "company": company, "filing": filing}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(code, "skill", "exec"), ns)  # noqa: S102 - our own documentation
    return ns, out.getvalue()


@pytest.mark.fast
def test_get_xbrl_object_and_statements_patterns_run(xbrl):
    run(pattern("Get XBRL Object"), xbrl)
    assert (xbrl.entity_info["fiscal_year"], xbrl.entity_info["fiscal_period"]) == ("2023", "FY")
    ns, _ = run(pattern("Statements"), xbrl)
    names = list(xbrl.statements.statement_by_type)
    assert names[:2] == ["CoverPage", "IncomeStatement"] and "BalanceSheet" in names


@pytest.mark.fast
def test_facts_access_pattern_runs_and_exact_needs_the_prefix(xbrl):
    ns, _ = run(pattern("Facts Access"), xbrl)
    assert ns["facts"].get_facts_by_concept("us-gaap:Assets", exact=True)["numeric_value"].tolist() == \
        [352_583_000_000, 352_755_000_000]
    assert len(ns["facts"].get_facts_by_concept("Assets", exact=True)) == 0


@pytest.mark.fast
def test_concept_history_uses_the_qualified_concept(xbrl):
    ns, _ = run(pattern("Concept History"), xbrl)
    history = ns["history"]
    assert len(history) == 45
    totals = history[history["label"] == "Net sales"]
    assert totals.sort_values("period_end")["numeric_value"].iloc[-1] == 383_285_000_000
    assert len(xbrl.facts.facts_history("Revenue")) == 0


@pytest.mark.fast
def test_raw_fact_details_keys_exist(xbrl):
    ns, _ = run(pattern("Raw Fact Details"), xbrl)
    facts = ns["all_facts"]
    assert all("unit_ref" in f and "is_dimensioned" in f for f in facts)
    assert not any("unit" in f or "dimensions" in f for f in facts)
    assert all(("period_end" in f) != ("period_instant" in f) for f in facts)
    assert {f["currency"] for f in facts if f.get("unit_ref") == "usd"} == {"USD"}


@pytest.mark.fast
def test_sharp_edge_examples_run(xbrl):
    run(edge("concept-name-variance"), xbrl)

    ns, _ = run(edge("dimensional-facts-complexity"), xbrl)
    facts, totals_only = ns["facts"], ns["totals_only"]
    assert 0 < len(totals_only) < len(facts)
    assert not any(f["is_dimensioned"] for f in totals_only)

    _, printed = run(edge("period-vs-instant"), xbrl)
    assert "As of 2023-09-30" in printed and "2022-09-25 to 2023-09-30" in printed

    ns, printed = run(edge("units-and-decimals"), xbrl)
    assert "Unit: usd, Currency: USD" in printed
    assert "Unit: shares, Currency: None" in printed


QUERYING_GUIDE = "docs/xbrl-querying.md"
EQUITY_GUIDE = "docs/guides/equity-statement-data-layers.md"


def _exact_concepts(page):
    text = "\n".join(re.findall(r"```python\n(.*?)```", (REPO_ROOT / page).read_text(encoding="utf-8"), re.DOTALL))
    return re.findall(r'by_concept\(["\']([^"\']+)["\'],\s*exact=True\)', text)


@pytest.mark.fast
@pytest.mark.parametrize("page", [QUERYING_GUIDE, EQUITY_GUIDE])
def test_docs_name_exact_concepts_with_their_prefix(page, xbrl):
    """``exact=True`` matches the filed QName, so an unqualified name returns 0 rows."""
    concepts = _exact_concepts(page)
    assert concepts, page
    assert all(":" in concept for concept in concepts), concepts
    assert len(xbrl.facts.query().by_concept("Assets", exact=True).to_dataframe()) == 0
    assert len(xbrl.facts.query().by_concept("us-gaap:Assets", exact=True).to_dataframe()) == 2


@pytest.mark.fast
def test_querying_guide_no_longer_says_exact_matches_without_a_prefix():
    text = " ".join((REPO_ROOT / QUERYING_GUIDE).read_text(encoding="utf-8").split())
    assert "An exact match needs the prefix" in text
    assert "The namespace e.g. `us-gaap:` is optional, so" not in text


@pytest.mark.fast
def test_equity_guide_concepts_are_queryable(xbrl):
    """The guide's own concepts, run as written (Apple FY2023 has no repurchase-program note, so 0 rows)."""
    concepts = _exact_concepts(EQUITY_GUIDE)
    assert len(concepts) == 5
    for concept in concepts:
        assert concept.startswith("us-gaap:")
        xbrl.facts.query().by_concept(concept, exact=True).to_dataframe()
