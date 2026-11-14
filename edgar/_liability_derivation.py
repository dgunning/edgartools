"""Conservative reconstruction from a single filed balance-sheet role."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_ASSETS = "us-gaap_Assets"
_COMBINED = "us-gaap_LiabilitiesAndStockholdersEquity"
_PARENT_EQUITY = "us-gaap_StockholdersEquity"
_TOTAL_EQUITY = "us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
_NCI = "us-gaap_MinorityInterest"
_TEMPORARY = {
    "us-gaap_TemporaryEquityCarryingAmount",
    "us-gaap_TemporaryEquityCarryingAmountAttributableToParent",
    "us-gaap_RedeemableNoncontrollingInterestEquityCarryingAmount",
}
_CONTINGENCIES = "us-gaap_CommitmentsAndContingencies"


@dataclass(frozen=True)
class LiabilityLineItem:
    """One filed input and its sign in the indicated calculation."""

    concept: str
    label: str
    value: Decimal
    weight: int


@dataclass(frozen=True)
class LiabilityDerivation:
    """Auditable result from two independent calculations of total liabilities."""

    value: Decimal
    period: str
    currency: str
    accession: str | None
    components: tuple[LiabilityLineItem, ...]
    identity_inputs: tuple[LiabilityLineItem, ...]
    component_total: Decimal
    identity_total: Decimal


class LiabilityDerivationError(ValueError):
    """The balance sheet does not support a safe derivation."""

    def __init__(self, reason: str, detail: str):
        self.reason = reason
        super().__init__(f"{reason}: {detail}")


def _is_liability(row):
    concept = row["concept"]
    name = concept.split("_", 1)[-1]
    if row.get("balance") != "credit":
        return False
    if concept.startswith("us-gaap_") and name in {
        "LiabilitiesCurrent", "LiabilitiesNoncurrent", "LongTermDebtNoncurrent",
    }:
        return True
    return name.endswith(("LiabilityNoncurrent", "LiabilitiesNoncurrent"))


def _sum_items(items):
    return sum((item.value * item.weight for item in items), Decimal(0))


def _balance_sheet_arcs(xbrl, role):
    tree = xbrl.calculation_trees.get(role)
    if not tree:
        raise LiabilityDerivationError("missing-calculation-role", role)

    arcs = {}
    arcroles = {arc.arcrole for arc in tree.all_arcs if arc.parent_id == _COMBINED}
    if not arcroles:
        raise LiabilityDerivationError("missing-liability-components", role)
    if len(arcroles) != 1:
        raise LiabilityDerivationError("ambiguous-calculation-network", role)
    arcrole = arcroles.pop()
    for arc in tree.all_arcs:
        if arc.arcrole == arcrole:
            arcs.setdefault(arc.parent_id, []).append(arc)
    return arcs


def _descendants(arcs, concept, path=frozenset()):
    if concept in path:
        raise LiabilityDerivationError("cyclic-components", concept)
    children = set()
    for arc in arcs.get(concept, ()):
        children.add(arc.child_id)
        children.update(_descendants(arcs, arc.child_id, path | {concept}))
    return children


def _balance_sheet_rows(xbrl, role, period_key):
    rows = {}
    for row in xbrl.get_statement(role, period_filter=period_key, should_display_dimensions=False):
        if row.get("is_abstract"):
            continue
        concept = row["concept"]
        if concept in rows:
            keys = ("values", "units")
            if any(row.get(key) != rows[concept].get(key) for key in keys):
                raise LiabilityDerivationError("ambiguous-component", concept)
        rows[concept] = row
    return rows


def _read_item(xbrl, rows, period_key, currencies, concept, weight):
    row = rows.get(concept, {})
    raw = row.get("values", {}).get(period_key)
    if raw is None or raw == "":
        raise LiabilityDerivationError("missing-component", concept)
    currency = xbrl._currency_measure(row.get("units", {}).get(period_key))
    if currency is None:
        raise LiabilityDerivationError("invalid-currency", concept)
    currencies.add(currency)
    try:
        value = Decimal(str(raw))
    except InvalidOperation as error:
        raise LiabilityDerivationError("invalid-component", concept) from error
    if not value.is_finite():
        raise LiabilityDerivationError("invalid-component", concept)
    return LiabilityLineItem(concept, row["label"], value, weight)


def _component_kind(rows, period_key, concept):
    row = rows.get(concept, {"concept": concept})
    missing = row.get("values", {}).get(period_key) in (None, "")
    if concept == _CONTINGENCIES and missing:
        return None
    if concept in (_PARENT_EQUITY, _TOTAL_EQUITY):
        return "equity"
    if concept in _TEMPORARY:
        return "temporary"
    if _is_liability(row):
        return "liability"
    reason = "missing-component" if missing else "unclassified-component"
    raise LiabilityDerivationError(reason, concept)


def _collect_components(arcs, rows, period_key, read):
    groups: dict[str, list[LiabilityLineItem]] = {"liability": [], "equity": [], "temporary": []}
    used = set()
    for arc in arcs[_COMBINED]:
        concept = arc.child_id
        if arc.weight != 1:
            raise LiabilityDerivationError("unsupported-weight", concept)
        branch = {concept} | _descendants(arcs, concept)
        if used & branch:
            raise LiabilityDerivationError("overlapping-components", concept)
        used.update(branch)
        kind = _component_kind(rows, period_key, concept)
        if kind is not None:
            groups[kind].append(read(concept, 1 if kind == "liability" else -1))
    return groups, used


def _validate_components(components, equity, temporary, rows, period):
    if len(equity) != 1 or len(temporary) > 1:
        raise LiabilityDerivationError("ambiguous-equity", period)
    if equity[0].concept == _PARENT_EQUITY and _NCI in rows:
        raise LiabilityDerivationError("ambiguous-noncontrolling-interest", period)
    if not components:
        raise LiabilityDerivationError("missing-liability-components", period)


def _check_face_rows(rows, period_key, used):
    # A monetary row on the liabilities/equity side with no calculation
    # relationship might be an omitted input. Refuse to guess where it belongs.
    seen_assets = False
    for concept, row in rows.items():
        if concept == _ASSETS:
            seen_assets = True
        elif concept == _COMBINED:
            break
        elif seen_assets and concept not in used and row.get("values", {}).get(period_key) not in (None, ""):
            raise LiabilityDerivationError("unclassified-face-row", concept)


def derive_from_balance_sheet(xbrl, role, period, accession):
    period_key = f"instant_{period}"
    arcs = _balance_sheet_arcs(xbrl, role)
    rows = _balance_sheet_rows(xbrl, role, period_key)
    currencies = set()

    def read(concept, weight):
        return _read_item(xbrl, rows, period_key, currencies, concept, weight)

    groups, used = _collect_components(arcs, rows, period_key, read)
    components, equity, temporary = groups["liability"], groups["equity"], groups["temporary"]
    _validate_components(components, equity, temporary, rows, period)
    _check_face_rows(rows, period_key, used)

    assets = read(_ASSETS, 1)
    combined = read(_COMBINED, 1)
    if len(currencies) != 1:
        raise LiabilityDerivationError("mixed-currencies", period)
    identity_inputs = [assets, *equity, *temporary]
    component_total = _sum_items(components)
    identity_total = _sum_items(identity_inputs)
    if assets.value != combined.value or component_total != identity_total or component_total < 0:
        raise LiabilityDerivationError("cross-check-mismatch", period)

    return LiabilityDerivation(
        component_total, period, currencies.pop().split(":")[-1], accession,
        tuple(components), tuple(identity_inputs), component_total, identity_total,
    )
