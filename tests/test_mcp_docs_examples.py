"""
Verify documented MCP tool examples against the tools' registered schemas.

`docs/ai/mcp-tools.md` and each tool's own `description=` text (in
`edgar/ai/mcp/tools/fund.py`, `notes.py`, `reader.py`) show example calls
like `action="bdc_portfolio", identifier="ARCC", form="10-Q",
period="2026-06-30"`. Nothing enforces that those examples actually use
parameter names (and enum values) the tool accepts -- a rename or a typo in
the docs would silently teach an agent to call the tool wrong. This module
is the enforcement: it re-derives one dict per documented example and checks
every key against `TOOLS[tool_name]["schema"]["properties"]`, and every
value against that property's `enum` when one is declared.

Fast, no network: importing the tool modules only registers `@tool`
decorators; it makes no request.
"""
from __future__ import annotations

import pytest

from edgar.ai.mcp.server import _import_tools
from edgar.ai.mcp.tools.base import TOOLS

_import_tools()


def _check_example(tool_name: str, params: dict) -> None:
    """Assert `params` are all valid arguments for `tool_name`'s schema.

    Raises AssertionError naming exactly what is wrong -- the unknown
    parameter, or the out-of-enum value -- so a failure points straight at
    the doc/description line that needs fixing.
    """
    assert tool_name in TOOLS, f"'{tool_name}' is not a registered MCP tool"
    properties = TOOLS[tool_name]["schema"]["properties"]

    for key, value in params.items():
        assert key in properties, (
            f"{tool_name}: documented example uses unknown parameter '{key}' "
            f"(known parameters: {sorted(properties)})"
        )
        enum = properties[key].get("enum")
        if enum is not None:
            assert value in enum, (
                f"{tool_name}.{key}: documented example value {value!r} "
                f"is not one of {enum}"
            )


# One entry per example call documented in docs/ai/mcp-tools.md and/or in
# the tool's own `description=` text. Keep this list in sync with those
# docs -- each entry here is a claim that some real doc text uses exactly
# this argument set.
DOCUMENTED_EXAMPLES: list[tuple[str, dict]] = [
    # edgar_fund: bdc_search / bdc_portfolio / bdc_nonaccrual
    ("edgar_fund", {"action": "bdc_search", "query": "Ares"}),
    ("edgar_fund", {"action": "bdc_portfolio", "identifier": "ARCC"}),
    (
        "edgar_fund",
        {"action": "bdc_portfolio", "identifier": "ARCC", "form": "10-Q", "period": "2026-06-30"},
    ),
    (
        "edgar_fund",
        {"action": "bdc_portfolio", "accession_number": "0001628280-26-050307"},
    ),
    (
        "edgar_fund",
        {"action": "bdc_portfolio", "identifier": "ARCC", "borrower": "Ivy Hill"},
    ),
    (
        "edgar_fund",
        {"action": "bdc_portfolio", "identifier": "ARCC", "cursor": "<page.next_cursor from the previous call>"},
    ),
    (
        "edgar_fund",
        {"action": "bdc_nonaccrual", "identifier": "ARCC", "form": "10-Q", "period": "2026-06-30"},
    ),
    # edgar_notes: chosen period / accession / cursor continuation
    (
        "edgar_notes",
        {"topic": "debt", "identifier": "ARCC", "form": "10-Q", "period": "2026-06-30"},
    ),
    (
        "edgar_notes",
        {"topic": "debt", "accession_number": "0001628280-26-050307"},
    ),
    (
        "edgar_notes",
        {"cursor": "<next_cursor from a previous call>"},
    ),
    # edgar_read: chosen period / cursor continuation
    (
        "edgar_read",
        {"identifier": "ARCC", "form": "10-Q", "period": "2026-06-30", "sections": ["mda"]},
    ),
    (
        "edgar_read",
        {"sections": ["mda"], "cursor": "<next_cursor from a previous call>"},
    ),
]


@pytest.mark.fast
@pytest.mark.parametrize(
    "tool_name,params",
    DOCUMENTED_EXAMPLES,
    ids=[f"{name}:{sorted(params)}" for name, params in DOCUMENTED_EXAMPLES],
)
def test_documented_example_uses_valid_params(tool_name, params):
    _check_example(tool_name, params)


@pytest.mark.fast
def test_checker_rejects_unknown_parameter():
    """Self-check: an unknown parameter name must fail, proving the
    checker above is not vacuously true."""
    with pytest.raises(AssertionError, match="unknown parameter"):
        _check_example("edgar_fund", {"action": "bdc_portfolio", "borrowerr": "Ivy Hill"})


@pytest.mark.fast
def test_checker_rejects_invalid_enum_value():
    """Self-check: a value outside a declared enum must fail."""
    with pytest.raises(AssertionError, match="is not one of"):
        _check_example("edgar_fund", {"action": "bdc_portfolio", "form": "10-K/A"})
