"""O55: Derivation planner for computed metrics.

Resolves metrics that can be derived from accounting identities using
already-resolved component concepts. For example, GrossProfit = Revenue - COGS.

The signed formula engine (ADD_STANDARDIZATION) already exists — this module
discovers WHICH company-specific concepts to use by looking up resolved
orchestrator results for the component metrics.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Accounting identities: metric = sum of (component, sign) pairs.
# Sign: +1 means add, -1 means subtract.
# Order matters for topological resolution — leaf metrics first.
ACCOUNTING_IDENTITIES: Dict[str, List[Tuple[str, int]]] = {
    "GrossProfit": [
        ("Revenue", +1),
        ("COGS", -1),
    ],
    "OperatingIncome": [
        ("Revenue", +1),
        ("COGS", -1),
        ("SGA", -1),
        ("ResearchAndDevelopment", -1),
    ],
    "TotalLiabilities": [
        ("TotalAssets", +1),
        ("StockholdersEquity", -1),
    ],
    "NetIncome": [
        ("OperatingIncome", +1),
        ("InterestExpense", -1),
        ("IncomeTaxExpense", -1),
    ],
    "TotalDebt": [
        ("ShortTermDebt", +1),
        ("LongTermDebt", +1),
    ],
}

# Topological order: resolve leaf metrics before composites
RESOLUTION_ORDER = [
    "TotalDebt",
    "GrossProfit",
    "TotalLiabilities",
    "OperatingIncome",
    "NetIncome",
]


@dataclass
class DerivationProposal:
    """A proposal to derive a metric from a formula."""
    ticker: str
    metric: str
    formula: str                          # Human-readable: "Revenue - COGS"
    components: Dict[str, str]            # metric -> resolved XBRL concept
    missing_components: List[str]         # Components not yet resolved
    confidence: float                     # 0.0-1.0 based on component coverage

    @property
    def is_complete(self) -> bool:
        """All components are resolved."""
        return len(self.missing_components) == 0


def derive_formula_from_identity(
    ticker: str,
    metric: str,
    orchestrator_results: Dict[str, 'MappingResult'],
) -> Optional[DerivationProposal]:
    """Look up accounting identity, find resolved component concepts, emit proposal.

    Args:
        ticker: Company ticker.
        metric: The metric to derive (e.g., "GrossProfit").
        orchestrator_results: Mapping results for this company from the orchestrator.
            Dict of metric_name -> MappingResult with .concept attribute.

    Returns:
        DerivationProposal if the metric has an identity and at least some
        components are resolved. None if no identity exists.
    """
    identity = ACCOUNTING_IDENTITIES.get(metric)
    if not identity:
        return None

    components: Dict[str, str] = {}
    missing: List[str] = []
    formula_parts: List[str] = []

    for component_metric, sign in identity:
        result = orchestrator_results.get(component_metric)
        concept = None
        if result is not None and hasattr(result, 'concept') and result.concept:
            concept = result.concept

        if concept:
            components[component_metric] = concept
        else:
            missing.append(component_metric)

        sign_str = "+" if sign > 0 else "-"
        if formula_parts:
            formula_parts.append(f"{sign_str} {component_metric}")
        else:
            formula_parts.append(component_metric if sign > 0 else f"-{component_metric}")

    formula = " ".join(formula_parts)
    total = len(identity)
    resolved = total - len(missing)
    confidence = resolved / total if total > 0 else 0.0

    proposal = DerivationProposal(
        ticker=ticker,
        metric=metric,
        formula=formula,
        components=components,
        missing_components=missing,
        confidence=confidence,
    )

    if proposal.is_complete:
        logger.info(
            f"[DERIVATION] {ticker}:{metric} = {formula} "
            f"(all {total} components resolved)"
        )
    elif resolved > 0:
        logger.info(
            f"[DERIVATION] {ticker}:{metric} = {formula} "
            f"({resolved}/{total} components resolved, missing: {missing})"
        )

    return proposal


def to_config_change(proposal: DerivationProposal) -> Optional['ConfigChange']:
    """Convert a complete DerivationProposal to a ConfigChange (ADD_STANDARDIZATION).

    Only emits a change if ALL components are resolved.

    Returns:
        ConfigChange or None if proposal is incomplete.
    """
    if not proposal.is_complete:
        return None

    from edgar.xbrl.standardization.tools.auto_eval_loop import ConfigChange, ChangeType

    # Build the standardization formula value
    # Format: "component1_concept [+-] component2_concept"
    identity = ACCOUNTING_IDENTITIES[proposal.metric]
    formula_parts = []
    for component_metric, sign in identity:
        concept = proposal.components[component_metric]
        if sign > 0:
            formula_parts.append(concept)
        else:
            formula_parts.append(f"-{concept}")

    formula_value = " ".join(formula_parts)

    return ConfigChange(
        file="metrics.yaml",
        change_type=ChangeType.ADD_STANDARDIZATION,
        yaml_path=f"metrics.{proposal.metric}.standardization",
        new_value={
            "formula": formula_value,
            "source": "derivation_planner",
            "components": proposal.components,
        },
        rationale=(
            f"O55 derivation: {proposal.metric} = {proposal.formula} "
            f"using resolved concepts for {proposal.ticker}"
        ),
        target_metric=proposal.metric,
        target_companies=proposal.ticker,
    )


def plan_derivations(
    ticker: str,
    orchestrator_results: Dict[str, 'MappingResult'],
    failed_metrics: Optional[List[str]] = None,
) -> List[DerivationProposal]:
    """Plan derivations for all failed metrics that have accounting identities.

    Processes metrics in topological order (RESOLUTION_ORDER) so that
    leaf metrics are resolved before composites that depend on them.

    Args:
        ticker: Company ticker.
        orchestrator_results: Current mapping results for this company.
        failed_metrics: List of metrics that need resolution. If None,
            checks all metrics in ACCOUNTING_IDENTITIES.

    Returns:
        List of DerivationProposals (complete ones first, sorted by confidence).
    """
    targets = failed_metrics if failed_metrics else list(ACCOUNTING_IDENTITIES.keys())

    # Filter to metrics that have identities
    derivable = [m for m in RESOLUTION_ORDER if m in targets and m in ACCOUNTING_IDENTITIES]

    proposals = []
    for metric in derivable:
        proposal = derive_formula_from_identity(ticker, metric, orchestrator_results)
        if proposal is not None:
            proposals.append(proposal)

    # Sort: complete proposals first, then by confidence
    proposals.sort(key=lambda p: (-int(p.is_complete), -p.confidence))

    return proposals
