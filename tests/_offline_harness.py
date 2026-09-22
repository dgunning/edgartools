"""Opt-in pytest plugin: measure which tests can run with no network at all.

This answers one question reproducibly — *does this test need the SEC?* — and it
exists because that question has been answered by hand three times, each time
from scratch, and the filename heuristic it replaces was wrong for five files
the last time someone classified by eye (see the long comment in
``tests/conftest.py`` above ``REGRESSION_NETWORK_FILES``).

NOT LOADED BY DEFAULT. It must not run in the normal suite: it blocks outbound
sockets, which would turn every genuinely-networked test into an error. It is
loaded explicitly::

    hatch run test-offline-audit tests/issues/regression/
    pytest -p tests._offline_harness tests/issues/regression/

Anything that fails under it is a candidate for `network`. Re-run those failures
*without* the plugin before believing it: a test can fail offline because it is
already broken, which is a different fact and needs a different fix. That
separation is the whole procedure — in the 2026-08-04 classification all 159
offline failures passed on the network, so none was broken, but the run that
established it is what made the result trustworthy.

TWO CONTROLS, BOTH REQUIRED.

1. Outbound TCP and DNS raise at the socket layer, so a real fetch fails loudly
   instead of quietly succeeding. VCR replay is unaffected: vcrpy intercepts at
   the transport, above the socket, so a cassette-backed test never reaches here.

2. Every functools cache in the edgar package is cleared before each test. This
   is the control that is easy to omit and the one that decides the answer.
   Without it a test is credited with a fetch an earlier test already cached, so
   the result depends on execution order and xdist worker count. That is exactly
   what hid the quarterly-index coupling: four cassette-backed regression files
   measured as offline or networked depending on who ran first, because 64 of
   their tests resolved an accession through ``find()`` and no cassette records
   the quarterly index (bead edgartools-zuuu).

This is stricter than CI, where xdist workers share warm caches, and deliberately
so — a test that only passes offline because of a neighbour is not offline.

Local storage is popped for the same reason: CI has no mirror, so a test served
from one here would measure as offline and then fetch on a cold runner. A
cassette existing is likewise not evidence of replay — ``test_issue_880``'s
cassette held a quarterly index and nothing else, and its document had always
been fetched live past vcr (bead edgartools-07lk.12.3).
"""
from __future__ import annotations

import os
import socket
import sys
import warnings

import pytest

# CI has no local mirror; do not let one here mask a real fetch.
for _var in ("EDGAR_LOCAL_DATA_DIR", "EDGAR_USE_LOCAL_DATA"):
    os.environ.pop(_var, None)


class NetworkBlockedError(RuntimeError):
    """Raised in place of any outbound connection while the harness is loaded."""


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo
_real_create_connection = socket.create_connection


def _blocked(*args, **kwargs):
    raise NetworkBlockedError(
        "outbound network blocked by tests/_offline_harness.py — this test needs the SEC. "
        "Re-run it without -p tests._offline_harness to confirm it passes on the network "
        "before classifying it as `network`."
    )


def pytest_configure(config):
    # getaddrinfo and create_connection cover httpx/httpcore; the two socket
    # methods catch anything that builds its own socket and connects directly.
    socket.socket.connect = _blocked
    socket.socket.connect_ex = _blocked
    socket.getaddrinfo = _blocked
    socket.create_connection = _blocked


def pytest_unconfigure(config):
    socket.socket.connect = _real_connect
    socket.socket.connect_ex = _real_connect_ex
    socket.getaddrinfo = _real_getaddrinfo
    socket.create_connection = _real_create_connection


def _try_clear(obj, failures: list) -> int:
    """Clear one cache, recording rather than swallowing a refusal.

    A cache that quietly fails to clear is the worst outcome this file can
    produce: the next test is credited with a fetch an earlier one cached, and
    it measures as offline when it is not — the precise error the harness exists
    to rule out. So failures are collected and reported, not passed over. The
    walk still continues, because a third-party object that merely happens to
    expose `cache_clear` should not end the sweep.
    """
    try:
        obj.cache_clear()
        return 1
    except Exception as exc:
        failures.append(f"{getattr(obj, '__qualname__', obj)!s}: {exc!r}")
        return 0


def _clear_edgar_caches() -> tuple[int, list]:
    """Clear every functools cache reachable in already-imported edgar modules.

    Walks sys.modules rather than importing the package, so it only touches what
    the run has actually loaded. Returns (cleared, failures) so the caller can
    tell a working sweep from one that found nothing — a walk that clears zero
    caches is indistinguishable from no isolation at all.
    """
    cleared, failures = 0, []
    for name, module in list(sys.modules.items()):
        if not (name == "edgar" or name.startswith("edgar.")):
            continue
        if module is None:
            continue
        for attr in list(vars(module).values()):
            # module-level @lru_cache / @cache functions
            if hasattr(attr, "cache_clear"):
                cleared += _try_clear(attr, failures)
                continue
            # @lru_cache applied to methods, which live on the class
            if isinstance(attr, type):
                for member in list(vars(attr).values()):
                    if hasattr(member, "cache_clear"):
                        cleared += _try_clear(member, failures)
    return cleared, failures


_reported: set = set()


def _warn_once(key: str, message: str) -> None:
    """Report a broken control once, not once per test."""
    if key not in _reported:
        _reported.add(key)
        warnings.warn(message, stacklevel=2)


@pytest.fixture(autouse=True)
def _offline_isolation():
    """Deny each test the benefit of any fetch an earlier test cached."""
    cleared, failures = _clear_edgar_caches()
    if failures:
        _warn_once(
            "clear-failed",
            "offline harness could not clear "
            f"{len(failures)} edgar cache(s), so a test may be credited with an "
            f"earlier test's fetch and measure as offline when it is not: {failures[:5]}",
        )
    elif not cleared:
        # A warm edgar clears ~100. Zero means the walk found nothing, and a
        # silent no-op here would report the whole run as offline.
        _warn_once(
            "cleared-none",
            "offline harness cleared no edgar caches — cache isolation is not in "
            "effect and offline results from this run are not trustworthy.",
        )
    yield
