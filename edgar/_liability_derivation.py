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


def derive_from_balance_sheet(xbrl, role, period, accession):
    period_key = f"instant_{period}"
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

    def descendants(concept, path=frozenset()):
        if concept in path:
            raise LiabilityDerivationError("cyclic-components", concept)
        children = set()
        for arc in arcs.get(concept, ()):
            children.add(arc.child_id)
            children.update(descendants(arc.child_id, path | {concept}))
        return children

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

    currencies = set()

    def read(concept, weight):
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

    components: list[LiabilityLineItem] = []
    equity: list[LiabilityLineItem] = []
    temporary: list[LiabilityLineItem] = []
    used = set()
    for arc in arcs[_COMBINED]:
        concept = arc.child_id
        if arc.weight != 1:
            raise LiabilityDerivationError("unsupported-weight", concept)
        branch = {concept} | descendants(concept)
        if used & branch:
            raise LiabilityDerivationError("overlapping-components", concept)
        used.update(branch)
        if concept == _CONTINGENCIES and rows.get(concept, {}).get("values", {}).get(period_key) in (None, ""):
            continue
        if concept in (_PARENT_EQUITY, _TOTAL_EQUITY):
            equity.append(read(concept, -1))
        elif concept in _TEMPORARY:
            temporary.append(read(concept, -1))
        elif _is_liability(rows.get(concept, {"concept": concept})):
            components.append(read(concept, 1))
        elif concept not in rows or rows[concept].get("values", {}).get(period_key) in (None, ""):
            raise LiabilityDerivationError("missing-component", concept)
        else:
            raise LiabilityDerivationError("unclassified-component", concept)

    if len(equity) != 1 or len(temporary) > 1:
        raise LiabilityDerivationError("ambiguous-equity", period)
    if equity[0].concept == _PARENT_EQUITY and _NCI in rows:
        raise LiabilityDerivationError("ambiguous-noncontrolling-interest", period)
    if not components:
        raise LiabilityDerivationError("missing-liability-components", period)

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
