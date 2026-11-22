"""
Prohibiting and overriding relationships, shared by every linkbase parser.

XBRL 2.1 section 3.5.3.9.7 decides which arcs in a DTS become relationships in
a network. Every parser (presentation, calculation, definition, label) records
each arc it reads as a candidate with `arc_candidate`, then keeps only what
`effective_relationships` returns. The rules, in brief:

- Arcs are grouped into base sets (3.5.3.9.7.3): the same arc element and
  `xlink:arcrole`, inside extended links of the same element and `xlink:role`.
- Within a base set, two relationships are equivalent (3.5.3.9.7.4) when their
  "from" and "to" fragments are identical and every non-exempt attribute is
  S-Equal. `use`, `priority` and attributes in the xlink and xmlns namespaces
  are exempt; `order`, `weight`, `preferredLabel` and `xbrldt:*` are not.
- Of a set of equivalent relationships (3.5.3.9.7.5): a prohibiting one
  (`use="prohibited"`) is never in the network; if the highest priority holds a
  prohibiting relationship, none of the set is; otherwise one relationship of
  the highest priority is, and the rest are overridden. Which one of several
  equally high is application dependent; this keeps the first in document
  order, which is what every parser did before prohibition was honoured.
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Hashable, Iterable, List, Optional, Tuple

XLINK_NS = "http://www.w3.org/1999/xlink"
XMLNS_NS = "http://www.w3.org/2000/xmlns/"
XBRLDT_NS = "http://xbrl.org/2005/xbrldt"

# Attributes whose S-Equal comparison (XBRL 2.1 section 4.10) is on the typed
# value, so order="1.0000" and order="1" are the same attribute value.
_DECIMAL_ATTRIBUTES = frozenset({"order", "weight"})
_BOOLEAN_ATTRIBUTES = frozenset({f"{{{XBRLDT_NS}}}closed", f"{{{XBRLDT_NS}}}usable"})

# Equivalence is judged after defaults are applied (3.5.3.9.7.4, note), so an
# absent `order` compares equal to order="1", the value 3.5.3.9.5 says it MUST
# default to. No other arc attribute these parsers read has a default that
# applies when it is absent: the xbrldt attributes are global attributes reached
# through the arc's anyAttribute wildcard, and a global attribute's default
# applies only through an attribute use.
_DEFAULTS = {"order": Decimal(1)}

# Exempt from equivalence (3.5.3.9.7.4): use, priority, and the xlink and xmlns
# namespaces. lxml does not report namespace declarations as attributes.
_EXEMPT_ATTRIBUTES = frozenset({"use", "priority"})


def _typed_value(name: str, value: str) -> Hashable:
    """An attribute's value as the type S-Equal compares it by."""
    value = value.strip()
    if name in _DECIMAL_ATTRIBUTES:
        try:
            return Decimal(value).normalize()
        except InvalidOperation:
            return value
    if name in _BOOLEAN_ATTRIBUTES:
        return value in ("true", "1")
    return value


def non_exempt_attributes(arc) -> Tuple[Tuple[str, Hashable], ...]:
    """
    The arc's non-exempt attributes with defaults applied, as a sorted tuple.

    Two arcs whose tuples are equal have the same number of non-exempt
    attributes and an S-Equal partner for each (XBRL 2.1 section 3.5.3.9.7.4).
    """
    values: Dict[str, Hashable] = dict(_DEFAULTS)
    for name, value in arc.attrib.items():
        if name in _EXEMPT_ATTRIBUTES or name.startswith(f"{{{XLINK_NS}}}") or name.startswith(f"{{{XMLNS_NS}}}"):
            continue
        values[name] = _typed_value(name, value)
    return tuple(sorted(values.items(), key=lambda item: item[0]))


def arc_priority(arc) -> int:
    """The arc's priority (XBRL 2.1 section 3.5.3.9.7.2): an integer, default 0."""
    try:
        return int(arc.get("priority", "0").strip())
    except (AttributeError, ValueError):
        return 0


def is_prohibiting(arc) -> bool:
    """Whether the arc is a prohibiting relationship (section 3.5.3.9.7.1)."""
    return (arc.get("use") or "optional").strip() == "prohibited"


def arc_candidate(arc, role: str, from_id: Hashable, to_id: Hashable,
                  payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Record one relationship an arc represents, for `effective_relationships`.

    Args:
        arc: The lxml arc element.
        role: The `xlink:role` of the extended link the arc sits in.
        from_id, to_id: What the arc's "from" and "to" sides resolve to. Two
            relationships whose sides resolve to the same values are taken to
            reference identical fragments (a concept by its element ID; a
            resource by whatever identity the caller gives it).
        payload: The parser's own fields for the relationship; returned with
            the candidate when it is effective.

    The candidate carries `equivalence` (the base set, both sides and the
    non-exempt attributes), `prohibiting` and `priority`.
    """
    link = arc.getparent()
    base_set = (
        link.tag if link is not None else None,
        role,
        arc.tag,
        arc.get(f"{{{XLINK_NS}}}arcrole"),
    )
    candidate = dict(payload or {})
    candidate["equivalence"] = (base_set, from_id, to_id, non_exempt_attributes(arc))
    candidate["prohibiting"] = is_prohibiting(arc)
    candidate["priority"] = arc_priority(arc)
    return candidate


def candidate_key(candidate: Dict[str, Any]) -> Tuple:
    """
    What makes two candidates interchangeable for `effective_relationships`.

    Re-reading a linkbase repeats every candidate. A repeat with the same
    equivalence, use and priority cannot change which relationship is effective,
    so a parser that accumulates candidates across reads may keep it once.
    """
    return candidate["equivalence"], candidate["prohibiting"], candidate["priority"]


def effective_relationships(candidates: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    The candidates that participate in their networks, in document order.

    Applies XBRL 2.1 section 3.5.3.9.7.5 to every set of equivalent candidates:
    prohibiting relationships are never included; if the highest priority in a
    set holds a prohibiting relationship, nothing in the set is included;
    otherwise the first relationship of the highest priority is included and
    every other is overridden.
    """
    candidates = list(candidates)
    winners: Dict[Hashable, int] = {}
    blocked: Dict[Hashable, int] = {}

    for index, candidate in enumerate(candidates):
        key = candidate["equivalence"]
        priority = candidate["priority"]
        if candidate["prohibiting"]:
            if key not in blocked or priority > blocked[key]:
                blocked[key] = priority
            continue
        held = winners.get(key)
        if held is None or priority > candidates[held]["priority"]:
            winners[key] = index

    effective = {
        index for key, index in winners.items()
        if key not in blocked or candidates[index]["priority"] > blocked[key]
    }
    return [candidate for index, candidate in enumerate(candidates) if index in effective]
