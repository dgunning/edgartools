"""The one exception vocabulary for edgartools.

Bead: edgartools-07lk.10. Design:
docs-internal/planning/active-tasks/2026-08-11-07lk10-error-hierarchy-design.md

A root and four branches, which is the whole tree:

    EdgarError
    ├── TransportError    we could not get an answer from SEC
    ├── NotFoundError     you named a thing and it does not exist
    ├── ParsingError      we got bytes and could not build the promised object
    └── ValidationError   your input was wrong before we ever asked

Before this module there were 27 exception classes across ten packages with no
shared base and no cross-package inheritance, of which exactly two were
reachable from the top-level namespace. `except` clauses had to name types from
whichever module happened to raise, and the most common thing we raised was a
bare `ValueError` (135 of them).

WHY THE BRANCHES INHERIT BUILTINS. `ValidationError` is a `ValueError` and
`NotFoundError` is a `LookupError`, so converting a raw `raise ValueError` to a
typed error does not break the `except ValueError:` written against it — the
conversion is additive rather than a break, which is what lets it ship in 5.x
instead of waiting for 6.0. The root stays clean: `except ValueError` catching a
network timeout would be absurd.

RULES FOR THIS MODULE:
  - stdlib imports only, at module level. Every other edgar module must be able
    to import this one, so this one may import none of them.
  - No third-party type (httpx above all) appears in a signature, base class or
    annotation here. That is what makes a future httpx swap a non-event.
  - A class whose construction needs edgar internals or a third-party object
    stays defined in its own module and subclasses a branch from here. Today
    that means `SSLVerificationError` (it categorizes an httpx error to build
    its message) and the eight `edgar.documents` parser subclasses.
"""
from __future__ import annotations

import os
import warnings
from typing import Any, Dict, List, Optional

__all__ = [
    # helpers
    "strict_errors_enabled",
    "http_status",
    "warn_will_raise",
    # root
    "EdgarError",
    # transport
    "TransportError",
    "TooManyRequestsError",
    "IdentityError",
    "IdentityNotSetError",
    "SECIdentityError",
    # not found
    "NotFoundError",
    "CompanyNotFoundError",
    "FilingNotFoundError",
    "CompanyFactsNotFoundError",
    "StatementNotFoundError",
    "SectionNotFoundError",
    "AttachmentNotFoundError",
    # parsing
    "ParsingError",
    "XBRLProcessingError",
    "DataObjectError",
    # validation
    "ValidationError",
    "InvalidDateError",
]


_TRUTHY = frozenset({"1", "true", "yes", "on"})


def strict_errors_enabled() -> bool:
    """True when `EDGARTOOLS_STRICT_ERRORS` asks for 6.0 error behaviour today.

    Under strict, the changes that would otherwise be a 6.0 break run now: the
    network boundary wraps httpx errors into `TransportError`, and the silent
    `None` returns raise instead. Two payoffs — a user can port before the break
    lands, and our own CI gets a job that runs the whole suite the 6.0 way,
    which is what flushes out internal code still relying on the old behaviour.

    Read fresh on every call rather than captured at import, so a test can set
    the variable, exercise a code path, and unset it. The branches this gates
    are all deleted in 6.0, when strict becomes the only path.
    """
    return os.environ.get("EDGARTOOLS_STRICT_ERRORS", "").strip().lower() in _TRUTHY


def http_status(exc: BaseException) -> Optional[int]:
    """The HTTP status behind a failure, whichever era raised it.

    `TransportError` carries `.status_code`; an httpx `HTTPStatusError` carries
    `.response.status_code`. Every dual-era `except` needs to ask the same
    question of both, and asking it through `getattr` rather than an isinstance
    check is what keeps this module free of any httpx import.

    Returns None when we never got an answer at all — a connection failure, a
    timeout, or a client-side refusal such as a missing identity. That None is
    load-bearing: it is the discriminator between "SEC said no" and "we could
    not ask", which is the whole distinction the transport branch exists for.
    """
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status
    return getattr(getattr(exc, "response", None), "status_code", None)


def warn_will_raise(error: "EdgarError", *, stacklevel: int = 3) -> None:
    """Stage a 6.0 error change at the exact line that changes.

    Call this where a function is about to return `None` for something 6.0 will
    raise on. Under strict it raises `error` now — which is what the strict CI
    job exercises and what a user porting early gets. Otherwise it warns and
    returns, and the caller carries on doing exactly what it does today.

    The warning names what the call becomes, so the thing the user reads while
    porting is the thing they will catch. That matters more than it sounds: a
    warning that says "this will change" without naming what it becomes leaves
    the reader to go and find out.

    `FutureWarning`, not `DeprecationWarning`. Nothing here is deprecated —
    these calls stay, they just stop answering `None`. And Python hides
    `DeprecationWarning` outside `__main__` by default, which would silence it
    for exactly the users who most need it: the ones whose code is a library too.

    The warning text has to be *stable per call site*, which is why it comes
    from `error.warning_summary` rather than from `str(error)`. Python's default
    filter suppresses a repeat only when the text matches exactly, so a message
    carrying the accession number defeats it: a corpus loop over ten thousand
    filings emits ten thousand warnings, one per filing, which reads as a broken
    library rather than a considerate one. The per-filing detail is not lost —
    it stays on the error, which is what strict mode raises and what 6.0 will
    raise, and that is the copy the user debugs against.

    An error with no `warning_summary` falls back to `str(error)`; that is safe
    for a fixed message and wrong for one that interpolates anything
    per-instance, so new call sites should set it.

    `stacklevel` defaults to 3 — helper, the function that called it, then the
    user. Pass a different value where the call sits deeper.
    """
    if strict_errors_enabled():
        raise error
    warnings.warn(
        f"{error.warning_summary or error}\nThis returns None today and raises "
        f"{type(error).__name__} in edgartools 6.0. Set EDGARTOOLS_STRICT_ERRORS=1 "
        f"to get the 6.0 behaviour now.",
        FutureWarning,
        stacklevel=stacklevel,
    )


class EdgarError(Exception):
    """Base for every edgartools exception.

    Carries the house message style structurally rather than by good intentions:
    a message, optional `context` (facts about what happened), optional
    `suggestions` (what the caller can do), and an optional `docs_url`. All are
    optional and `EdgarError("something broke")` works, so converting a raise
    site costs exactly one class name — which is the point, at 154 of them.

    The signature is positionally compatible with the `ParsingError` this
    replaces (`message, context, suggestions`), so the nine parser subclasses
    and their call sites re-base without edits.
    """

    #: Dedup-stable text for `warn_will_raise`, set by call sites whose message
    #: interpolates something per-instance. It must not contain an accession
    #: number, a user-supplied identifier, or anything else that varies between
    #: two filings hitting the same line — Python's warning filter compares the
    #: rendered text, so anything that varies turns one warning into thousands.
    #: `None` means `str(self)` is already stable and is used as-is.
    warning_summary: Optional[str] = None

    def __init__(self,
                 message: str = "",
                 context: Optional[Dict[str, Any]] = None,
                 suggestions: Optional[List[str]] = None,
                 *,
                 docs_url: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.suggestions = suggestions or []
        self.docs_url = docs_url

    def __str__(self) -> str:
        # Rendering is byte-identical to the ParsingError this promotes, so no
        # existing message changes; docs_url is new and only renders when set.
        result = self.message
        if self.context:
            result += f"\nContext: {self.context}"
        if self.suggestions:
            result += f"\nSuggestions: {', '.join(self.suggestions)}"
        if self.docs_url:
            result += f"\nDetails: {self.docs_url}"
        return result

    def __reduce__(self):
        # Exceptions cross process boundaries whenever a user runs us under
        # multiprocessing. BaseException.__reduce__ replays `args` through the
        # constructor, which loses every attribute a subclass set from a
        # different signature (TooManyRequestsError(url, retry_after) keeps only
        # the built message in args). Restoring __dict__ afterwards fixes the
        # family in one place. test_exceptions.py round-trips every class.
        return (self.__class__, self.args, self.__dict__)


# --------------------------------------------------------------------------
# Transport — we could not get an answer from SEC
# --------------------------------------------------------------------------

class TransportError(EdgarError):
    """We could not get an answer from SEC EDGAR.

    Raise when the request never completed or was rejected at the door: network
    failure, SSL interception, rate limiting, a missing or rejected identity, or
    an HTTP error status. `status_code` is None for a pure network failure.

    This is the distinction that matters most to callers: a `TransportError`
    means *we could not ask*, which is never the same answer as "there is no
    such thing" — see `NotFoundError`.
    """

    def __init__(self,
                 message: str = "",
                 context: Optional[Dict[str, Any]] = None,
                 suggestions: Optional[List[str]] = None,
                 *,
                 url: Optional[str] = None,
                 status_code: Optional[int] = None,
                 docs_url: Optional[str] = None):
        super().__init__(message, context, suggestions, docs_url=docs_url)
        self.url = url
        self.status_code = status_code


class TooManyRequestsError(TransportError):
    """SEC returned HTTP 429 (Too Many Requests).

    The SEC limits requests to 10 per second. When exceeded, your IP is blocked
    for approximately 10 minutes. Continuing to send requests during this period
    will extend the block duration.

    Important: Do NOT retry immediately - wait for the block to expire.
    """

    BLOCK_DURATION_MINUTES = 10

    def __init__(self, url=None, retry_after: Optional[int] = None):
        # Message built exactly as it was in edgar/httprequests.py — this class
        # is the house style's best example and moving it must not dilute it.
        header = f"""
SEC Rate Limit Exceeded (HTTP 429)
==================================

URL: {url}"""

        if retry_after:
            wait_info = f"""
Retry-After: {retry_after} seconds (from SEC response header)"""
        else:
            wait_info = f"""
Estimated Wait: ~{self.BLOCK_DURATION_MINUTES} minutes"""

        cause = """

What happened:
  Your request rate exceeded the SEC's limit of 10 requests/second.
  Your IP address has been temporarily blocked."""

        warning = """

{warning} Important: Do NOT retry immediately!
  Continuing to send requests during the block period will EXTEND it.
  The SEC penalizes continued requests during timeout.""".format(warning="⚠")

        solution = f"""

What to do:
  1. Wait at least {self.BLOCK_DURATION_MINUTES} minutes before retrying
  2. Reduce your request rate (edgartools defaults to 9 req/sec)
  3. Consider using local storage: download_edgar_data()

To adjust rate limit:
  import os
  os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = '5'  # More conservative"""

        footer = """

Details: https://www.sec.gov/os/webmaster-faq#developers"""

        message = f"{header}{wait_info}{cause}{warning}{solution}{footer}"
        super().__init__(message, url=url, status_code=429)
        self.retry_after = retry_after

    def __str__(self) -> str:
        # The message is already a full banner; the base's context/suggestions
        # rendering would only append noise to it.
        return self.message


class IdentityError(TransportError):
    """EDGAR_IDENTITY is missing or was rejected, so no request can succeed.

    A transport error rather than a validation one on purpose: nothing the
    caller passed to *this* call was wrong, and every subsequent request fails
    the same way until the identity is fixed.
    """


class IdentityNotSetError(IdentityError):
    """Client-side pre-check: no identity is configured.

    Was `IdentityNotSetException` in edgar.httprequests, which said only
    "User-Agent identity is not set" and left the reader to discover
    `set_identity()` on their own.
    """

    def __init__(self, message: str = "", **kwargs):
        if not message:
            message = "SEC requires a User-Agent identifying you, and none is set."
            kwargs.setdefault("suggestions", [
                'set_identity("Your Name your.email@example.com")',
                "or set the EDGAR_IDENTITY environment variable to the same string",
            ])
            kwargs.setdefault("docs_url",
                              "https://www.sec.gov/os/webmaster-faq#developers")
        super().__init__(message, **kwargs)


class SECIdentityError(IdentityError):
    """Server-side: SEC rejected the request because of its identity.

    Distinct from `IdentityNotSetError` by *who noticed* — we checked before
    sending, or SEC told us after. Same root cause, same fix, so they share a
    parent and `except IdentityError` catches both.
    """


# --------------------------------------------------------------------------
# Not found — you named a thing and it does not exist
# --------------------------------------------------------------------------

class NotFoundError(EdgarError, LookupError):
    """You asked for a specific named thing and it does not exist.

    Raise when a *dereference* fails: an identifier, key, section name or
    statement name that resolves to nothing. Do not raise it for a probe whose
    documented answer may legitimately be "no" — `Filing.xbrl()` returning None
    for a filing without XBRL is an answer, not a failure.

    Inherits `LookupError` so that this reads as what it is to any Python
    programmer, and so converting a `KeyError` raise site is additive.
    """


def _company_not_found_message(identifier, suggestions) -> str:
    msg = f"Company not found: '{identifier}'"
    if suggestions:
        suggestions_str = ", ".join(
            f"'{s['ticker']}' ({s['company']})" for s in suggestions[:3]
        )
        msg += f"\n  Similar: {suggestions_str}"
    msg += "\n  Tip: Search by name with find_company(\"...\") or pass a CIK directly."
    return msg


class CompanyNotFoundError(NotFoundError):
    """A company could not be found by ticker, CIK, or name."""

    def __init__(self, identifier, suggestions=None):
        # `suggestions` here is the fuzzy-match structure (dicts of ticker and
        # company), not the base class's list of strings — kept as it was,
        # because this message is already public and documented. Building it
        # through a module function rather than `str(self)` keeps `.suggestions`
        # a single assignment; calling up with `str(self)` would have the base
        # reset it from its own parameter.
        super().__init__(_company_not_found_message(identifier, suggestions or []))
        self.identifier = identifier
        self.suggestions = suggestions or []

    def __str__(self) -> str:
        return _company_not_found_message(self.identifier, self.suggestions)


class FilingNotFoundError(NotFoundError):
    """SEC has no filing at that accession number.

    Canonical name for `SECFilingNotFoundError`.
    """


class CompanyFactsNotFoundError(NotFoundError):
    """The SEC Facts API has no data for this CIK.

    Was `NoCompanyFactsFound`, whose `__init__` called `super().__init__()` with
    no arguments and set `self.message` instead — so `str(exc)` was `''` and the
    message never reached a traceback or a log. Building the message and passing
    it up makes that unrepresentable.
    """

    def __init__(self, cik=None, message: str = "", **kwargs):
        self.cik = cik
        if not message:
            message = f"No Company facts found for cik {cik}"
        super().__init__(message, **kwargs)


class StatementNotFoundError(NotFoundError):
    """A financial statement could not be resolved with sufficient confidence.

    Canonical name for `StatementNotFound`. Keeps that class's keyword
    signature and its rendered message exactly; it is no longer a dataclass,
    because a dataclass cannot pass a built message up to the base.
    """

    def __init__(self,
                 statement_type: str = "",
                 confidence: float = 0.0,
                 found_statements: Optional[List[str]] = None,
                 entity_name: str = "Unknown",
                 cik: str = "Unknown",
                 period_of_report: str = "Unknown",
                 reason: str = ""):
        self.statement_type = statement_type
        self.confidence = confidence
        self.found_statements = found_statements if found_statements is not None else []
        self.entity_name = entity_name
        self.cik = cik
        self.period_of_report = period_of_report
        self.reason = reason
        super().__init__(str(self))

    def __str__(self) -> str:
        base_msg = (f"Failed to resolve {self.statement_type} for {self.entity_name} "
                    f"(CIK: {self.cik}, Period: {self.period_of_report})")
        if self.confidence > 0:
            confidence_msg = f"Low confidence match: {self.confidence:.2f}"
        else:
            confidence_msg = "No matching statements found"

        if self.found_statements:
            found_msg = f"Found statements: {self.found_statements}"
        else:
            found_msg = "No statements available"

        details = f"{base_msg}. {confidence_msg}. {found_msg}"
        if self.reason:
            details += f". {self.reason}"

        return details


class SectionNotFoundError(NotFoundError, KeyError):
    """A named section of a report does not exist (e.g. `tenk['Item 7A']`).

    Also a `KeyError`, so the `except KeyError:` a caller already wrote around
    item access keeps working when this starts being raised in 6.0. `EdgarError`
    precedes `KeyError` in the MRO, so `str(exc)` is the message rather than
    KeyError's repr-quoted form.

    Raised from the `__getitem__` flip (PR3 of this bead); defined here so the
    vocabulary lands in one piece.
    """


class AttachmentNotFoundError(NotFoundError, KeyError):
    """No attachment matches that key or sequence number.

    Also a `KeyError` — `Attachments.__getitem__` already raised one, and this
    narrows that to a typed error without breaking the handler.
    """


# --------------------------------------------------------------------------
# Parsing — we got bytes and could not build the promised object
# --------------------------------------------------------------------------

class ParsingError(EdgarError):
    """We fetched the data and could not build the object we promised.

    This is `edgar.documents.exceptions.ParsingError` promoted to a branch: its
    message/context/suggestions shape moved up into `EdgarError`, so the parser
    subclasses that lived under it re-base with no change to their signatures.
    """


class XBRLProcessingError(ParsingError):
    """An error occurred while processing XBRL."""


class DataObjectError(ParsingError):
    """`filing.obj()` could not build a data object for a form it supports.

    Canonical name for `DataObjectException`. Takes primitives rather than a
    Filing, because this module imports nothing from edgar; the deprecated
    alias keeps the Filing-taking constructor.
    """

    def __init__(self, message: str = "", *, form=None, accession_no=None, **kwargs):
        self.form = form
        self.accession_no = accession_no
        if not message:
            message = f"Could not create a data object for Form {form} filing: {accession_no}"
        super().__init__(message, **kwargs)


# --------------------------------------------------------------------------
# Validation — your input was wrong before we ever asked
# --------------------------------------------------------------------------

class ValidationError(EdgarError, ValueError):
    """The caller's input was invalid before any request was made.

    Hoisted from `edgar.enums` with `parameter` and `invalid_value` made
    optional, so the enum validation framework and a plain bad-input raise
    share one class. Positional order is unchanged
    (`message, parameter, invalid_value, suggestions`).

    IS-A `ValueError`, which is what makes converting the 135 raw `ValueError`
    raises additive rather than a break.
    """

    def __init__(self,
                 message: str,
                 parameter: Optional[str] = None,
                 invalid_value: Any = None,
                 suggestions: Optional[List[str]] = None,
                 **kwargs):
        super().__init__(message, suggestions=suggestions, **kwargs)
        self.parameter = parameter
        self.invalid_value = invalid_value


class InvalidDateError(ValidationError):
    """A date or date range could not be understood.

    Canonical name for `InvalidDateException`.
    """
