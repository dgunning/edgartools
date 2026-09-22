"""Deprecated import location for the Form 144 parser.

`Form144` moved to `edgar.ownership.form144` (bead edgartools-07lk.12.1): Form 144
is an affiliate's notice of a proposed sale of restricted stock, so it now sits
with the Forms 3/4/5 ownership parsers instead of loose at the top of the
package.

This shim re-exports the new module unchanged and is REMOVED IN 6.0. Import
from `edgar.ownership.form144` instead. `filing.obj()` already routes to the new
path, so ordinary use never reaches this module.
"""

import warnings

from edgar.ownership import form144 as _moved

__all__ = list(getattr(_moved, "__all__", ()))

_MOVED = (
    "edgar.form144 has moved to edgar.ownership.form144 and will be removed in "
    "edgartools 6.0. Import from edgar.ownership.form144 instead."
)


def __getattr__(name: str):
    # PEP 562. Forwarding by attribute rather than re-exporting a fixed list
    # keeps object IDENTITY — `edgar.form144.Form144 is
    # edgar.ownership.form144.Form144` — so isinstance checks and pickles written
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
