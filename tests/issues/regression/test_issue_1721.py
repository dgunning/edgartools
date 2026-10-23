"""edgar_company and edgar_trends reported Python AttributeError text for a company with no facts.

``Entity.get_facts()`` returns None when the SEC has no XBRL company facts.
Circuit City Stores (CIK 104599, last 10-K filed 2008) is such a company. The
handlers called ``facts.income_statement(...)`` and ``facts.time_series(...)`` on
None and put ``'NoneType' object has no attribute ...`` into a ``success: true``
response with ``error_code: null``.

They now say the facts are missing, with the documented ``NO_FACTS_DATA`` code
(``edgar/ai/skills/core/sharp-edges.yaml``, ``error-code-handling``).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1721
"""
import pytest

from edgar import Company
from edgar.ai.mcp.tools import company as company_tool  # noqa: F401  (registers edgar_company)
from edgar.ai.mcp.tools import compare as compare_tool  # noqa: F401  (registers edgar_compare)
from edgar.ai.mcp.tools import trends as trends_tool  # noqa: F401  (registers edgar_trends)
from edgar.ai.mcp.tools.base import call_tool_handler

CIRCUIT_CITY_CIK = 104599


@pytest.mark.vcr
async def test_issue_1721_circuit_city_has_no_company_facts():
    """Ground truth: SEC returns no companyfacts document for CIK 104599."""
    assert Company(CIRCUIT_CITY_CIK).get_facts() is None


@pytest.mark.vcr
async def test_issue_1721_edgar_company_reports_missing_facts():
    response = await call_tool_handler(
        "edgar_company", {"identifier": str(CIRCUIT_CITY_CIK), "include": ["financials"]})
    financials = response.data["financials"]
    assert financials["error_code"] == "NO_FACTS_DATA"
    assert financials["error"] == "No company facts found for CIK 104599"
    assert "income_statement" not in financials
    assert "NoneType" not in str(response.data)
    # Visible from the top level of the data, in the list edgar_compare uses
    assert response.data["errors"] == [{
        "section": "financials", "error": "No company facts found for CIK 104599",
        "error_code": "NO_FACTS_DATA"}]
    assert not any("edgar_compare" in step for step in response.next_steps)


@pytest.mark.vcr
async def test_issue_1721_edgar_trends_reports_missing_facts():
    response = await call_tool_handler(
        "edgar_trends", {"identifier": str(CIRCUIT_CITY_CIK), "concepts": ["revenue"]})
    assert response.success is False
    assert response.error_code == "NO_FACTS_DATA"
    assert response.error == "No company facts found for CIK 104599"
    assert response.suggestions


@pytest.mark.vcr
async def test_issue_1721_edgar_compare_reports_missing_facts():
    """Every metric used to be skipped silently, leaving a success with no metrics."""
    response = await call_tool_handler(
        "edgar_compare", {"identifiers": [str(CIRCUIT_CITY_CIK), str(CIRCUIT_CITY_CIK)]})
    assert response.data["companies"] == []
    assert [e["error_code"] for e in response.data["errors"]] == ["NO_FACTS_DATA"] * 2
    assert response.data["errors"][0]["error"] == "No company facts found for CIK 104599"
