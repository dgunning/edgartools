"""
Continuation service for MCP tools: cursors, pagination, and a result cache.

An ARCC 10-Q has 1,481 extracted holdings and extraction costs roughly 11
seconds per call (XBRL parse plus footnote extraction). A caller that wants
holding 1,450 cannot be asked to re-describe the whole extraction on every
page, and the MCP may run under streamable-http with multiple worker
processes or restart between calls, so a page cursor cannot rely on anything
living in this process's memory. It has to describe itself completely.

That is what a cursor here is: a small, versioned JSON payload — which tool
issued it, which filing/document/query it was issued for, the offset it
points at, and a fingerprint of the underlying result — base64url-encoded so
it travels as an opaque string. On the next call the tool re-extracts (cheap
if ``results_cache``/``text_cache`` still has it, ~11s if not), recomputes
the fingerprint, and compares it against the one in the cursor. A mismatch
there (``CURSOR_STALE``) means the underlying data changed since the cursor
was issued; a mismatch on tool/accession/document/query (``CURSOR_MISMATCH``)
means the cursor was issued for a different call entirely; anything that
does not even decode to a well-formed payload (``INVALID_CURSOR``) is
treated the same as a caller starting over.

This module is pure Python: no network access, and no edgar imports beyond
``base.py``'s ``error()`` helper (Tasks 4-6 wire the pieces below into
edgar_fund, edgar_notes and edgar_read; this module has no opinion on how
they're used).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
from collections import OrderedDict
from typing import Any, Iterable, Optional, Sequence

from edgar.ai.mcp.tools.base import error

logger = logging.getLogger(__name__)

CURSOR_VERSION = 1
MAX_CURSOR_CHARS = 2048
TEXT_PAGE_CHARS = 6000

# Every cursor error suggests the same escape hatch: drop the cursor and
# start the listing/read over from the top. A stale/mismatched/malformed
# cursor is never something a caller can repair by inspecting it.
_RESTART_SUGGESTION = "Omit the cursor parameter to restart from the first page."


class CursorError(Exception):
    """Raised when a cursor cannot be trusted for the current call.

    Mirrors ``FilingSelectionError`` (edgar/ai/mcp/tools/selection.py): it
    carries a response-ready error code and suggestions so a tool can just
    call ``to_response()`` rather than re-deriving the error shape itself.
    """

    def __init__(self, message: str, error_code: str, suggestions: Optional[list[str]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.suggestions = suggestions or [_RESTART_SUGGESTION]

    def to_response(self):
        """Build the standard MCP error response for this failure."""
        return error(self.message, suggestions=self.suggestions, error_code=self.error_code)


def _cursor_error(error_code: str, message: str) -> CursorError:
    return CursorError(message, error_code=error_code, suggestions=[_RESTART_SUGGESTION])


# =============================================================================
# FINGERPRINT
# =============================================================================

def fingerprint(parts: Iterable[str]) -> str:
    """A short, order-sensitive fingerprint of ``parts``.

    Used to detect that a re-extracted result is (or is not) the same result
    a cursor was issued against. SHA-1 is fine here — this is a change
    detector, not a security boundary — truncated to 12 hex characters,
    which is plenty to catch a changed extraction without bloating every
    cursor.
    """
    joined = "\x1f".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def check_fingerprint(payload: dict, fp: str) -> None:
    """Raise ``CursorError(CURSOR_STALE)`` if ``payload``'s fingerprint differs from ``fp``.

    ``payload`` is whatever ``decode_cursor`` returned; ``fp`` is the
    fingerprint of the result as it looks *right now*, recomputed by the
    caller. A mismatch means the cursor decoded fine (same tool, filing,
    document, query, offset) but the data it points into has changed since
    it was issued.
    """
    if payload.get("fp") != fp:
        raise _cursor_error(
            "CURSOR_STALE",
            "This cursor's underlying result has changed since it was issued.",
        )


# =============================================================================
# CURSOR ENCODE / DECODE
# =============================================================================

def _b64_decode(cursor: str) -> bytes:
    padding = (-len(cursor)) % 4
    return base64.urlsafe_b64decode(cursor + ("=" * padding))


def encode_cursor(
    *,
    tool: str,
    accession: str,
    offset: int,
    fp: str,
    document: Optional[str] = None,
    query: Optional[dict] = None,
) -> str:
    """Encode a self-describing page cursor as urlsafe base64url (no padding).

    The payload always carries all seven keys (``v, tool, acc, doc, q, off,
    fp``) even when ``document``/``query`` are absent, so decoding never has
    to distinguish "key missing" from "key present but null" — both just mean
    "not given". Keys are JSON-sorted with compact separators so the same
    logical cursor always encodes to the same bytes.
    """
    payload = {
        "v": CURSOR_VERSION,
        "tool": tool,
        "acc": accession,
        "doc": document,
        "q": query,
        "off": offset,
        "fp": fp,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(
    cursor: str,
    *,
    tool: str,
    accession: str,
    document: Optional[str] = None,
    query: Optional[dict] = None,
) -> dict:
    """Decode and validate ``cursor`` against the current call's identity.

    Validates, in order: size, decodability, shape (a JSON object), version,
    and the offset's type/sign — any failure there is ``INVALID_CURSOR``,
    because none of those are "you asked for something else", they are "this
    is not a cursor this function issued". Then it compares ``tool``,
    ``accession``, ``document`` and ``query`` against the current call —
    ``document``/``query`` missing from the cursor and ``None`` on the
    current call are treated as equal, since ``encode_cursor`` always writes
    both keys as ``null`` rather than omitting them. Any difference there is
    ``CURSOR_MISMATCH``: the cursor is well-formed, just not for this call.

    Does not check the fingerprint — that requires the caller to have
    recomputed the current result first, so it is a separate call to
    ``check_fingerprint``.
    """
    if not isinstance(cursor, str) or not cursor:
        raise _cursor_error("INVALID_CURSOR", "Cursor is empty or not a string.")
    if len(cursor) > MAX_CURSOR_CHARS:
        raise _cursor_error(
            "INVALID_CURSOR",
            f"Cursor exceeds the {MAX_CURSOR_CHARS}-character limit.",
        )

    try:
        payload = json.loads(_b64_decode(cursor))
    except Exception as exc:
        raise _cursor_error("INVALID_CURSOR", f"Cursor could not be decoded: {exc}") from exc

    if not isinstance(payload, dict):
        raise _cursor_error("INVALID_CURSOR", "Cursor did not decode to an object.")

    if payload.get("v") != CURSOR_VERSION:
        raise _cursor_error(
            "INVALID_CURSOR",
            f"Unsupported cursor version: {payload.get('v')!r} (expected {CURSOR_VERSION}).",
        )

    off = payload.get("off")
    if not isinstance(off, int) or isinstance(off, bool) or off < 0:
        raise _cursor_error("INVALID_CURSOR", f"Invalid cursor offset: {off!r}.")

    if payload.get("tool") != tool or payload.get("acc") != accession:
        raise _cursor_error(
            "CURSOR_MISMATCH",
            "Cursor was issued for a different tool or filing than this call.",
        )
    if payload.get("doc") != document:
        raise _cursor_error(
            "CURSOR_MISMATCH",
            "Cursor was issued for a different document than this call.",
        )
    if payload.get("q") != query:
        raise _cursor_error(
            "CURSOR_MISMATCH",
            "Cursor was issued for a different query than this call.",
        )

    return payload


# =============================================================================
# PAGINATION
# =============================================================================

def paginate(items: Sequence, *, offset: int, limit: int) -> tuple[list, dict]:
    """Slice ``items[offset:offset + limit]`` and describe the page.

    An offset at or beyond ``len(items)`` is not an error — it is simply an
    empty page with ``remaining: 0``, the same as reading past the end of a
    file.
    """
    total = len(items)
    page = list(items[offset:offset + limit])
    returned = len(page)
    remaining = max(total - offset - returned, 0)
    return page, {
        "offset": offset,
        "returned": returned,
        "total": total,
        "remaining": remaining,
    }


def _find_text_break(chunk: str, budget: int) -> Optional[int]:
    """Where inside ``chunk`` (length ``budget``) to break the page, if anywhere.

    Prefers the last paragraph boundary (``"\\n\\n"``), then the last plain
    newline, but only when the break point falls in the last 30% of the
    budget — breaking earlier than that would return an oddly short page
    just to land on a boundary that isn't really "near the end" of this
    page. Returns ``None`` when neither is found in that zone, meaning: hard
    cut at ``budget``.
    """
    zone_start = int(budget * 0.7)

    para_idx = chunk.rfind("\n\n")
    if para_idx != -1:
        break_at = para_idx + 2
        if break_at >= zone_start:
            return break_at

    nl_idx = chunk.rfind("\n")
    if nl_idx != -1:
        break_at = nl_idx + 1
        if break_at >= zone_start:
            return break_at

    return None


def paginate_text(text: str, *, offset: int, budget: int = TEXT_PAGE_CHARS) -> tuple[str, dict]:
    """Slice up to ``budget`` characters of ``text`` starting at ``offset``.

    Never returns more than ``budget`` characters. When the natural window
    end falls short of the text's end, prefers breaking at a paragraph or
    line boundary near the end of the window (see ``_find_text_break``) so
    pages read naturally; otherwise hard-cuts at ``budget``. Concatenating
    every page in order (following each page's ``next_offset`` until it is
    ``None``) reproduces ``text`` exactly, regardless of which break rule
    fired.
    """
    total_chars = len(text)

    if offset >= total_chars:
        return "", {
            "offset": offset,
            "returned_chars": 0,
            "total_chars": total_chars,
            "remaining_chars": 0,
            "next_offset": None,
        }

    window_end = min(offset + budget, total_chars)
    chunk = text[offset:window_end]

    if window_end < total_chars:
        break_at = _find_text_break(chunk, budget)
        if break_at is not None:
            chunk = chunk[:break_at]
            window_end = offset + break_at

    next_offset = window_end if window_end < total_chars else None
    return chunk, {
        "offset": offset,
        "returned_chars": len(chunk),
        "total_chars": total_chars,
        "remaining_chars": total_chars - window_end,
        "next_offset": next_offset,
    }


# =============================================================================
# RESULT CACHE
# =============================================================================

class ResultCache:
    """A thread-safe, in-process LRU cache keyed by a hashable tuple.

    Bounded two ways at once: ``max_entries`` (always enforced) and
    ``max_bytes`` (enforced when non-zero; 0 means "don't track bytes at
    all"). A single item larger than ``max_bytes`` is never cached — storing
    it would either immediately evict everything else or blow the budget on
    its own, neither of which is "caching" it usefully.

    This is the process-local half of continuation: a cursor's fingerprint
    lets a *different* process (or this one, after a restart) tell that a
    cache miss is safe to just re-extract and re-check, rather than treating
    a miss as an error.
    """

    def __init__(self, max_entries: int, max_bytes: int = 0):
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._data: "OrderedDict[Any, tuple[Any, int]]" = OrderedDict()
        self._total_bytes = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._rejected = 0

    def get(self, key: Any) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None
            self._data.move_to_end(key)
            self._hits += 1
            return entry[0]

    def put(self, key: Any, value: Any, size_bytes: int = 0) -> None:
        with self._lock:
            if self.max_bytes and size_bytes > self.max_bytes:
                self._rejected += 1
                return

            existing = self._data.pop(key, None)
            if existing is not None:
                self._total_bytes -= existing[1]

            self._data[key] = (value, size_bytes)
            self._total_bytes += size_bytes
            self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        while len(self._data) > self.max_entries or (self.max_bytes and self._total_bytes > self.max_bytes):
            if not self._data:
                break
            _, (_, evicted_size) = self._data.popitem(last=False)
            self._total_bytes -= evicted_size
            self._evictions += 1

    def stats(self) -> dict:
        with self._lock:
            return {
                "entries": len(self._data),
                "bytes": self._total_bytes,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "rejected": self._rejected,
            }


def _env_int(name: str, default: int) -> int:
    """Read a positive int from env var ``name``, falling back to ``default``.

    Any value that isn't a positive integer (missing, non-numeric, zero,
    negative) falls back silently to the caller except for a logged
    warning — a bad env value should degrade to the default cache size, not
    crash import of this module.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError(f"must be positive, got {value}")
        return value
    except ValueError as exc:
        logger.warning("Invalid value for %s=%r (%s); using default %d", name, raw, exc, default)
        return default


# Module singletons. `results_cache` holds small structured page results
# (e.g. a paginated holdings listing); `text_cache` holds larger raw text
# pages, hence the separate byte budget.
results_cache = ResultCache(max_entries=_env_int("EDGAR_MCP_CACHE_MAX_RESULTS", 8))
text_cache = ResultCache(
    max_entries=64,
    max_bytes=_env_int("EDGAR_MCP_CACHE_MAX_TEXT_MB", 32) * 1024 * 1024,
)
