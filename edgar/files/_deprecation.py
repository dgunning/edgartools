"""Frame-gated deprecation helper for legacy edgar.files.* modules.

The legacy HTML stack (edgar.files.html, edgar.files.html_documents,
edgar.files.htmltools) is deprecated in favor of edgar.documents, but
edgartools' own code still instantiates these classes during normal
operation. Naive module-top warnings.warn() calls fire on every
internal import and pollute downstream test suites that run with
``-W error`` — turning every ``import edgar`` into a failure.

This helper suppresses the deprecation signal when the call site is
edgartools-internal, and re-emits it for user code so the deprecation
notice is preserved where it matters.
"""

import inspect
import warnings

# Modules that are transparent to the caller check: the deprecated
# modules themselves and (for dataclass-generated __init__ trampolines)
# the standard library's dataclasses module. The dataclass machinery
# emits an __init__ that runs in the *defining* module's namespace, so
# we also skip the deprecated modules when walking up.
_TRANSPARENT_MODULES = frozenset({
    'edgar.files._deprecation',
    'edgar.files.html',
    'edgar.files.html_documents',
    'edgar.files.htmltools',
    'dataclasses',
})


def warn_legacy_html_usage(message: str) -> None:
    """Emit a ``DeprecationWarning`` unless the call site is internal.

    Walks up the call stack past the deprecation helper and the
    deprecated modules themselves (and the ``dataclasses`` module that
    hosts synthesized ``__init__`` trampolines) to find the first
    non-transparent frame. If that frame's module is ``edgar`` or any
    ``edgar.*`` submodule, the call is internal and the warning is
    suppressed. Any other caller — user code, notebooks, third-party
    libraries, tests — receives the standard ``DeprecationWarning`` at
    its own call site.
    """
    current = inspect.currentframe()
    frame = current.f_back if current is not None else None
    while frame is not None:
        mod_name = frame.f_globals.get('__name__', '')
        if mod_name in _TRANSPARENT_MODULES:
            frame = frame.f_back
            continue
        if mod_name == 'edgar' or mod_name.startswith('edgar.'):
            return  # edgartools-internal call — stay quiet
        break

    warnings.warn(message, DeprecationWarning, stacklevel=3)
