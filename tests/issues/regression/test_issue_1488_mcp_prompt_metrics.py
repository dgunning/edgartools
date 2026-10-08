"""Explicit built-in MCP prompt requests must pass registered input validation.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1488

These user-initiated templates guide clients; they do not execute tools. Render
every registered prompt, including both filing-comparison branches, then read
the shipped explicit argument syntax and submit representative requests through
the real MCP SDK. Synthetic identifiers, peers, holdings, a previous accession,
and a fund-family query fill choices that normally require earlier tool results.
Only downstream handlers are replaced. Admission proves the input contract,
not SEC availability, section existence, financial values, or arbitrary prose
interpretation by an LLM.
"""

import json
import re
import socket
from datetime import timedelta

import pytest
import pytest_asyncio
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import GetPromptResult, TextContent

from edgar.ai.mcp import server
from edgar.ai.mcp.tools.base import TOOLS, ToolResponse, success

pytestmark = [pytest.mark.fast, pytest.mark.regression]

CASES = [
    ("due_diligence", {"identifier": "SYNTH_A"}),
    ("earnings_analysis", {"identifier": "SYNTH_A"}),
    ("industry_overview", {"industry": "synthetic sector"}),
    ("insider_monitor", {"identifier": "SYNTH_A"}),
    ("fund_analysis", {"identifier": "SYNTH_FUND"}),
    ("filing_comparison", {"identifier": "SYNTH_A"}),
    ("filing_comparison", {"identifier": "SYNTH_A", "form": "10-Q", "compare_to": "SYNTH_B"}),
    ("activist_tracking", {"identifier": "SYNTH_A"}),
]

# Each row recognizes one numbered tool-use clause: step, tool, literal fields.
# Field names describe syntax; their values always come from rendered text.
# An added tool mention or literal field requires a deliberate new recognizer.
EXPECTED_USES = {
    "due_diligence": [
        (1, "edgar_company", ""),
        (2, "edgar_trends", "concepts"),
        (3, "edgar_read", ""),
        (4, "edgar_read", ""),
        (5, "edgar_ownership", "analysis_type"),
    ],
    "earnings_analysis": [
        (1, "edgar_read", "form sections"),
        (2, "edgar_trends", "concepts"),
        (3, "edgar_compare", "metrics"),
        (4, "edgar_read", "sections"),
    ],
    "industry_overview": [
        (1, "edgar_screen", "industry"),
        (3, "edgar_compare", "metrics"),
        (4, "edgar_trends", ""),
        (5, "edgar_monitor", ""),
    ],
    "insider_monitor": [
        (1, "edgar_company", "include"),
        (2, "edgar_ownership", "analysis_type"),
        (3, "edgar_trends", "concepts"),
        (4, "edgar_monitor", "form"),
    ],
    "fund_analysis": [
        (1, "edgar_fund", "action identifier"),
        (2, "edgar_fund", "action identifier"),
        (3, "edgar_fund", "action"),
        (4, "edgar_company", ""),
        (5, "edgar_fund", "action"),
    ],
    "filing_comparison_periods": [
        (1, "edgar_company", "identifier include"),
        (2, "edgar_filing", "identifier form"),
        (2, "edgar_read", "sections"),
        (3, "edgar_search", "identifier form search_type"),
        (3, "edgar_read", "sections"),
        (4, "edgar_trends", "identifier concepts"),
        (5, "edgar_read", "form"),
    ],
    "filing_comparison_companies": [
        (1, "edgar_company", "include"),
        (2, "edgar_read", "identifier form sections"),
        (3, "edgar_read", "identifier form"),
        (4, "edgar_compare", "identifiers"),
        (5, "edgar_trends", "concepts"),
    ],
    "activist_tracking": [
        (1, "edgar_company", "identifier include"),
        (2, "edgar_read", "identifier form"),
        (3, "edgar_read", "identifier form"),
        (4, "edgar_proxy", "identifier"),
        (5, "edgar_text_search", "query identifier"),
        (6, "edgar_ownership", "identifier analysis_type"),
    ],
}

TOOL_MENTION = re.compile(r"\b(edgar_[a-z_]+)\b")
TOOL_USE = re.compile(r"\b[Uu]se (edgar_[a-z_]+)\b")
NUMBERED_STEP = re.compile(r"^(\d+)\. \*\*[^*]+\*\*: (.*)$")
JSON_LITERAL = re.compile(r'\[[^\]\n]*\]|"(?:\\.|[^"\\])*"')
LITERAL_ARGUMENT = re.compile(r'\b([a-z_]+)\s*(?:=|\s)\s*(\[[^\]\n]*\]|"(?:\\.|[^"\\])*")')


@pytest_asyncio.fixture
async def network_attempts(monkeypatch):
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append("network access")
        raise AssertionError("Prompt/schema validation must not access the network")

    # Async fixture setup runs after loop creation; restore before loop teardown.
    # In particular, Windows event-loop socketpair setup is outside this scope.
    with monkeypatch.context() as guard:
        guard.setattr(socket.socket, "connect", blocked)
        guard.setattr(socket.socket, "connect_ex", blocked)
        guard.setattr(socket, "create_connection", blocked)
        guard.setattr(socket, "getaddrinfo", blocked)
        yield attempts
    assert attempts == []


def _workflow_key(name: str, arguments: dict[str, str]) -> str:
    if name == "filing_comparison":
        return f"{name}_{'companies' if arguments.get('compare_to') else 'periods'}"
    return name


def _explicit_uses(prompt: GetPromptResult) -> list[tuple[int, str, str]]:
    uses = []
    mentions = []
    for message in prompt.messages:
        assert isinstance(message.content, TextContent), "This recognizer covers the built-in text templates"
        mentions.extend(TOOL_MENTION.findall(message.content.text))
        for line in message.content.text.splitlines():
            step = NUMBERED_STEP.fullmatch(line)
            if step is None:
                continue
            instruction = step.group(2)
            matches = list(TOOL_USE.finditer(instruction))
            assert TOOL_MENTION.findall(instruction) == [match.group(1) for match in matches]
            for index, match in enumerate(matches):
                end = matches[index + 1].start() if index + 1 < len(matches) else len(instruction)
                uses.append((int(step.group(1)), match.group(1), instruction[match.end() : end]))
    assert mentions == [tool for _, tool, _ in uses], "Every rendered tool mention needs a recognized request clause"
    return uses


def _literal_arguments(instruction: str, fields: str, *, query_alternatives: bool = False) -> list[dict[str, object]]:
    matches = list(LITERAL_ARGUMENT.finditer(instruction))
    values: dict[str, list[object]] = {}
    for match in matches:
        field = "metrics" if match.group(1) == "comparing" else match.group(1)
        assert field not in values or (query_alternatives and field == "query"), "Unrecognized repeated argument"
        values.setdefault(field, []).append(json.loads(match.group(2)))
    assert set(values) == set(fields.split()), "Every explicit argument needs a recognized field"
    for literal in JSON_LITERAL.finditer(instruction):
        assert any(match.start(2) <= literal.start() and literal.end() <= match.end(2) for match in matches), "Unrecognized explicit JSON literal"
    remainder = LITERAL_ARGUMENT.sub("", instruction)
    assert re.search(r"\b[a-z_]+\s*=", remainder) is None, "Unrecognized explicit assignment"

    # Only the activist search clause supplies repeated 'query=...' alternatives.
    count = len(values.get("query", [None]))
    return [{field: options[index if len(options) > 1 else 0] for field, options in values.items()} for index in range(count)]


def _match(instruction: str, pattern: str) -> re.Match[str]:
    match = re.search(pattern, instruction)
    assert match is not None, "The per-line recognizer no longer matches the rendered instruction"
    return match


def _complete_requests(
    key: str,
    step: int,
    tool: str,
    instruction: str,
    literals: dict[str, object],
    arguments: dict[str, str],
    prior: list[tuple[str, dict[str, object]]],
) -> list[dict[str, object]]:
    request = dict(literals)
    # Representative values fill runtime choices, not literal schema parameters.
    subject = arguments.get("identifier", "SYNTH_SCREEN_A")
    if tool in {"edgar_company", "edgar_trends", "edgar_read", "edgar_ownership", "edgar_fund", "edgar_proxy"}:
        request.setdefault("identifier", subject)

    if key == "due_diligence":
        if step == 2:
            request["periods"] = int(_match(instruction, r"over (\d+) years").group(1))
        elif step == 3:
            match = _match(instruction, r"latest (\S+) (\w+) section")
            request.update(form=match.group(1), sections=[match.group(2)])
        elif step == 4:
            request["form"] = _match(instruction, r"latest (\S+) for material events").group(1)

    elif key == "earnings_analysis":
        if step == 2:
            match = _match(instruction, r"for both (\w+) \((\d+) years\) and (\w+) \((\d+) quarters\)")
            return [dict(request, period=match.group(index), periods=int(match.group(index + 1))) for index in (1, 3)]
        if step == 3:
            identifier = _match(instruction, r"with (\S+) and \d+-\d+ peer companies").group(1)
            request["identifiers"] = [identifier, "SYNTH_PEER_B", "SYNTH_PEER_C"]
        elif step == 4:
            match = _match(instruction, r"latest (\S+) or (\S+), sections")
            return [dict(request, form=match.group(index)) for index in (1, 2)]

    elif key == "industry_overview" and tool == "edgar_compare":
        request["identifiers"] = ["SYNTH_SCREEN_A", "SYNTH_SCREEN_B", "SYNTH_SCREEN_C"]

    elif key == "fund_analysis":
        if step == 4:
            request["identifier"] = "SYNTH_HOLDING_A"
        elif step == 5:
            request.pop("identifier")
            request["query"] = "synthetic fund family"

    elif key == "filing_comparison_periods":
        if step == 2 and tool == "edgar_read":
            assert "with the same identifier and form" in instruction
            filing = next(previous for previous_tool, previous in prior if previous_tool == "edgar_filing")
            request.update(identifier=filing["identifier"], form=filing["form"])
        elif step == 3 and tool == "edgar_read":
            assert "with that accession_number" in instruction
            request.pop("identifier")
            request["accession_number"] = "0000000001-26-000001"  # Synthetic earlier-search result.
        elif step == 4:
            request["periods"] = int(_match(instruction, r"over (\d+) periods").group(1))

    elif key == "filing_comparison_companies":
        if step == 1:
            match = _match(instruction, r"for both (\S+) and (\S+) with include")
            return [dict(request, identifier=match.group(index)) for index in (1, 2)]
        if step == 3:
            assert "Read the same sections" in instruction
            filing_a = next(previous for previous_tool, previous in prior if previous_tool == "edgar_read")
            request["sections"] = filing_a["sections"]
        elif step == 5:
            assert "for both companies" in instruction
            identifiers = [previous["identifier"] for previous_tool, previous in prior if previous_tool == "edgar_company"]
            assert len(identifiers) == 2
            return [dict(request, identifier=identifier) for identifier in identifiers]

    return [request]


def _requests(name: str, arguments: dict[str, str], prompt: GetPromptResult) -> list[tuple[str, dict[str, object]]]:
    key = _workflow_key(name, arguments)
    uses = _explicit_uses(prompt)
    expected = EXPECTED_USES[key]
    assert [(step, tool) for step, tool, _ in uses] == [(step, tool) for step, tool, _ in expected]
    requests = []
    for (step, tool, instruction), (_, _, fields) in zip(uses, expected, strict=True):
        variants = _literal_arguments(instruction, fields, query_alternatives=key == "activist_tracking" and step == 5)
        for literals in variants:
            requests.extend((tool, completed) for completed in _complete_requests(key, step, tool, instruction, literals, arguments, requests))
    return requests


def _record_accepted_request(name: str, calls: list[tuple[str, dict[str, object]]]):
    async def handler(**arguments) -> ToolResponse:
        calls.append((name, arguments))
        return success({"accepted_tool": name, "accepted_arguments": arguments})

    return handler


@pytest.mark.parametrize(
    ("name", "arguments"),
    [pytest.param(name, arguments, id=_workflow_key(name, arguments)) for name, arguments in CASES],
)
async def test_explicit_prompt_requests_pass_registered_input_validation(name, arguments, monkeypatch, network_attempts):
    server._import_tools()
    calls = []
    async with create_connected_server_and_client_session(server.app, read_timeout_seconds=timedelta(seconds=5)) as client:
        registered = await client.list_prompts()
        assert {prompt.name for prompt in registered.prompts} == {case_name for case_name, _ in CASES}
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        prompt = await client.get_prompt(name, arguments)
        requests = _requests(name, arguments, prompt)
        assert requests
        with monkeypatch.context() as handlers:
            for tool in {tool for tool, _ in requests}:
                handlers.setitem(TOOLS[tool], "handler", _record_accepted_request(tool, calls))
            for tool, request in requests:
                # MCP permits extra properties, so do not let **kwargs hide an unknown field.
                assert set(request) <= set(tools[tool].inputSchema["properties"])
                result = await client.call_tool(tool, request)
                assert result.isError is False, (name, tool, request, result.content)
                assert len(result.content) == 1 and isinstance(result.content[0], TextContent)
                assert json.loads(result.content[0].text) == {
                    "success": True,
                    "data": {"accepted_tool": tool, "accepted_arguments": request},
                }
            assert calls == requests

        # Keep the requested analyses; deleting a rejected field is not the fix.
        if name in {"earnings_analysis", "industry_overview"}:
            metrics = next(request["metrics"] for tool, request in requests if tool == "edgar_compare")
            assert isinstance(metrics, list)
            assert "margins" in metrics
            if name == "industry_overview":
                assert "assets" in metrics  # Valid for edgar_compare, unlike edgar_trends.
        elif _workflow_key(name, arguments) == "filing_comparison_periods":
            concepts = next(request["concepts"] for tool, request in requests if tool == "edgar_trends")
            assert isinstance(concepts, list)
            assert "total_assets" in concepts


async def test_sdk_rejects_unsupported_input_names_before_downstream_handlers(monkeypatch, network_attempts):
    server._import_tools()
    calls = []
    controls = [
        ("edgar_compare", {"identifiers": ["SYNTH_A", "SYNTH_B"], "metrics": ["net_margin"]}, "net_margin"),
        ("edgar_trends", {"identifier": "SYNTH_A", "concepts": ["assets"]}, "assets"),
    ]
    with monkeypatch.context() as handlers:
        for tool, _, _ in controls:
            handlers.setitem(TOOLS[tool], "handler", _record_accepted_request(tool, calls))
        async with create_connected_server_and_client_session(server.app, read_timeout_seconds=timedelta(seconds=5)) as client:
            await client.list_tools()
            for tool, request, rejected_value in controls:
                result = await client.call_tool(tool, request)
                assert result.isError is True
                assert any(isinstance(content, TextContent) and rejected_value in content.text for content in result.content)
                assert calls == [], "Registered schema validation must precede the replaced handler"
