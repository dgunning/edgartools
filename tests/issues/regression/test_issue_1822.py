"""Regression test for GitHub Issue #1822.

``income_statement(period="ttm")`` raised ``ValueError: Insufficient data for TTM
trend: need at least 4 quarters, found 1 quarters`` for e.l.f. Beauty at every
``periods`` value, although its revenue has dozens of quarters.

The statement builder picks its period columns from the first concept whose
trend is labelled Q1..Q4. ELF's FY2026 10-K re-files earlier quarters tagged
``fiscal_period="FY"``, and those copies win de-duplication, so every preferred
concept (revenue, net income) is rejected. The builder then tried each line
item in turn, without the ``except (ValueError, KeyError)`` its item loop has,
and the first sparse one (BusinessCombinationAcquisitionRelatedCosts, 2 facts)
raised for the whole statement.

Choosing the columns now skips a concept it cannot use. The FY labels on ELF's
re-filed quarters are a separate problem (bead edgartools-r3hxg); until that is
fixed, Total Revenue has a value only in the newest column.

The fixture is SEC companyfacts for CIK 1600033, downloaded 2026-11-01.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1822
"""
import json
from pathlib import Path

import pytest

from edgar.entity.parser import EntityFactsParser

pytestmark = pytest.mark.regression

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "elf_facts.json"


@pytest.fixture(scope="module")
def elf_facts():
    return EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))


@pytest.mark.parametrize("periods", [4, 8])
def test_ttm_income_statement_builds(elf_facts, periods):
    statement = elf_facts.income_statement(period="ttm", periods=periods)
    assert len(statement.periods) == periods
    assert all(fp in {"Q1", "Q2", "Q3", "Q4"} for _, fp in statement.periods)


def test_fiscal_year_end_ttm_equals_the_10k_annual_total(elf_facts):
    """ELF's FY2026 10-K (accession 0001600033-26-000020) reports
    CostOfGoodsAndServicesSold of 479,125,000 for 2025-04-01..2026-03-31,
    and the TTM ending at fiscal Q4 2026 is that same twelve months."""
    statement = elf_facts.income_statement(period="ttm", periods=8)
    rows = {item["concept"].split(":")[-1]: item["values"] for item in statement.items}
    assert rows["CostOfGoodsAndServicesSold"]["Q4 2026"] == 479_125_000
