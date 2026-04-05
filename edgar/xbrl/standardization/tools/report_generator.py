"""
Markdown report generator and parser for the expansion pipeline.

Generates structured markdown reports that pass state between pipeline stages:
- Cohort reports: inner loop output (companies, fixes, unresolved gaps)
- Escalation reports: outer loop output (auto-fixes, escalated gaps for review)

This module is standalone — no dependencies on other expansion pipeline modules.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CompanyResult:
    ticker: str
    ef_cqs: float
    status: str       # "graduated" | "needs_investigation" | "failed"
    gaps_remaining: int
    notes: str = ""


@dataclass
class AppliedFix:
    ticker: str
    metric: str
    action: str       # e.g., "EXCLUDE_METRIC", "MAP_CONCEPT"
    confidence: float
    detail: str = ""


@dataclass
class UnresolvedGapEntry:
    ticker: str
    metric: str
    gap_type: str     # "unmapped" | "high_variance" | etc.
    variance: Optional[float]
    root_cause: str
    graveyard: int = 0
    # Evidence fields for confidence scorer (not rendered in markdown tables)
    reference_value: Optional[float] = None
    xbrl_value: Optional[float] = None
    components_found: int = 0
    components_needed: int = 0


@dataclass
class CohortReportData:
    name: str
    status: str
    companies: List[CompanyResult] = field(default_factory=list)
    fixes: List[AppliedFix] = field(default_factory=list)
    unresolved: List[UnresolvedGapEntry] = field(default_factory=list)


@dataclass
class EscalatedGap:
    ticker: str
    metric: str
    gap_type: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    why_escalated: str = ""
    recommendation: str = ""


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_cohort_report(data: CohortReportData) -> str:
    """Generate a markdown cohort report from structured data."""
    lines: list[str] = []

    # Header
    lines.append(f"# Cohort Report: {data.name}")
    lines.append("")
    lines.append(f"**Status:** {data.status}")
    lines.append("")

    # Companies table
    lines.append("## Companies")
    lines.append("")
    lines.append("| Ticker | EF-CQS | Status | Gaps | Notes |")
    lines.append("|--------|--------|--------|------|-------|")
    for c in data.companies:
        lines.append(f"| {c.ticker} | {c.ef_cqs:.2f} | {c.status} | {c.gaps_remaining} | {c.notes} |")
    lines.append("")

    # Fixes Applied table
    lines.append("## Fixes Applied")
    lines.append("")
    if data.fixes:
        lines.append("| Ticker | Metric | Action | Confidence | Detail |")
        lines.append("|--------|--------|--------|------------|--------|")
        for f in data.fixes:
            lines.append(f"| {f.ticker} | {f.metric} | {f.action} | {f.confidence:.2f} | {f.detail} |")
    else:
        lines.append("_No fixes applied._")
    lines.append("")

    # Unresolved Gaps table
    lines.append("## Unresolved Gaps")
    lines.append("")
    if data.unresolved:
        lines.append("| Ticker | Metric | Gap Type | Variance | Root Cause | Graveyard |")
        lines.append("|--------|--------|----------|----------|------------|-----------|")
        for u in data.unresolved:
            var_str = f"{u.variance:.1f}" if u.variance is not None else "\u2014"
            lines.append(f"| {u.ticker} | {u.metric} | {u.gap_type} | {var_str} | {u.root_cause} | {u.graveyard} |")
    else:
        lines.append("_No unresolved gaps._")
    lines.append("")

    return "\n".join(lines)


def generate_escalation_report(
    name: str,
    auto_fixes: List[AppliedFix],
    escalated_gaps: List[EscalatedGap],
    ef_cqs_before: float,
    ef_cqs_after: float,
) -> str:
    """Generate a markdown escalation report for human/AI review."""
    lines: list[str] = []

    # Header
    lines.append(f"# Escalation Report: {name}")
    lines.append("")
    lines.append("**Status:** pending_review")
    lines.append(f"**EF-CQS:** {ef_cqs_before:.2f} \u2192 {ef_cqs_after:.2f}")
    lines.append("")

    # Auto-fixes summary
    lines.append("## Auto-Fixes Applied")
    lines.append("")
    if auto_fixes:
        lines.append("| Ticker | Metric | Action | Confidence | Detail |")
        lines.append("|--------|--------|--------|------------|--------|")
        for f in auto_fixes:
            lines.append(f"| {f.ticker} | {f.metric} | {f.action} | {f.confidence:.2f} | {f.detail} |")
    else:
        lines.append("_No auto-fixes applied._")
    lines.append("")

    # Escalated gaps
    lines.append("## Escalated Gaps")
    lines.append("")
    if escalated_gaps:
        for i, gap in enumerate(escalated_gaps, 1):
            lines.append(f"### Gap {i}: {gap.ticker}:{gap.metric}")
            lines.append("")
            lines.append(f"- **Type:** {gap.gap_type}")
            lines.append(f"- **Confidence:** {gap.confidence:.2f}")
            lines.append("")
            lines.append("**Evidence:**")
            lines.append("")
            for ev in gap.evidence:
                lines.append(f"- {ev}")
            lines.append("")
            lines.append(f"**Why escalated:** {gap.why_escalated}")
            lines.append("")
            lines.append(f"**Recommendation:** {gap.recommendation}")
            lines.append("")
    else:
        lines.append("_No gaps escalated._")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_table_rows(text: str, header_pattern: str) -> list[list[str]]:
    """Parse markdown table rows following a header that matches the pattern.

    Returns a list of rows, each row a list of cell values (stripped).
    """
    rows: list[list[str]] = []
    lines = text.split("\n")
    in_table = False
    header_seen = False

    for line in lines:
        stripped = line.strip()
        if not in_table:
            # Look for the header row
            if re.search(header_pattern, stripped):
                header_seen = True
                continue
            # Skip separator row after header
            if header_seen and re.match(r"^\|[-\s|]+\|$", stripped):
                in_table = True
                continue
            header_seen = False
        else:
            # We're in the table body
            if stripped.startswith("|") and not re.match(r"^\|[-\s|]+\|$", stripped):
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                rows.append(cells)
            else:
                break  # End of table

    return rows


def parse_cohort_report(md: str) -> CohortReportData:
    """Parse a markdown cohort report back into structured data."""
    # Extract name from header
    name_match = re.search(r"^# Cohort Report:\s*(.+)$", md, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else ""

    # Extract status
    status_match = re.search(r"^\*\*Status:\*\*\s*(.+)$", md, re.MULTILINE)
    status = status_match.group(1).strip() if status_match else ""

    # Parse companies table
    companies: list[CompanyResult] = []
    company_rows = _parse_table_rows(md, r"\|\s*Ticker\s*\|\s*EF-CQS\s*\|")
    for row in company_rows:
        if len(row) >= 5:
            companies.append(CompanyResult(
                ticker=row[0],
                ef_cqs=float(row[1]),
                status=row[2],
                gaps_remaining=int(row[3]),
                notes=row[4],
            ))

    # Parse fixes table
    fixes: list[AppliedFix] = []
    fix_rows = _parse_table_rows(md, r"\|\s*Ticker\s*\|\s*Metric\s*\|\s*Action\s*\|")
    for row in fix_rows:
        if len(row) >= 5:
            fixes.append(AppliedFix(
                ticker=row[0],
                metric=row[1],
                action=row[2],
                confidence=float(row[3]),
                detail=row[4],
            ))

    # Parse unresolved gaps table
    unresolved: list[UnresolvedGapEntry] = []
    unresolved_rows = _parse_table_rows(md, r"\|\s*Ticker\s*\|\s*Metric\s*\|\s*Gap Type\s*\|")
    for row in unresolved_rows:
        if len(row) >= 6:
            var_str = row[3]
            variance = None if var_str == "\u2014" else float(var_str)
            unresolved.append(UnresolvedGapEntry(
                ticker=row[0],
                metric=row[1],
                gap_type=row[2],
                variance=variance,
                root_cause=row[4],
                graveyard=int(row[5]),
            ))

    return CohortReportData(
        name=name,
        status=status,
        companies=companies,
        fixes=fixes,
        unresolved=unresolved,
    )


# ---------------------------------------------------------------------------
# Evidence sidecar
# ---------------------------------------------------------------------------

def write_evidence_sidecar(
    report_path: Path,
    cohort_name: str,
    gaps: List[UnresolvedGapEntry],
) -> Path:
    """Write companion JSON with evidence fields lost in markdown.

    The sidecar file is named ``{report_path}.evidence.json``, e.g.
    ``cohort-2026-04-05-test.md.evidence.json``.
    """
    sidecar: dict = {
        "cohort_name": cohort_name,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "gaps": {},
    }
    for g in gaps:
        key = f"{g.ticker}:{g.metric}"
        sidecar["gaps"][key] = {
            "reference_value": g.reference_value,
            "xbrl_value": g.xbrl_value,
            "components_found": g.components_found,
            "components_needed": g.components_needed,
            "variance_pct": g.variance,
            "root_cause": g.root_cause,
        }
    sidecar_path = Path(str(report_path) + ".evidence.json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2))
    return sidecar_path


def load_evidence_sidecar(
    report_path: Path,
    gaps: List[UnresolvedGapEntry],
) -> List[UnresolvedGapEntry]:
    """Enrich parsed gaps with evidence from companion JSON.

    Gracefully returns gaps unchanged if the sidecar is missing or corrupt.
    """
    sidecar_path = Path(str(report_path) + ".evidence.json")
    if not sidecar_path.exists():
        return gaps
    try:
        data = json.loads(sidecar_path.read_text())
    except (json.JSONDecodeError, OSError):
        return gaps

    evidence_map = data.get("gaps", {})
    for gap in gaps:
        key = f"{gap.ticker}:{gap.metric}"
        ev = evidence_map.get(key)
        if ev:
            gap.reference_value = ev.get("reference_value")
            gap.xbrl_value = ev.get("xbrl_value")
            gap.components_found = ev.get("components_found", 0)
            gap.components_needed = ev.get("components_needed", 0)
    return gaps
