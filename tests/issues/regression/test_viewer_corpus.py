"""
Viewer Verification Corpus
==========================

Systematic correctness coverage for the SEC R*.htm viewer subsystem. Reads
``tests/fixtures/viewer-corpus/manifest.yaml`` and runs ground-truth
assertions across a curated set of filings spanning the variation surface
(header shapes, footnote conventions, scaling, filer types, fiscal-year
ends).

Beads: edgartools-doup
Background: 5 viewer correctness bugs in the 5.31.x line (GH #797, #799,
#807, #810, #812) motivated the move from per-bug regression tests to a
shared corpus. Every viewer bug fix must add an entry here before merging
— that's the mechanism that makes the corpus self-expanding.

Run with::

    hatch run test-regression -k viewer_corpus
    pytest -m viewer_corpus

Test stays out of ``test-fast`` because it hits the network. Each entry
emits a per-filing diagnostic on failure (period_headers dump + concept
row) — not just a green/red summary.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml

from edgar import Company, Filing


MANIFEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures" / "viewer-corpus" / "manifest.yaml"
)


def _load_manifest() -> Dict[str, Any]:
    with MANIFEST_PATH.open() as f:
        return yaml.safe_load(f)


def _entry_param(entry: Dict[str, Any]) -> Any:
    """Wrap a manifest entry for parametrize, marking xfail if requested."""
    marks = []
    if entry.get("xfail_until_fixed"):
        bugs = ", ".join(entry.get("bug_references", []))
        marks.append(pytest.mark.xfail(
            reason=f"Open viewer bug ({bugs}); corpus entry pins the fix shape",
            strict=False,
        ))
    return pytest.param(entry, id=entry["id"], marks=marks)


def _load_filing(entry: Dict[str, Any]) -> Filing:
    """Resolve a manifest entry to a Filing object.

    Two modes:
      - Pinned: ``accession`` + ``filing_date`` (most entries — reproducible).
      - Latest: ``use_latest_filing: true`` (entries that test steady-state
        behavior across filings; we accept the rot risk for the benefit of
        always exercising current filer output).
    """
    if entry.get("use_latest_filing"):
        return Company(entry["ticker"]).get_filings(form=entry["form"]).latest()
    return Filing(
        form=entry["form"],
        filing_date=entry["filing_date"],
        company=entry["company"],
        cik=entry["cik"],
        accession_no=entry["accession"],
    )


def _find_statement(viewer, *, index: Optional[int] = None,
                    short_name_contains: Optional[str] = None):
    """Locate a viewer statement by index or substring match. Skips
    parenthetical variants for substring matches."""
    if index is not None:
        stmts = viewer.financial_statements
        if index >= len(stmts):
            return None
        return stmts[index]
    needle = (short_name_contains or "").upper()
    for vr in viewer.financial_statements:
        if needle in vr.short_name.upper() and "Parenthetical" not in vr.short_name:
            return vr
    return None


def _diagnose(viewer, statement, label: str) -> str:
    """Build a per-filing failure diagnostic. The runner attaches this to
    any failed assertion so a maintainer can see *what the viewer saw*."""
    lines = [f"\n--- viewer diagnostic ({label}) ---"]
    lines.append(f"financial_statements ({len(viewer.financial_statements)}):")
    for i, vr in enumerate(viewer.financial_statements):
        lines.append(f"  [{i}] {vr.short_name!r}  -> {vr.html_file_name}")
    if statement is not None and statement.concept_report is not None:
        cr = statement.concept_report
        lines.append(f"\nperiod_headers ({len(cr.period_headers)}):")
        for i, h in enumerate(cr.period_headers):
            lines.append(f"  [{i}] {h!r}")
        lines.append(
            f"\ncurrency: {cr.currency}  "
            f"currency_scaling: {cr.currency_scaling}  "
            f"row_count: {len(cr.rows)}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Assertion runners — one per declared YAML key
# ---------------------------------------------------------------------------

def _assert_statement_count_min(viewer, spec, diag):
    actual = len(viewer.financial_statements)
    assert actual >= spec, (
        f"statement_count_min: expected >={spec}, got {actual}{diag()}"
    )


def _assert_statement_short_name_present(viewer, spec: List[str], diag):
    names = {vr.short_name for vr in viewer.financial_statements}
    for required in spec:
        assert required in names, (
            f"statement_short_name_present: {required!r} missing. "
            f"have={sorted(names)}{diag()}"
        )


def _assert_levels_min_distinct(viewer, spec: Dict[str, Any], diag):
    stmt = _find_statement(
        viewer, short_name_contains=spec["statement_short_name_contains"]
    )
    assert stmt is not None, (
        f"levels_min_distinct: no statement matching "
        f"{spec['statement_short_name_contains']!r}{diag()}"
    )
    levels = {row.level for row in stmt.concept_rows}
    assert min(levels) == spec.get("min_level", 0), (
        f"levels_min_distinct: min level = {min(levels)}, "
        f"expected {spec.get('min_level', 0)}{diag()}"
    )
    assert len(levels) >= spec["min_distinct"], (
        f"levels_min_distinct: distinct levels = {len(levels)} "
        f"({sorted(levels)}), expected >= {spec['min_distinct']}{diag()}"
    )


def _assert_currency_scaling(viewer, spec: Dict[str, Any], diag):
    stmt = _find_statement(
        viewer, short_name_contains=spec["statement_short_name_contains"]
    )
    assert stmt is not None, (
        f"currency_scaling: no statement matching "
        f"{spec['statement_short_name_contains']!r}{diag()}"
    )
    actual = stmt.currency_scaling
    assert actual == spec["expected"], (
        f"currency_scaling: expected {spec['expected']}, got {actual}{diag()}"
    )


def _assert_scaling_consistent_across_statements(viewer, spec, diag):
    if not spec:
        return
    scales = {}
    for vr in viewer.financial_statements:
        if "Parenthetical" in vr.short_name:
            continue
        if vr.currency_scaling is None:
            continue
        scales[vr.short_name] = vr.currency_scaling
    distinct = set(scales.values())
    assert len(distinct) <= 1, (
        f"currency_scaling_consistent_across_statements: filing reports "
        f"multiple scales {distinct} across statements {scales}{diag()}"
    )


def _assert_period_headers_contain(viewer, spec: Dict[str, Any], diag):
    stmt = _find_statement(viewer, index=spec["statement_index"])
    assert stmt is not None and stmt.concept_report is not None, (
        f"period_headers_contain: statement_index={spec['statement_index']} "
        f"not found or has no concept_report{diag()}"
    )
    headers = stmt.concept_report.period_headers
    for needle in spec["substrings"]:
        assert any(needle in h for h in headers), (
            f"period_headers_contain: substring {needle!r} not found in "
            f"any period header{diag()}"
        )


def _assert_concept_row_check(viewer, spec: Dict[str, Any], diag):
    stmt = _find_statement(viewer, index=spec["statement_index"])
    assert stmt is not None, (
        f"concept_row_check: statement_index={spec['statement_index']} "
        f"not found{diag()}"
    )
    target = spec["concept"]
    row = next((r for r in stmt.concept_rows if r.concept_id == target), None)
    assert row is not None, (
        f"concept_row_check: concept {target!r} not found in statement"
        f"{diag()}"
    )

    if "numeric_value" in spec:
        expected = spec["numeric_value"]
        actual = row.numeric_value
        assert actual == expected, (
            f"concept_row_check: {target} numeric_value: "
            f"expected {expected}, got {actual}{diag()}"
        )

    for period_key, expected_value in (spec.get("period_value") or {}).items():
        actual = row.numeric_values.get(period_key)
        assert actual == expected_value, (
            f"concept_row_check: {target} at {period_key!r}: "
            f"expected {expected_value}, got {actual}{diag()}"
        )

    if "period_contains" in spec:
        needle = spec["period_contains"]
        matching_period = next(
            (p for p in row.numeric_values if needle in p), None
        )
        assert matching_period is not None, (
            f"concept_row_check: no period containing {needle!r} for "
            f"{target}. periods={list(row.numeric_values)}{diag()}"
        )
        value = row.numeric_values[matching_period]
        if "expected_value_min" in spec:
            assert value >= spec["expected_value_min"], (
                f"concept_row_check: {target} at {matching_period!r}: "
                f"value {value} < min {spec['expected_value_min']}{diag()}"
            )
        if "expected_value_max" in spec:
            assert value <= spec["expected_value_max"], (
                f"concept_row_check: {target} at {matching_period!r}: "
                f"value {value} > max {spec['expected_value_max']}{diag()}"
            )


# Map YAML assertion keys to runner functions. Keys not in this map are
# rejected so typos in the manifest surface immediately.
ASSERTION_RUNNERS = {
    "statement_count_min": _assert_statement_count_min,
    "statement_short_name_present": _assert_statement_short_name_present,
    "levels_min_distinct": _assert_levels_min_distinct,
    "currency_scaling": _assert_currency_scaling,
    "currency_scaling_consistent_across_statements": (
        _assert_scaling_consistent_across_statements
    ),
    "period_headers_contain": _assert_period_headers_contain,
    "concept_row_check": _assert_concept_row_check,
    "concept_row_check_2": _assert_concept_row_check,
}


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

_MANIFEST = _load_manifest()
_ENTRIES = [_entry_param(e) for e in _MANIFEST["entries"]]


def test_manifest_schema_version():
    """Guard against accidental schema drift."""
    assert _MANIFEST.get("schema_version") == 1


def test_manifest_dimension_tags_match_vocabulary():
    """Every entry's dimension values must come from the closed vocabulary
    in the manifest. Typos in dimension labels would silently weaken
    coverage tracking."""
    vocab = _MANIFEST["dimensions"]
    for entry in _MANIFEST["entries"]:
        dims = entry.get("dimensions", {})
        for axis, value in dims.items():
            allowed = vocab.get(axis)
            assert allowed is not None, (
                f"{entry['id']}: unknown dimension axis {axis!r}"
            )
            assert value in allowed, (
                f"{entry['id']}: dimension {axis}={value!r} not in "
                f"vocabulary {allowed}"
            )


def test_manifest_assertion_keys_are_known():
    """Reject typos in assertion keys so manifest entries can't silently
    skip checks."""
    for entry in _MANIFEST["entries"]:
        for key in (entry.get("assertions") or {}):
            assert key in ASSERTION_RUNNERS, (
                f"{entry['id']}: unknown assertion key {key!r}. "
                f"known={sorted(ASSERTION_RUNNERS)}"
            )


@pytest.mark.network
@pytest.mark.regression
@pytest.mark.viewer_corpus
@pytest.mark.parametrize("entry", _ENTRIES)
def test_viewer_corpus_entry(entry):
    """Run all assertions declared for one manifest entry."""
    filing = _load_filing(entry)
    viewer = filing.viewer
    assert viewer is not None, (
        f"{entry['id']}: filing.viewer is None — MetaLinks.json missing?"
    )

    assertions = entry.get("assertions") or {}
    assert assertions, (
        f"{entry['id']}: manifest entry has no assertions. Every corpus "
        f"entry must encode at least one ground-truth check."
    )

    def diag():
        # Re-find the first statement referenced by any assertion for the
        # diagnostic dump. Falls back to financial_statements[0].
        stmt = None
        for spec in assertions.values():
            if isinstance(spec, dict) and "statement_index" in spec:
                stmt = _find_statement(viewer, index=spec["statement_index"])
                if stmt is not None:
                    break
        if stmt is None and viewer.financial_statements:
            stmt = viewer.financial_statements[0]
        return _diagnose(viewer, stmt, entry["id"])

    for key, spec in assertions.items():
        runner = ASSERTION_RUNNERS[key]
        runner(viewer, spec, diag)
