"""Offline checks for the scheduled bug-finding sweeps.

Covers scripts/scheduled_issues.py (signatures, dedupe plan, issue bodies),
scripts/crash_sweep.py (families, the stratified draw, per-stage isolation) and
scripts/fidelity_sweep.py (reading failures back from the scorecard's filings.csv).
"""
import csv
import importlib
import sys
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


si = importlib.import_module("scheduled_issues")
crash = importlib.import_module("crash_sweep")
fidelity = importlib.import_module("fidelity_sweep")


def _tb(*frames, exc="KeyError: 'Revenues'"):
    lines = ["Traceback (most recent call last):"]
    for path, line, func in frames:
        lines += [f'  File "{path}", line {line}, in {func}', "    code()"]
    return " || ".join(lines + [exc])


SCRIPT_FRAME = ("/home/runner/work/edgartools/edgartools/scripts/crash_sweep.py", 210, "run_filing")
XBRL_FRAME = ("/home/runner/work/edgartools/edgartools/edgar/xbrl/xbrl.py", 412, "parse")
FACTS_FRAME = ("/home/runner/work/edgartools/edgartools/edgar/xbrl/facts.py", 88, "_value")
PANDAS_FRAME = ("/opt/hostedtoolcache/Python/3.11/lib/python3.11/site-packages/pandas/core/frame.py", 3, "loc")


class TestSignatures:

    def test_innermost_edgar_frame_ignores_dependencies_below_it(self):
        tb = _tb(SCRIPT_FRAME, XBRL_FRAME, FACTS_FRAME, PANDAS_FRAME)
        assert si.edgar_frame(tb) == "edgar/xbrl/facts:_value"

    def test_checkout_directory_is_not_mistaken_for_the_package(self):
        assert si.edgar_frame(_tb(SCRIPT_FRAME)) == ""

    def test_installed_package_paths_are_recognised(self):
        tb = _tb(("/usr/lib/python3.11/site-packages/edgar/entity/core.py", 1, "get_facts"))
        assert si.edgar_frame(tb) == "edgar/entity/core:get_facts"

    def test_signature_survives_line_number_changes(self):
        moved = ("/x/edgar/xbrl/facts.py", 999, "_value")
        assert si.signature("crash", "KeyError", _tb(XBRL_FRAME, FACTS_FRAME), "xbrl") == \
            si.signature("crash", "KeyError", _tb(XBRL_FRAME, moved), "xbrl")

    def test_same_type_from_different_places_is_two_signatures(self):
        assert si.signature("crash", "KeyError", _tb(FACTS_FRAME), "xbrl") != \
            si.signature("crash", "KeyError", _tb(XBRL_FRAME), "xbrl")

    def test_group_drops_transient_and_harness_errors(self):
        failures = [
            si.Failure("0000000001-26-000001", "10-K", "A", "xbrl", "KeyError", "x", _tb(FACTS_FRAME)),
            si.Failure("0000000002-26-000002", "10-Q", "B", "xbrl", "KeyError", "y", _tb(FACTS_FRAME)),
            si.Failure("0000000003-26-000003", "8-K", "C", "text", "TransportError", "503", _tb(XBRL_FRAME)),
            si.Failure("0000000004-26-000004", "10-K", "D", "statements", "AttributeError", "z", _tb(SCRIPT_FRAME)),
        ]
        groups = si.group_failures("crash", failures)
        assert len(groups) == 1
        assert [f.accession for f in groups[0].failures] == ["0000000001-26-000001", "0000000002-26-000002"]
        assert groups[0].title == "[crash sweep] KeyError in xbrl: edgar/xbrl/facts:_value"


class TestPlan:

    def _signature(self, frame=FACTS_FRAME):
        return si.group_failures("crash", [
            si.Failure("0000000001-26-000001", "10-K", "A", "xbrl", "KeyError", "x", _tb(frame))])[0]

    def test_new_signature_is_filed_and_its_body_marks_it(self):
        s = self._signature()
        body = si.failure_issue_body(s, "2026-11-16 to 2026-11-22")
        assert si.plan([s], [], "crash").to_file == [s]
        # The body's marker is what the next run dedupes on.
        issue = {"number": 7, "state": "OPEN", "body": body}
        assert si.known_signatures([issue], "crash") == {s.digest: issue}

    def test_open_and_closed_signatures_are_never_refiled(self):
        open_s, closed_s = self._signature(FACTS_FRAME), self._signature(XBRL_FRAME)
        issues = [{"number": 7, "state": "OPEN", "body": si.failure_issue_body(open_s, "run")},
                  {"number": 9, "state": "CLOSED", "body": si.failure_issue_body(closed_s, "run")}]
        p = si.plan([open_s, closed_s], issues, "crash")
        assert p.to_file == []
        assert [n for _, n in p.known_open] == [7]
        assert [n for _, n in p.seen_again_closed] == [9]
        assert "#9" in si.plan_summary(p)

    def test_another_jobs_marker_does_not_count(self):
        s = self._signature()
        other = {"number": 3, "state": "OPEN", "body": f"<!-- sweep-signature: fidelity:{s.digest} -->"}
        assert si.plan([s], [other], "crash").to_file == [s]

    def test_scorecard_issue_is_found_by_marker_only_when_open(self):
        issues = [{"number": 4, "state": "CLOSED", "body": "<!-- sweep-scorecard: crash -->"},
                  {"number": 5, "state": "OPEN", "body": "<!-- sweep-scorecard: crash -->"},
                  {"number": 6, "state": "OPEN", "body": "<!-- sweep-scorecard: fidelity -->"}]
        assert si.scorecard_issue(issues, "crash") == 5
        assert si.scorecard_issue(issues[:1], "crash") is None


class TestCrashSweep:

    def test_form_families(self):
        assert crash.family_of("10-K") == "10-K"
        assert crash.family_of("6-K") == "foreign"
        assert crash.family_of("SCHEDULE 13G") == "schedule-13"
        assert crash.family_of("10-K/A") == "other"

    def test_draw_is_stratified_and_reproducible(self):
        population = ([{"form": "10-K", "accession_number": f"0000000001-26-{i:06d}"} for i in range(50)]
                      + [{"form": "4", "accession_number": f"0000000002-26-{i:06d}"} for i in range(50)]
                      + [{"form": "8-K", "accession_number": "0000000003-26-000001"}])
        first = crash.draw_sample(population, 9, seed=20261122)
        assert crash.draw_sample(list(reversed(population)), 9, seed=20261122) == first
        counts = {fam: sum(1 for r in first if r["family"] == fam) for fam in ("10-K", "ownership", "8-K")}
        # 9 shared by three families; 8-K has only one filing to give.
        assert counts == {"10-K": 3, "ownership": 3, "8-K": 1}

    def test_stage_names_match_the_stages_run(self):
        assert tuple(name for name, _ in crash.stages_for(object())) == crash.STAGE_NAMES

    def test_a_failing_stage_does_not_stop_the_next(self):
        def boom(_state):
            raise ValueError("bad table")

        def skipped(_state):
            raise crash._Skip

        row = {"form": "10-K", "filing_date": date(2026, 11, 20), "company": "A", "cik": 1,
               "accession_number": "0000000001-26-000001", "family": "10-K"}
        result = crash.run_filing(row, timeout=30, stages=lambda _f: [
            ("text", boom), ("obj", lambda s: None), ("xbrl", skipped), ("markdown", lambda s: "ok")])
        assert [(s.stage, s.outcome) for s in result.stages] == [
            ("text", "error"), ("obj", "none"), ("xbrl", "skipped"), ("markdown", "ok")]
        assert result.stages[0].error_type == "ValueError"
        assert "test_scheduled_sweeps.py" in result.stages[0].traceback


class TestFidelitySweep:

    def test_failures_are_read_from_filings_csv(self, tmp_path):
        path = tmp_path / "filings.csv"
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["accession_number", "form", "company", "outcome", "error_type",
                                              "error_message", "error_stage", "traceback"])
            w.writeheader()
            w.writerow({"accession_number": "0000000001-26-000001", "form": "10-K", "company": "A",
                        "outcome": "ok"})
            w.writerow({"accession_number": "0000000002-26-000002", "form": "10-Q", "company": "B",
                        "outcome": "error", "error_type": "KeyError", "error_message": "x",
                        "error_stage": "statements", "traceback": _tb(FACTS_FRAME)})
        failures = fidelity.failures_from(path)
        assert [(f.accession, f.stage) for f in failures] == [("0000000002-26-000002", "statements")]
        assert fidelity.failures_from(tmp_path / "missing.csv") == []
