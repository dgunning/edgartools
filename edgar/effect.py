"""Deprecated import location for the EFFECT parser.

`Effect` moved to `edgar.offerings.effect` (bead edgartools-07lk.12.1): a
notice of effectiveness is a registration-lifecycle document, and it now sits
with the S-1/S-3/S-4, 424B and Form C/D parsers instead of loose at the top of
the package.

This shim re-exports the new module unchanged and is REMOVED IN 6.0. Import
from `edgar.offerings.effect` instead. `filing.obj()` already routes to the new
path, so ordinary use never reaches this module.
"""

import warnings

from edgar.offerings import effect as _moved

__all__ = list(getattr(_moved, "__all__", ()))

_MOVED = (
    "edgar.effect has moved to edgar.offerings.effect and will be removed in "
    "edgartools 6.0. Import from edgar.offerings.effect instead."
)


def __getattr__(name: str):
    # PEP 562. Forwarding by attribute rather than re-exporting a fixed list
    # keeps object IDENTITY — `edgar.effect.Effect is
    # edgar.offerings.effect.Effect` — so isinstance checks and pickles written
    # against either path agree. A hand-maintained re-export list would drift
    # the day a name is added to the real module.
    try:
        value = getattr(_moved, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    warnings.warn(_MOVED, DeprecationWarning, stacklevel=2)
    return value


def __dir__():
    return sorted(set(__all__) | set(dir(_moved)))
