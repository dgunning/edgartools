"""Deprecated names that still resolve, and warn when you use them.

Bead: edgartools-07lk.10.

Renaming a public class has two failure modes and this module exists to avoid
both. Aliasing the new name onto the old one leaves the deprecated spelling as
the real implementation, so the rename never actually happens (the trap
recorded in edgartools-07lk.23). Assigning `OldName = NewName` at module level
does perform the rename, but silently — nobody finds out until 6.0 deletes it.

`deprecated_alias` gives the third behaviour: the canonical class is the real
one, the old name resolves to *the same object* — so `except OldName:` and
`isinstance(x, OldName)` keep working — and touching the old name warns once
per call site.

    # edgar/dates.py
    from edgar._compat import deprecated_alias
    from edgar.exceptions import InvalidDateError

    __getattr__ = deprecated_alias(InvalidDateException=InvalidDateError)

PEP 562 module `__getattr__` covers both `module.OldName` and
`from module import OldName`. It does not cover static analysis: mypy will not
see these names. That is a feature for deprecated spellings — a type checker
pointing users at the canonical name is the outcome we want.
"""
from __future__ import annotations

import warnings
from typing import Any, Callable, Dict

__all__ = ["deprecated_alias"]


def deprecated_alias(__module_getattr__: Callable[[str], Any] = None,
                     **aliases: Any) -> Callable[[str], Any]:
    """Build a module-level `__getattr__` that resolves deprecated names.

    Args:
        __module_getattr__: an existing module `__getattr__` to fall through to,
            for modules that already define one. Optional.
        **aliases: `OldName=CanonicalObject` pairs.

    Returns:
        A function to assign to the module's `__getattr__`.
    """
    def __getattr__(name: str) -> Any:  # noqa: N807 - it IS a module __getattr__
        if name in aliases:
            target = aliases[name]
            canonical = getattr(target, "__name__", str(target))
            warnings.warn(
                f"{name} is deprecated and will be removed in v6.0. "
                f"Use {canonical} instead (from edgar.exceptions import {canonical}).",
                DeprecationWarning,
                stacklevel=2,
            )
            return target
        if __module_getattr__ is not None:
            return __module_getattr__(name)
        raise AttributeError(name)

    return __getattr__


def alias_map(**aliases: Any) -> Dict[str, Any]:
    """The alias mapping on its own, for tests that assert what is deprecated."""
    return dict(aliases)
