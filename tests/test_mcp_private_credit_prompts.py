"""Verify discovery and rendering of the private credit prompt workflows."""

import pytest

from edgar.ai.mcp.server import handle_get_prompt, handle_list_prompts
from edgar.ai.mcp.tools.prompts import get_prompt


@pytest.mark.asyncio
async def test_private_credit_prompts_are_discoverable():
    prompts = {prompt.name: prompt for prompt in await handle_list_prompts()}
    assert {a.name for a in prompts["borrower_credit_review"].arguments if a.required} == {"borrower", "bdc"}
    assert {a.name for a in prompts["lender_protection_review"].arguments if a.required} == {"borrower"}


@pytest.mark.asyncio
async def test_borrower_review_preserves_requested_periods():
    result = await handle_get_prompt("borrower_credit_review", {
        "borrower": "Ivy Hill",
        "bdc": "ARCC",
        "period": "2026-06-30",
        "comparison_period": "2025-06-30",
    })
    text = result.messages[0].content.text
    assert result.messages[0].role == "user"
    for value in ("Ivy Hill", "ARCC", "2026-06-30", "2025-06-30"):
        assert value in text


@pytest.mark.asyncio
async def test_protection_review_preserves_document_and_focus():
    result = await handle_get_prompt("lender_protection_review", {
        "borrower": "Example Borrower",
        "filing_or_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/agreement.htm",
        "focus": "guarantees and release provisions",
    })
    text = result.messages[0].content.text
    assert "agreement.htm" in text
    assert "guarantees and release provisions" in text


@pytest.mark.parametrize("name,arguments,missing", [
    ("borrower_credit_review", {"borrower": "Ivy Hill"}, "bdc"),
    ("lender_protection_review", {}, "borrower"),
])
def test_missing_required_input_gives_useful_error(name, arguments, missing):
    with pytest.raises(ValueError, match=f"requires arguments: {missing}"):
        get_prompt(name, arguments)


@pytest.mark.parametrize("name,arguments", [
    ("borrower_credit_review", {"borrower": "Ivy Hill", "bdc": "ARCC"}),
    ("lender_protection_review", {"borrower": "Example Borrower"}),
])
def test_optional_inputs_can_be_omitted(name, arguments):
    result = get_prompt(name, arguments)
    assert arguments["borrower"] in result.messages[0].content.text
