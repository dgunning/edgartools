"""
Regression test for bead edgartools-2tz1g: ``FactQuery.pivot_by_period(return_statement=False)``
set pandas' global ``display.float_format`` to ``'{:,.0f}'`` before returning.

Bead: edgartools-2tz1g

Every DataFrame printed afterwards in the same process lost its decimals, so
182.4 printed as 182. That kept main's network lane red from 2026-10-16: the
6byc pivot tests ran first, and the README test then could not find
"FY 2025 182.4 62.6 332.2" (README.md:89, JPM/PFE/XOM revenue in $ billions)
in the rendered frame.

Fix: the line is gone; a returned DataFrame does not change process-wide
display options.

Filing, offline: LPA (CIK 1997711) company facts, tests/fixtures/entity/lpa_facts.json.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from edgar.entity.parser import EntityFactsParser

pytestmark = [pytest.mark.regression]

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "lpa_facts.json"


def test_raw_pivot_leaves_the_global_float_format_alone():
    facts = EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))
    before = pd.get_option("display.float_format")

    pivot = facts.query().pivot_by_period(return_statement=False)

    assert isinstance(pivot, pd.DataFrame) and not pivot.empty
    assert pd.get_option("display.float_format") is before
    assert "182.4" in str(pd.DataFrame({"JPM": [182.4]}, index=["FY 2025"]))
