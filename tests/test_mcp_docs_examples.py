"""Check marked MCP tool-call examples against registered tool schemas."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from edgar.ai.mcp.server import _import_tools
from edgar.ai.mcp.tools.base import TOOLS

_import_tools()

ROOT = Path(__file__).parents[1]
DOC_PATHS = (
    ROOT / "docs/ai/mcp-tools.md",
    ROOT / "edgar/ai/mcp/docs/MCP_QUICKSTART.md",
    ROOT / "docs/ai/mcp-workflows.md",
)
DESCRIPTION_EXAMPLE_TOOLS = {
    "edgar_fund",
    "edgar_notes",
    "edgar_read",
    "edgar_filing",
    "edgar_text_search",
    "edgar_document",
}
MARKED_JSON = re.compile(
    r"<!--\s*MCP_TOOL_CALL_EXAMPLE\s*-->\s*```json\s*(.*?)\s*```",
    flags=re.DOTALL,
)


def _extract_examples(source: str, content: str) -> list[dict[str, Any]]:
    """Decode every marked JSON tool call in one documentation source."""
    examples = []
    for match in MARKED_JSON.finditer(content):
        try:
            example = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{source}: invalid marked tool-call JSON: {exc}") from exc
        assert isinstance(example, dict), f"{source}: marked tool call must be an object"
        assert set(example) == {"tool", "arguments"}, (
            f"{source}: marked tool call must contain only 'tool' and 'arguments'"
        )
        assert isinstance(example["tool"], str), f"{source}: tool name must be a string"
        assert isinstance(example["arguments"], dict), f"{source}: arguments must be an object"
        example["_source"] = source
        examples.append(example)
    return examples


def _check_value(path: str, value: Any, schema: dict[str, Any]) -> None:
    """Check enums and nested object fields from a JSON Schema property."""
    enum = schema.get("enum")
    if enum is not None:
        assert value in enum, f"{path}: {value!r} is not one of {enum}"

    if schema.get("type") == "array":
        assert isinstance(value, list), f"{path}: expected an array"
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            _check_value(f"{path}[{index}]", item, item_schema)
    elif schema.get("type") == "object":
        assert isinstance(value, dict), f"{path}: expected an object"
        properties = schema.get("properties", {})
        missing = set(schema.get("required", ())) - set(value)
        assert not missing, f"{path}: missing required fields {sorted(missing)}"
        unknown = set(value) - set(properties)
        assert not unknown, f"{path}: unknown fields {sorted(unknown)}"
        for key, item in value.items():
            _check_value(f"{path}.{key}", item, properties[key])


def _has_filing_selector(tool_name: str, arguments: dict[str, Any]) -> bool:
    if tool_name == "edgar_filing":
        return bool(arguments.get("input")) or bool(
            arguments.get("identifier") and arguments.get("form")
        )
    if tool_name in {"edgar_read", "edgar_notes"}:
        return bool(arguments.get("accession_number") or arguments.get("identifier"))
    if tool_name == "edgar_document":
        return bool(arguments.get("accession_number") or arguments.get("url"))
    if tool_name == "edgar_fund" and arguments.get("action") in {
        "bdc_portfolio",
        "bdc_nonaccrual",
    }:
        return bool(arguments.get("accession_number") or arguments.get("identifier"))
    return True


def _check_conditional_selectors(tool_name: str, arguments: dict[str, Any], source: str) -> None:
    """Validate selector requirements that JSON Schema cannot express."""
    prefix = f"{source}: {tool_name}"
    action = arguments.get("action")

    if not _has_filing_selector(tool_name, arguments):
        raise AssertionError(f"{prefix} example must include a filing selector")

    if tool_name == "edgar_filing":
        assert arguments.get("input") or (arguments.get("identifier") and arguments.get("form")), (
            f"{prefix} needs input or both identifier and form"
        )
    elif tool_name == "edgar_read":
        if arguments.get("identifier"):
            assert arguments.get("form"), f"{prefix} needs form with identifier"
        if arguments.get("period"):
            assert arguments.get("identifier") and arguments.get("form"), (
                f"{prefix} needs identifier and form with period"
            )
        if arguments.get("cursor"):
            sections = arguments.get("sections")
            assert isinstance(sections, list) and len(sections) == 1, (
                f"{prefix} cursor needs the original single section"
            )
    elif tool_name == "edgar_notes":
        if arguments.get("period"):
            assert arguments.get("identifier") and arguments.get("form"), (
                f"{prefix} needs identifier and form with period"
            )
        if arguments.get("cursor"):
            assert arguments.get("topic") and arguments.get("detail"), (
                f"{prefix} cursor needs the original topic and detail"
            )
    elif tool_name == "edgar_fund":
        if action == "bdc_search":
            assert arguments.get("query"), f"{prefix} bdc_search needs query"
        if arguments.get("cursor"):
            assert action in {"bdc_portfolio", "bdc_nonaccrual"}, (
                f"{prefix} cursor requires a pageable BDC action"
            )
    elif tool_name == "edgar_document":
        if action == "search":
            assert arguments.get("query"), f"{prefix} search needs query"
        if action == "read":
            assert arguments.get("document") or arguments.get("url"), (
                f"{prefix} read needs an exact document or SEC document URL"
            )
        if arguments.get("cursor") and action == "read":
            assert arguments.get("document") or arguments.get("url"), (
                f"{prefix} read cursor needs the original document selector"
            )


def _check_source_examples(source: str, examples: list[dict[str, Any]]) -> None:
    """Validate source examples and require cursor calls to repeat identity."""
    prior_calls = []
    for example in examples:
        tool_name = example["tool"]
        arguments = example["arguments"]
        assert tool_name in TOOLS, f"{source}: '{tool_name}' is not a registered MCP tool"
        schema = TOOLS[tool_name]["schema"]
        properties = schema.get("properties", {})
        missing = set(schema.get("required", ())) - set(arguments)
        assert not missing, f"{source}: {tool_name} missing required fields {sorted(missing)}"
        unknown = set(arguments) - set(properties)
        assert not unknown, f"{source}: {tool_name} uses unknown fields {sorted(unknown)}"
        for key, value in arguments.items():
            _check_value(f"{source}: {tool_name}.{key}", value, properties[key])
        _check_conditional_selectors(tool_name, arguments, source)

        if arguments.get("cursor"):
            base_arguments = {key: value for key, value in arguments.items() if key != "cursor"}
            assert any(
                prior["tool"] == tool_name and prior["arguments"] == base_arguments
                for prior in prior_calls
            ), (
                f"{source}: {tool_name} cursor example must repeat the exact filing selector "
                "and query/topic/detail/section arguments from its prior call"
            )
        else:
            prior_calls.append(example)


def _all_marked_examples() -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Read marked examples from scoped docs and every registered description."""
    doc_examples = {
        str(path.relative_to(ROOT)): _extract_examples(str(path.relative_to(ROOT)), path.read_text())
        for path in DOC_PATHS
    }
    description_examples = {
        name: _extract_examples(f"{name} description", info["description"])
        for name, info in TOOLS.items()
    }
    return doc_examples, description_examples


@pytest.mark.fast
def test_marked_examples_match_registered_schemas_and_continuation_identity():
    doc_examples, description_examples = _all_marked_examples()
    assert len(TOOLS) == 14, f"expected 14 registered tools, found {len(TOOLS)}"

    for source, examples in doc_examples.items():
        assert examples, f"{source}: no marked JSON tool-call examples found"
        _check_source_examples(source, examples)

    for name in DESCRIPTION_EXAMPLE_TOOLS:
        examples = description_examples[name]
        assert examples, f"{name} description has no marked JSON tool-call example"
        _check_source_examples(f"{name} description", examples)

    for examples in description_examples.values():
        if examples:
            _check_source_examples(examples[0]["_source"], examples)


@pytest.mark.fast
def test_checker_rejects_cursor_example_missing_original_filing_selector():
    source = "self-check"
    examples = [
        {
            "tool": "edgar_read",
            "arguments": {
                "identifier": "ARCC",
                "form": "10-Q",
                "period": "2026-06-30",
                "sections": ["mda"],
            },
            "_source": source,
        },
        {
            "tool": "edgar_read",
            "arguments": {"sections": ["mda"], "cursor": "<next_cursor>"},
            "_source": source,
        },
    ]

    with pytest.raises(AssertionError, match="filing selector"):
        _check_source_examples(source, examples)
