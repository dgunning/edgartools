"""
Cursor routing and page helpers shared by the BDC actions of edgar_fund.

A BDC cursor is self-describing (constraints rule 7b): `peek_bdc_cursor`
reads its tool and accession before any filing is loaded, so a cursor alone
selects its own filing (`selection_args`). The full identity and fingerprint
checks still run through `decode_page_cursor`/`resolve_cursor_offset`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from edgar.ai.mcp.tools.base import error

# =============================================================================
# Cursor routing (P1-H1, P1-H2 / constraints rule 7b)
# =============================================================================

PORTFOLIO_CURSOR_TOOL = "edgar_fund:bdc_portfolio"
SOI_TEXT_CURSOR_TOOL = "edgar_fund:bdc_soi_text"
NONACCRUAL_CURSOR_TOOL = "edgar_fund:bdc_nonaccrual"


@dataclass(frozen=True)
class PeekedCursor:
    """What a cursor says about itself before any filing is loaded."""
    tool: str
    accession: str
    query: Optional[dict]


def _canonical_accession(value: str) -> str:
    """`value` stripped, with an 18-digit form rewritten to NNNNNNNNNN-NN-NNNNNN."""
    cleaned = value.strip()
    if len(cleaned) == 18 and cleaned.isdigit():
        return f"{cleaned[:10]}-{cleaned[10:12]}-{cleaned[12:]}"
    return cleaned


def _cursor_error_response(message: str, error_code: str) -> Any:
    from edgar.ai.mcp.tools.continuation import CursorError

    return CursorError(message, error_code=error_code).to_response()


def peek_bdc_cursor(cursor: Optional[str], *, allowed_tools: tuple[str, ...], accession_number: Optional[str]):
    """Peek `cursor` to route the call. Returns `(peeked_or_None, error_or_None)`.

    A cursor is self-describing (rule 7b): its accession selects the filing,
    so a bare cursor is enough to continue. Rejected up front, before any
    filing is loaded: an undecodable cursor (`INVALID_CURSOR`), a cursor from
    another tool/action, or an `accession_number` naming a different filing
    (`CURSOR_MISMATCH`). The full identity and fingerprint checks still run
    later against the loaded filing.
    """
    from edgar.ai.mcp.tools.continuation import CursorError, peek_cursor

    if not cursor:
        return None, None
    try:
        payload = peek_cursor(cursor)
    except CursorError as exc:
        return None, exc.to_response()

    accession = payload.get("acc")
    if not isinstance(accession, str) or not accession:
        return None, _cursor_error_response("Cursor does not name a filing.", "INVALID_CURSOR")
    if payload.get("tool") not in allowed_tools:
        return None, _cursor_error_response(
            "Cursor was issued for a different tool or action than this call.", "CURSOR_MISMATCH"
        )
    if accession_number and _canonical_accession(accession_number) != accession:
        return None, _cursor_error_response(
            "Cursor was issued for a different filing than accession_number.", "CURSOR_MISMATCH"
        )
    return PeekedCursor(tool=payload["tool"], accession=accession, query=payload.get("q")), None


def selection_args(peeked: Optional[PeekedCursor], accession_number: Optional[str], period: Optional[str]):
    """`(accession_number, period)` to select with: the cursor's own accession
    when continuing (form/period ignored), else the caller's selectors."""
    if peeked is None:
        return accession_number, period
    return peeked.accession, None


def decode_page_cursor(cursor: Optional[str], *, tool: str, accession: str, query: dict):
    """Decode a page cursor, if given. Returns `(payload_or_None, error_response_or_None)`.

    Thin wrapper over `continuation.try_decode_cursor` (shared with
    edgar_notes/edgar_read), called the same way by both BDC actions.
    """
    from edgar.ai.mcp.tools.continuation import try_decode_cursor

    return try_decode_cursor(cursor, tool=tool, accession=accession, query=query)


def build_next_cursor(tool: str, accession: str, offset: int, fp: str, query: Optional[dict]):
    """Encode a page cursor. Returns `(cursor_or_None, error_response_or_None)`.

    Thin wrapper over `continuation.try_encode_cursor` (shared with
    edgar_notes/edgar_read), called the same way by both BDC actions.
    """
    from edgar.ai.mcp.tools.continuation import try_encode_cursor

    return try_encode_cursor(tool=tool, accession=accession, offset=offset, fp=fp, query=query)


def resolve_cursor_offset(cursor_payload: Optional[dict], fp: str):
    """The page offset a decoded cursor points at. Returns `(offset, error_response)`;
    `offset` is `0` with no cursor. Checks the fingerprint -- the one part of
    cursor validation that needs the just-computed extraction fingerprint,
    so it can't happen inside `decode_page_cursor` (which runs before
    extraction)."""
    from edgar.ai.mcp.tools.continuation import CursorError, check_fingerprint

    if cursor_payload is None:
        return 0, None
    try:
        check_fingerprint(cursor_payload, fp)
    except CursorError as exc:
        return None, exc.to_response()
    return cursor_payload["off"], None


def no_xbrl_response(accession: str) -> Any:
    return error(
        f"No XBRL data found for filing {accession}.",
        suggestions=[
            "Use edgar_read to read this filing as raw text instead",
            "Try a different filing from this BDC",
        ],
        error_code="NO_XBRL",
    )
