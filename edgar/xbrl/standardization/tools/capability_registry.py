"""
Capability-Aware Gap Triage: classify gaps by whether the engine can act on them.

Prevents wasting AI cycles on cosmetic gaps (sign-inverted metrics that already
pass CQS via abs() comparison, or industry_structural gaps with ref=None that
are already excluded from CQS denominator as "unverified").

Usage:
    from edgar.xbrl.standardization.tools.capability_registry import (
        GapDisposition, classify_gap_disposition, filter_actionable_gaps,
    )

    disposition = classify_gap_disposition(
        root_cause="sign_error",
        reference_value=-90e9,
        hv_subtype="hv_sign_inverted",
    )
    assert disposition == GapDisposition.SCORING_INERT
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edgar.xbrl.standardization.tools.auto_eval_loop import UnresolvedGap

logger = logging.getLogger(__name__)


class GapDisposition(str, Enum):
    """Whether a gap can be fixed AND whether fixing it improves CQS."""
    CONFIG_FIXABLE = "config_fixable"    # Can fix via config AND CQS improves
    SCORING_INERT = "scoring_inert"      # Correct fix exists but CQS unchanged
    ENGINE_BLOCKED = "engine_blocked"    # Cannot fix with current engine capabilities


def classify_gap_disposition(
    root_cause: Optional[str],
    reference_value: Optional[float],
    hv_subtype: Optional[str],
) -> GapDisposition:
    """Classify a gap's disposition based on root cause and scoring impact.

    Classification rules (derived from code tracing of auto_eval.py and
    reference_validator.py):

    - sign_error / hv_sign_inverted → SCORING_INERT
      (sign gaps that survive _classify_gap() filtering still won't improve CQS)
    - industry_structural with ref=None → SCORING_INERT
      (already "unverified" in CQS, excluded from denominator)
    - extension_concept → ENGINE_BLOCKED
      (company-specific extension, no standard concept available)
    - missing_concept / wrong_concept with ref not None → CONFIG_FIXABLE
    - Default → CONFIG_FIXABLE
    """
    # Sign-inverted metrics already pass CQS via abs() comparison
    if root_cause == "sign_error" or hv_subtype == "hv_sign_inverted":
        return GapDisposition.SCORING_INERT

    # Industry-structural with no reference value: already unverified in CQS
    if root_cause == "industry_structural" and reference_value is None:
        return GapDisposition.SCORING_INERT

    # Extension concepts: engine cannot resolve these
    if root_cause == "extension_concept":
        return GapDisposition.ENGINE_BLOCKED

    # Missing/wrong concept with a reference value: config can fix
    if root_cause in ("missing_concept", "wrong_concept") and reference_value is not None:
        return GapDisposition.CONFIG_FIXABLE

    # Default: assume config-fixable
    return GapDisposition.CONFIG_FIXABLE


def classify_unresolved_gap(gap: 'UnresolvedGap') -> GapDisposition:
    """Classify an UnresolvedGap by its scoring impact."""
    return classify_gap_disposition(
        root_cause=gap.root_cause,
        reference_value=gap.reference_value,
        hv_subtype=gap.hv_subtype,
    )


def filter_actionable_gaps(gaps: List['UnresolvedGap']) -> List['UnresolvedGap']:
    """Return only config_fixable gaps, logging skip counts."""
    actionable = []
    skipped = 0
    for gap in gaps:
        if gap.disposition != GapDisposition.CONFIG_FIXABLE:
            skipped += 1
            logger.info(
                f"Skipping {gap.ticker}:{gap.metric} — disposition={gap.disposition} "
                f"(root_cause={gap.root_cause})"
            )
        else:
            actionable.append(gap)
    if skipped:
        logger.info(f"Triage: {skipped} gaps skipped (scoring_inert/engine_blocked), "
                     f"{len(actionable)} actionable gaps remain")
    return actionable


def triage_gaps(gaps: List['UnresolvedGap']) -> Dict[GapDisposition, List['UnresolvedGap']]:
    """Partition a list of gaps by disposition."""
    result: Dict[GapDisposition, List['UnresolvedGap']] = {
        GapDisposition.CONFIG_FIXABLE: [],
        GapDisposition.SCORING_INERT: [],
        GapDisposition.ENGINE_BLOCKED: [],
    }
    for gap in gaps:
        disposition = classify_unresolved_gap(gap)
        result[disposition].append(gap)
    return result


def print_triage_summary(gaps: List['UnresolvedGap']) -> None:
    """Print a Rich-formatted triage summary table."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        triaged = triage_gaps(gaps)
        for disp, group in triaged.items():
            print(f"  {disp.value}: {len(group)} gaps")
        return

    console = Console()
    triaged = triage_gaps(gaps)

    table = Table(title="Gap Triage Summary", show_lines=True)
    table.add_column("Disposition", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Action", style="dim")

    style_map = {
        GapDisposition.CONFIG_FIXABLE: ("green", "Dispatch to AI"),
        GapDisposition.SCORING_INERT: ("yellow", "Skip (no CQS impact)"),
        GapDisposition.ENGINE_BLOCKED: ("red", "Log and skip"),
    }

    for disp in GapDisposition:
        count = len(triaged.get(disp, []))
        style, action = style_map[disp]
        table.add_row(f"[{style}]{disp.value}[/{style}]", str(count), action)

    total = len(gaps)
    fixable = len(triaged[GapDisposition.CONFIG_FIXABLE])
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]", f"{fixable} actionable")

    console.print(table)

    # Detail breakdown for scoring_inert
    inert = triaged[GapDisposition.SCORING_INERT]
    if inert:
        sign_inert = [g for g in inert if g.root_cause == "sign_error" or g.hv_subtype == "hv_sign_inverted"]
        struct_inert = [g for g in inert if g.root_cause == "industry_structural"]
        console.print(f"  [yellow]Scoring-inert breakdown:[/yellow] "
                      f"{len(sign_inert)} sign-inverted, {len(struct_inert)} industry-structural")
