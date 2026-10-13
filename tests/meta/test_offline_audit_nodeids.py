"""Preserve failed pytest parameter identities in the offline-audit ratchet.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1476

Pytest prints arbitrary node IDs followed by an unescaped `` - message``.
Native reports avoid that ambiguity; legacy summaries support balanced Python
parameter IDs and fail before writing the baseline when recovery is ambiguous.
These tests use only report data and temporary files, never network access.
"""

import importlib.util
import json
import shlex
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.regression]

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_offline_audit.py"
MACHINE_PREFIX = "OFFLINE_AUDIT_NODEIDS: "
CASE = "tests/unit/test_example.py::TestReport::test_case"
SALES = CASE + "[Net sales]"
INCOME = CASE + "[Net income]"


@pytest.fixture(scope="module")
def audit() -> ModuleType:
    spec = importlib.util.spec_from_file_location("offline_audit_1476", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import offline audit from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _machine(*nodeids: str) -> str:
    return MACHINE_PREFIX + json.dumps({"version": 1, "nodeids": list(nodeids)}) + "\n"


def _report(kind: str, *nodeids: str) -> str:
    if kind == "machine":
        return _machine(*nodeids)
    return "".join(f"FAILED {node}\n" for node in nodeids)


def _invoke_report(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    report: str,
    baseline: tuple[str, ...] = (),
    *,
    write: bool = False,
    paths: tuple[str, ...] = (),
) -> int:
    baseline_path = tmp_path / "tests" / "offline_audit_baseline.txt"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text("\n".join(baseline) + "\n", encoding="utf-8")
    report_path = tmp_path / "report.log"
    report_path.write_text(report, encoding="utf-8")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "BASELINE_PATH", baseline_path)

    def unexpected_run(paths: list[str]) -> str:
        pytest.fail(f"--report unexpectedly ran pytest for {paths}")

    monkeypatch.setattr(audit, "run_audit", unexpected_run)
    argv = ["check_offline_audit.py", "--report", str(report_path)]
    if write:
        argv.append("--write")
    monkeypatch.setattr(sys, "argv", [*argv, *paths])
    return audit.main()


@pytest.mark.parametrize("outcome", ["FAILED", "ERROR"])
@pytest.mark.parametrize("suffix", ["", " - AssertionError: [actual] != [expected] mismatch"])
@pytest.mark.parametrize(
    "parameter",
    [
        "Net sales",
        "Net - sales",
        "nested [period] sales",
        "  sales  ",
        "tab\tlabel",
    ],
)
def test_legacy_summary_preserves_full_balanced_parameter(
    audit: ModuleType,
    outcome: str,
    suffix: str,
    parameter: str,
) -> None:
    nodeid = f"{CASE}[{parameter}]"
    assert audit.parse_report(f"{outcome} {nodeid}{suffix}\n") == {nodeid}


def test_legacy_summary_keeps_parameters_distinct(audit: ModuleType) -> None:
    assert audit.parse_report(_report("plain", SALES, INCOME)) == {SALES, INCOME}


def test_legacy_summary_ignores_harness_logs(audit: ModuleType) -> None:
    text = f"ERROR    edgar.core:company_subsets.py:347 outbound network blocked\nERROR {CASE} - RuntimeError: blocked\n"
    assert audit.parse_report(text) == {CASE}


def test_legacy_collection_error_keeps_file_id(audit: ModuleType) -> None:
    assert audit.parse_report("ERROR tests/unit/test_broken.py - SyntaxError: invalid syntax\n") == {
        "tests/unit/test_broken.py",
    }


@pytest.mark.parametrize(
    "line",
    [
        f"FAILED {CASE}[right] - hand]\n",
        f"FAILED {CASE}[left[] - RuntimeError: blocked\n",
        f"FAILED {CASE}[right] hand]\n",
        f"FAILED {CASE}[right] - hand] - RuntimeError: blocked\n",
        f"FAILED {SALES} - AssertionError: [1] != [2]\n",
        "ERROR tests/first.py - second.py\n",
    ],
)
def test_legacy_ambiguous_ids_are_rejected(audit: ModuleType, line: str) -> None:
    with pytest.raises(ValueError, match="Ambiguous or unsupported"):
        audit.parse_report(line)


@pytest.mark.parametrize(
    "parameter",
    [
        "Net sales",
        "Net - sales",
        "right] - hand",
        "left[",
        "A] - [B",
        "O'Brien $amount; [item]",
        "back\\slash with space",
        "tab\tlabel",
    ],
)
def test_machine_report_preserves_native_ids(audit: ModuleType, parameter: str) -> None:
    nodeid = f"{CASE}[{parameter}]"
    assert audit.parse_report(_machine(nodeid)) == {nodeid}


def test_machine_report_takes_precedence_over_stdout(audit: ModuleType) -> None:
    text = (
        f"FAILED {CASE}[right] - hand]\n"
        "FAILED tests/unit/test_stdout.py::test_fake - captured output\n"
        "ERROR    edgar.core:company_subsets.py:347 outbound network blocked\n" + _machine(SALES, INCOME)
    )
    assert audit.parse_report(text) == {SALES, INCOME}


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        '{"version": 2, "nodeids": []}',
        '{"version": true, "nodeids": []}',
        '{"version": 1.0, "nodeids": []}',
        '{"version": 1, "nodeids": [], "extra": "captured stdout"}',
        '{"version": 1, "nodeids": "tests/unit/test_a.py::test_a"}',
        '{"version": 1, "nodeids": [1]}',
        '{"version": 1, "nodeids": ["edgar.core:company_subsets.py:347"]}',
    ],
)
def test_invalid_machine_reports_fail_closed(audit: ModuleType, payload: str) -> None:
    with pytest.raises(ValueError, match="report"):
        audit.parse_report(MACHINE_PREFIX + payload + "\n")


def test_duplicate_machine_reports_fail_closed(audit: ModuleType) -> None:
    with pytest.raises(ValueError, match="Expected one"):
        audit.parse_report(_machine(SALES) + _machine(INCOME))


def test_captured_stdout_cannot_override_the_genuine_machine_report(
    audit: ModuleType,
) -> None:
    text = "Captured stdout call\n" + _machine() + "end captured output\n" + _machine(SALES)
    with pytest.raises(ValueError, match="Expected one"):
        audit.parse_report(text)


@pytest.mark.parametrize("break_char", ["\n", "\r"])
def test_machine_report_cannot_write_multiline_baseline_ids(
    audit: ModuleType,
    break_char: str,
) -> None:
    with pytest.raises(ValueError, match="line break"):
        audit.parse_report(_machine(f"{CASE}[line{break_char}label]"))


class _Reporter:
    def __init__(self, reports: dict[str, list[SimpleNamespace]]) -> None:
        self.reports = reports
        self.requested: list[str] = []
        self.lines: list[str] = []

    def getreports(self, outcome: str) -> list[SimpleNamespace]:
        self.requested.append(outcome)
        return self.reports.get(outcome, [])

    def write_line(self, line: str) -> None:
        self.lines.append(line)


def test_pytest_hook_uses_failed_and_error_reports_only(audit: ModuleType) -> None:
    unusual = f"{CASE}[right] - hand]"
    collection = "tests/unit/test_broken.py"
    reporter = _Reporter(
        {
            "failed": [SimpleNamespace(nodeid=SALES), SimpleNamespace(nodeid=unusual)],
            "error": [
                SimpleNamespace(nodeid=collection),
                SimpleNamespace(nodeid=SALES),
                SimpleNamespace(nodeid="edgar.core:company_subsets.py:347"),
            ],
            "passed": [SimpleNamespace(nodeid=INCOME)],
            "skipped": [SimpleNamespace(nodeid=CASE + "[skipped]")],
        }
    )
    audit.pytest_terminal_summary(reporter)
    assert reporter.requested == ["failed", "error"]
    assert len(reporter.lines) == 1
    payload = json.loads(reporter.lines[0][len(MACHINE_PREFIX) :])
    assert payload == {"version": 1, "nodeids": sorted({SALES, unusual, collection})}
    assert audit.parse_report(reporter.lines[0]) == {SALES, unusual, collection}


@pytest.mark.parametrize("kind", ["plain", "machine"])
def test_main_keeps_known_space_parameters(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: str,
) -> None:
    assert (
        _invoke_report(
            audit,
            tmp_path,
            monkeypatch,
            _report(kind, SALES, INCOME),
            (SALES, INCOME),
            paths=("tests/unit",),
        )
        == 0
    )
    output = capsys.readouterr()
    assert "OK: 2 known" in output.out
    assert "none new" in output.out
    assert not output.err


@pytest.mark.parametrize("kind", ["plain", "machine"])
def test_main_detects_new_parameter_without_collapsing_it(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: str,
) -> None:
    assert (
        _invoke_report(
            audit,
            tmp_path,
            monkeypatch,
            _report(kind, SALES, INCOME),
            (SALES,),
            paths=("tests/unit/test_example.py",),
        )
        == 1
    )
    output = capsys.readouterr()
    assert "1 test(s) need the SEC" in output.out
    assert INCOME in output.out
    command = next(line.strip() for line in output.out.splitlines() if line.strip().startswith("python -m pytest "))
    assert shlex.split(command) == ["python", "-m", "pytest", INCOME]


@pytest.mark.parametrize("kind", ["plain", "machine"])
def test_main_detects_fixed_parameter_by_full_identity(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: str,
) -> None:
    assert (
        _invoke_report(
            audit,
            tmp_path,
            monkeypatch,
            _report(kind, SALES),
            (SALES, INCOME),
            paths=("tests/unit/test_example.py",),
        )
        == 1
    )
    output = capsys.readouterr()
    assert "1 baseline entry/entries" in output.out
    assert INCOME in output.out
    assert "test(s) need the SEC" not in output.out


@pytest.mark.parametrize("kind", ["plain", "machine"])
def test_baseline_write_keeps_distinct_parameter_ids(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: str,
) -> None:
    assert _invoke_report(audit, tmp_path, monkeypatch, _report(kind, SALES, INCOME), write=True) == 0
    assert "Wrote 2 node id(s)" in capsys.readouterr().out
    assert audit.read_baseline() == {SALES, INCOME}


@pytest.mark.parametrize("whitespace", [" ", "\t", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"])
def test_native_baseline_roundtrip_preserves_collector_whitespace(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    whitespace: str,
) -> None:
    trailing = "tests/custom::trailing" + whitespace
    interior = "tests/custom::item[period" + whitespace + "label]"
    report = _machine(trailing, interior)
    assert _invoke_report(audit, tmp_path, monkeypatch, report, write=True) == 0
    assert "Wrote 2 node id(s)" in capsys.readouterr().out
    baseline = audit.BASELINE_PATH.read_text(encoding="utf-8")
    assert baseline.endswith("\n".join(sorted([trailing, interior])) + "\n")
    assert audit.read_baseline() == {trailing, interior}
    # Check the ratchet against the just-written file without recreating it.
    monkeypatch.setattr(sys, "argv", ["check_offline_audit.py", "--report", str(tmp_path / "report.log")])
    assert audit.main() == 0
    assert "OK: 2 known" in capsys.readouterr().out


@pytest.mark.parametrize(
    "parameter",
    [
        "Net sales",
        "O'Brien $amount; [item]",
        '"double" $(x) * ?',
        "back\\slash with space",
    ],
)
def test_rerun_command_quotes_the_complete_native_id(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    parameter: str,
) -> None:
    nodeid = f"{CASE}[{parameter}]"
    assert _invoke_report(audit, tmp_path, monkeypatch, _machine(nodeid)) == 1
    output = capsys.readouterr()
    command = next(line.strip() for line in output.out.splitlines() if line.strip().startswith("python -m pytest "))
    assert shlex.split(command) == ["python", "-m", "pytest", nodeid]


def test_ambiguous_report_does_not_rewrite_the_baseline(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    text = f"FAILED {CASE}[right] - hand]\n"
    assert _invoke_report(audit, tmp_path, monkeypatch, text, (SALES,), write=True) == 2
    assert "Ambiguous or unsupported" in capsys.readouterr().err
    assert audit.read_baseline() == {SALES}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1 passed in 0.01s\n", 2),
        (_machine() + "no tests ran in 0.01s\n", 2),
        (_machine() + "5 deselected in 0.01s\n", 0),
        (_machine("tests/unit/test_broken.py") + "1 error in 0.01s\n", 1),
    ],
)
def test_native_audit_keeps_no_result_and_collection_guards(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    text: str,
    expected: int,
) -> None:
    monkeypatch.setattr(audit, "BASELINE_PATH", tmp_path / "absent-baseline.txt")
    monkeypatch.setattr(audit, "run_audit", lambda paths: text)
    monkeypatch.setattr(sys, "argv", ["check_offline_audit.py"])
    assert audit.main() == expected
    output = capsys.readouterr()
    if "1 passed" in text:
        assert "required offline-audit machine report" in output.err
    elif "no tests ran" in text:
        assert "Audit produced no result" in output.err
    elif "deselected" in text:
        assert "nothing to audit" in output.out
    else:
        assert "tests/unit/test_broken.py" in output.out


@pytest.mark.parametrize("status", [2, 3, 4, -9])
def test_native_audit_rejects_infrastructure_status_before_write(
    audit: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: int,
) -> None:
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(SALES + "\n", encoding="utf-8")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    monkeypatch.setattr(audit, "BASELINE_PATH", baseline)
    result = subprocess.CompletedProcess([], status, _machine() + "1 passed\n", "")
    monkeypatch.setattr(audit.subprocess, "run", lambda *args, **kwargs: result)
    monkeypatch.setattr(sys, "argv", ["check_offline_audit.py", "--write"])
    assert audit.main() == 2
    assert f"Pytest exited with status {status}" in capsys.readouterr().err
    assert baseline.read_text(encoding="utf-8") == SALES + "\n"
