"""
Extensible enumerations (GH #1255).

An extensible-enumeration concept (type ``enum2:enumerationItemType`` or
``enum2:enumerationSetItemType``) reports which members of a domain apply,
such as the balance-sheet lines that hold hedged assets. Its fact value is one
or more whitespace-separated expanded names::

    http://fasb.org/us-gaap/2023#MarketableSecuritiesCurrent http://fasb.org/us-gaap/2023#MarketableSecuritiesNoncurrent

``EnumerationDomain`` is what the concept's declaration says about the allowed
members (``XBRL.element_metadata(concept).enumeration``), and
``parse_enumeration_value`` splits a fact value into ``EnumerationMember``
records (``XBRL.enumeration_members(value)``). Neither validates a value
against the domain or resolves member labels.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from edgar.exceptions import ValidationError

__all__ = ['EnumerationDomain', 'EnumerationMember', 'parse_enumeration_value',
           'ENUMERATION_ITEM_TYPE', 'ENUMERATION_SET_ITEM_TYPE']

ENUMERATION_ITEM_TYPE = 'enumerationItemType'
ENUMERATION_SET_ITEM_TYPE = 'enumerationSetItemType'
_ENUMERATION_TYPES = (ENUMERATION_ITEM_TYPE, ENUMERATION_SET_ITEM_TYPE)


@dataclass(frozen=True)
class EnumerationDomain:
    """
    The declared domain of an extensible-enumeration concept.

    Attributes:
        domain: The ``enum2:domain`` attribute as written, a QName such as
            'us-gaap:AssetsAbstract': the head of the member list.
        linkrole: The ``enum2:linkrole`` attribute: the extended link role
            whose domain-member tree lists the allowed members.
        head_usable: Whether the domain head itself may be reported. The
            attribute defaults to False when absent; None means the declaration
            carries a value that is not an xs:boolean.
        is_set: True for ``enumerationSetItemType`` (a value may hold several
            members), False for ``enumerationItemType`` (exactly one).
    """
    domain: Optional[str]
    linkrole: Optional[str]
    head_usable: Optional[bool]
    is_set: bool


@dataclass(frozen=True)
class EnumerationMember:
    """
    One member named in an enumeration fact value.

    Attributes:
        namespace: The namespace URI, e.g. 'http://fasb.org/us-gaap/2023'.
        name: The local name, e.g. 'MarketableSecuritiesCurrent'.
        concept: The element id, e.g. 'us-gaap_MarketableSecuritiesCurrent',
            built from the prefix the filing binds to the namespace; None when
            the filing binds no prefix to it.
    """
    namespace: str
    name: str
    concept: Optional[str]


def _type_local_name(data_type: Optional[str]) -> Optional[str]:
    if not data_type:
        return None
    return data_type.rsplit(':', 1)[-1].rsplit('}', 1)[-1]


def parse_head_usable(value: Optional[str]) -> Optional[bool]:
    """xs:boolean: absent -> False (the enum2 default), unparseable -> None."""
    if value is None:
        return False
    text = value.strip()
    if text in ('true', '1'):
        return True
    if text in ('false', '0'):
        return False
    return None


def enumeration_domain(data_type: Optional[str], domain: Optional[str], linkrole: Optional[str],
                       head_usable: Optional[str]) -> Optional[EnumerationDomain]:
    """An EnumerationDomain from a declaration's type and enum attributes, or None for a non-enumeration."""
    type_name = _type_local_name(data_type)
    if type_name not in _ENUMERATION_TYPES and domain is None and linkrole is None:
        return None
    return EnumerationDomain(domain=domain or None,
                             linkrole=linkrole or None,
                             head_usable=parse_head_usable(head_usable),
                             is_set=type_name == ENUMERATION_SET_ITEM_TYPE)


def parse_enumeration_value(value: Optional[str],
                            namespace_prefixes: Optional[Dict[str, str]] = None) -> Tuple[EnumerationMember, ...]:
    """
    Split an extensible-enumeration fact value into its members.

    The value is split on any whitespace and each token on its last '#', so any
    URI scheme works. The concept id uses the prefix ``namespace_prefixes``
    (namespace URI -> prefix) binds to the member's namespace; a namespace with
    no binding gets ``concept=None`` rather than a prefix guessed from the URI.

    Args:
        value: The fact value. None, '' or whitespace (a nil fact) gives ().
        namespace_prefixes: The filing's namespace bindings.

    Returns:
        A tuple of EnumerationMember, in the order the value lists them.

    Raises:
        TypeError: value is not a string.
        ValidationError: a token is not a 'namespace#localName' expanded name.

    Example:
        >>> parse_enumeration_value('http://fasb.org/us-gaap/2023#MarketableSecuritiesCurrent',
        ...                         {'http://fasb.org/us-gaap/2023': 'us-gaap'})[0].concept
        'us-gaap_MarketableSecuritiesCurrent'
    """
    if value is None:
        return ()
    if not isinstance(value, str):
        raise TypeError(f"an enumeration value must be a string, not {type(value).__name__}")
    bindings = namespace_prefixes or {}
    members = []
    for token in value.split():
        namespace, hash_sign, name = token.rpartition('#')
        if not (hash_sign and namespace and name):
            raise ValidationError(
                f"{token!r} is not an extensible-enumeration member: expected an expanded name "
                f"'namespace#LocalName', e.g. 'http://fasb.org/us-gaap/2024#AssetsCurrent'",
                parameter='value', invalid_value=value)
        prefix = bindings.get(namespace)
        members.append(EnumerationMember(namespace=namespace, name=name,
                                         concept=f"{prefix}_{name}" if prefix else None))
    return tuple(members)
