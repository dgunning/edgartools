"""Filing attachment discovery, search and bounded document reading."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any, Optional
from urllib.parse import unquote, urlsplit

from edgar.ai.mcp.tools.base import ToolResponse, error, success, tool
from edgar.ai.mcp.tools.continuation import (
    TEXT_PAGE_CHARS,
    check_fingerprint,
    decode_cursor,
    fingerprint,
    paginate,
    paginate_text,
    try_encode_cursor,
)

_LIST_TOOL = "edgar_document:list"
_SEARCH_TOOL = "edgar_document:search"
_READ_TOOL = "edgar_document:read"
MAX_SEARCH_MATCHES = 1_000
MAX_SEARCH_MATCH_CHARS = 2_048
REGEX_TIMEOUT_SECONDS = 0.05
_LIST_NOTE = (
    "Some exhibits referenced by this filing may be incorporated by reference from earlier SEC filings; "
    "they are not included in this filing's attachments."
)
_EVIDENCE_SCOPE_NOTE = (
    "If this is a BDC filing, it identifies evidence reported by the BDC and may not contain an underlying "
    "agreement for a portfolio borrower."
)
_ACCESSION_DASHED = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_ACCESSION_UNDASHED = re.compile(r"^\d{18}$")
_R_FILE = re.compile(r"^R\d+\.htm$", re.IGNORECASE)


def _normalise_accession(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if _ACCESSION_DASHED.fullmatch(value):
        return value
    if _ACCESSION_UNDASHED.fullmatch(value):
        return f"{value[:10]}-{value[10:12]}-{value[12:]}"
    return None


def _parse_sec_url(value: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Validate a caller URL and return accession, filename and error text.

    Only the URL's identity is read. The URL itself is never fetched.
    """
    if not isinstance(value, str) or not value:
        return None, None, "Provide an HTTPS SEC Archives URL."
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        return None, None, f"The URL could not be parsed: {exc}"
    if parsed.scheme != "https" or parsed.netloc != "www.sec.gov":
        return None, None, "Only HTTPS URLs with the exact authority www.sec.gov are accepted."
    if not parsed.path.startswith("/Archives/"):
        return None, None, "The SEC URL path must begin with /Archives/."

    match = re.fullmatch(
        r"/Archives/edgar/data/\d+/(?P<accession>\d{18})(?:/(?P<path>[^?#]*))?/?",
        parsed.path,
    )
    if not match:
        return None, None, "The URL must identify an SEC filing under /Archives/edgar/data/ with an accession number."

    filename = None
    path = match.group("path") or ""
    if path:
        try:
            decoded_path = unquote(path, errors="strict")
        except (UnicodeDecodeError, ValueError):
            return None, None, "The URL contains an invalid encoded path."
        parts = decoded_path.split("/")
        if any(part in {".", ".."} for part in parts) or "\\" in decoded_path:
            return None, None, "The URL contains an invalid document path."
        filename = PurePosixPath(decoded_path).name or None
        if filename and ("/" in filename or "\\" in filename):
            return None, None, "The URL does not contain a valid document filename."

    accession_raw = match.group("accession")
    accession = f"{accession_raw[:10]}-{accession_raw[10:12]}-{accession_raw[12:]}"
    return accession, filename, None


def _filing_identity(filing, selected_by: str, selected_attachment=None) -> tuple[dict, dict]:
    """Build light-weight provenance without triggering a period-of-report fetch."""
    cik = int(filing.cik)
    name = getattr(filing, "company", None)
    source = {
        "cik": cik,
        "entity": name,
        "accession_number": filing.accession_number,
        "form": filing.form,
        "period_of_report": str(getattr(filing, "report_date", None) or "") or None,
        "filed": str(filing.filing_date),
        "url": filing.homepage_url,
        "is_amendment": str(filing.form).endswith("/A"),
        "selected_by": selected_by,
    }
    if selected_attachment is not None:
        source["document_url"] = _safe_url(selected_attachment)
    return {"cik": cik, "name": name}, source


def _safe_url(attachment) -> Optional[str]:
    try:
        return getattr(attachment, "url", None)
    except Exception:
        return None


def _identity(attachment) -> dict[str, Any]:
    primary = str(getattr(attachment, "sequence_number", "")) == "1"
    sequence = str(getattr(attachment, "sequence_number", "") or "")
    doc_type = getattr(attachment, "document_type", None)
    return {
        "sequence": sequence,
        "sequence_number": sequence,
        "filename": getattr(attachment, "document", None),
        "type": doc_type,
        "document_type": doc_type,
        "description": getattr(attachment, "display_description", None)
        or getattr(attachment, "description", None),
        "size": getattr(attachment, "size", None),
        "primary": primary,
        "is_primary": primary,
        "readable": _readable_format(attachment),
        "url": _safe_url(attachment),
    }


def _readable_format(attachment) -> bool:
    if _is_paper_attachment(attachment):
        return False
    if getattr(attachment, "empty", False) or getattr(attachment, "is_binary", lambda: False)():
        return False
    return bool(getattr(attachment, "is_text", lambda: False)())


def _is_paper_attachment(attachment) -> bool:
    filename = str(getattr(attachment, "document", "") or "")
    return PurePosixPath(filename).suffix.lower() == ".paper"


def _is_hidden_by_default(attachment) -> bool:
    # The filing's sequence-1 document is the main report, even when it is
    # inline XBRL. Keep it available while hiding separate XBRL support files.
    if str(getattr(attachment, "sequence_number", "")) == "1":
        return False
    filename = str(getattr(attachment, "document", "") or "")
    doc_type = str(getattr(attachment, "document_type", "") or "").upper()
    extension = PurePosixPath(filename).suffix.lower()
    return bool(
        _R_FILE.fullmatch(filename)
        or getattr(attachment, "ixbrl", False)
        or extension in {".xml", ".xbrl", ".xsd"}
        or doc_type.startswith("EX-101")
        or doc_type in {"XML", "XBRL", "EX-104"}
    )


def _attachments(filing) -> list:
    try:
        return list(filing.attachments)
    except Exception as exc:
        raise RuntimeError(f"Could not list filing attachments: {exc}") from exc


def _resolve_attachment(attachments: list, selector: Optional[str]) -> tuple[Optional[Any], Optional[ToolResponse]]:
    if selector is None or not str(selector).strip():
        return None, error(
            "A document selector is required for this action.",
            suggestions=["Use a sequence number, exact filename, or exhibit type such as EX-32.1."],
            error_code="DOCUMENT_REQUIRED",
        )

    selector = str(selector).strip()
    if selector.isdigit():
        matches = [a for a in attachments if str(getattr(a, "sequence_number", "")) == selector]
    else:
        exact_filename = [a for a in attachments if getattr(a, "document", None) == selector]
        if exact_filename:
            matches = exact_filename
        else:
            # A type selector is a prefix, so EX-10 deliberately covers EX-10.1,
            # EX-10.2 and similar variants. Ambiguity is surfaced below.
            normalized_selector = selector.upper()
            if re.fullmatch(r"EX-\d+", normalized_selector):
                matches = [
                    a
                    for a in attachments
                    if (doc_type := str(getattr(a, "document_type", "") or "").upper())
                    == normalized_selector
                    or doc_type.startswith(normalized_selector + ".")
                ]
            elif normalized_selector.startswith("EX-"):
                # A qualified exhibit type (EX-10.1) is an exact identity.
                # Treating it as a raw startswith prefix would also select
                # EX-10.10 when EX-10.1 is absent.
                matches = [
                    a for a in attachments
                    if str(getattr(a, "document_type", "") or "").upper() == normalized_selector
                ]
            else:
                matches = [
                    a
                    for a in attachments
                    if str(getattr(a, "document_type", "") or "").upper().startswith(normalized_selector)
                ]

    if not matches:
        return None, error(
            f"No filing attachment matches document selector {selector!r}.",
            suggestions=["List this filing's documents and use an exact sequence or filename."],
            error_code="DOCUMENT_NOT_FOUND",
        )
    if len(matches) > 1:
        return None, ToolResponse(
            success=False,
            error=f"Document selector {selector!r} matches multiple attachments.",
            error_code="AMBIGUOUS_DOCUMENT",
            suggestions=["Choose one candidate by exact filename or sequence number."],
            data={"candidates": [_identity(a) for a in matches]},
        )
    return matches[0], None


def _eligible(attachments: list, include_all: bool) -> list:
    return attachments if include_all else [a for a in attachments if not _is_hidden_by_default(a)]


def _library_version() -> str:
    try:
        import edgar
        return str(edgar.__version__)
    except Exception:
        return "unknown"


def _unreadable_reason(attachment, render_error: Optional[str] = None) -> str:
    if getattr(attachment, "empty", False):
        return "The filing attachment has no document filename or content."
    if _is_paper_attachment(attachment):
        return "Paper filing attachments are not rendered as readable document text by this tool."
    if getattr(attachment, "is_binary", lambda: False)():
        extension = PurePosixPath(str(getattr(attachment, "document", ""))).suffix.lower()
        if extension == ".pdf":
            return "This PDF attachment has no extracted text available through the filing text renderer."
        kind = extension.lstrip(".") or "binary"
        return (
            f"This {kind} attachment has no extracted text available "
            "through the filing text renderer."
        )
    if render_error:
        return f"The attachment could not be rendered as text: {render_error}"
    return "The attachment did not produce readable text."


def _read_text(filing, attachment) -> tuple[Optional[str], Optional[str]]:
    """Return full rendered text and an unreadable reason, using the shared cache."""
    from edgar.ai.mcp.tools.continuation import text_cache

    if _is_paper_attachment(attachment):
        return None, _unreadable_reason(attachment)

    filename = str(getattr(attachment, "document", "") or "")
    cache_key = ("edgar_document", filing.accession_number, filename, _library_version())
    cached = text_cache.get(cache_key)
    if cached is not None:
        return cached, None

    if getattr(attachment, "empty", False) or getattr(attachment, "is_binary", lambda: False)():
        return None, _unreadable_reason(attachment)

    render_error = None
    text = None
    try:
        text = attachment.markdown()
    except Exception as exc:
        render_error = str(exc)
    if not text:
        try:
            text = attachment.text()
        except Exception as exc:
            render_error = str(exc)

    if text is None:
        return None, _unreadable_reason(attachment, render_error)
    text = text.decode("utf-8", errors="replace") if isinstance(text, bytes) else str(text)
    if not text.strip():
        return None, _unreadable_reason(attachment, render_error)

    text_cache.put(cache_key, text, size_bytes=len(text.encode("utf-8")))
    return text, None


def _serialized_matches(
    filing,
    attachments: list,
    query: str,
    regex: bool,
    *,
    document_filter: Optional[str],
    include_all: bool,
) -> tuple[list[dict[str, Any]], bool]:
    from edgar.ai.mcp.tools.continuation import results_cache

    cache_key = (
        "edgar_document:search",
        filing.accession_number,
        document_filter,
        query,
        bool(regex),
        bool(include_all),
        _library_version(),
    )
    cached = results_cache.get(cache_key)
    if cached is not None:
        return cached, False

    records = []
    for attachment in attachments:
        filename = str(getattr(attachment, "document", "") or "")
        if not filename or _is_paper_attachment(attachment):
            continue
        remaining = max(0, MAX_SEARCH_MATCHES - len(records))
        grep_result = filing.grep(
            query,
            regex=regex,
            document=filename,
            render_markdown=True,
            max_matches=remaining,
            max_match_chars=MAX_SEARCH_MATCH_CHARS,
            regex_timeout=REGEX_TIMEOUT_SECONDS if regex else None,
        )
        if grep_result.overflowed:
            return [], True
        if len(grep_result) > remaining:
            # Defensive guard if a downstream Filing.grep implementation
            # returns candidates without honoring its bounded-search contract.
            return [], True
        records.extend(
            {
                "location": match.location,
                "match": match.match,
                "context": match.context,
                "locator": {"document": filename, "char_offset": match.char_offset},
            }
            for match in grep_result
        )
        if len(records) > MAX_SEARCH_MATCHES:
            return [], True

    results_cache.put(cache_key, records)
    return records, False


def _records_fingerprint(records: list[dict[str, Any]]) -> str:
    return fingerprint(json.dumps(record, sort_keys=True, default=str) for record in records)


def _page_records(
    *,
    action: str,
    accession: str,
    document: Optional[str],
    records: list[dict[str, Any]],
    cursor: Optional[str],
    limit: int,
    query: dict,
) -> tuple[Optional[list], Optional[dict], Optional[ToolResponse]]:
    tool_name = _LIST_TOOL if action == "list" else _SEARCH_TOOL
    fp = _records_fingerprint(records)
    try:
        payload = decode_cursor(
            cursor,
            tool=tool_name,
            accession=accession,
            document=document,
            query=query,
        ) if cursor else None
        if payload is not None:
            check_fingerprint(payload, fp)
    except Exception as exc:
        if hasattr(exc, "to_response"):
            return None, None, exc.to_response()
        return None, None, error(str(exc), error_code="INVALID_CURSOR")

    offset = payload["off"] if payload is not None else 0
    page_items, meta = paginate(records, offset=offset, limit=limit)
    next_cursor = None
    if meta["remaining"]:
        next_cursor, cursor_error = try_encode_cursor(
            tool=tool_name,
            accession=accession,
            offset=offset + meta["returned"],
            fp=fp,
            document=document,
            query=query,
        )
        if cursor_error:
            return None, None, cursor_error
    page = {**meta, "next_cursor": next_cursor}
    return page_items, page, None


def _source_input(
    accession_number: Optional[str], url: Optional[str]
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[ToolResponse]]:
    url_accession = None
    url_filename = None
    if url is not None:
        url_accession, url_filename, parse_error = _parse_sec_url(url)
        if parse_error:
            return None, None, None, error(
                parse_error,
                suggestions=["Use an HTTPS URL on www.sec.gov under /Archives/edgar/data/."],
                error_code="INVALID_URL",
            )
    supplied_accession = _normalise_accession(accession_number) if accession_number else None
    if accession_number and supplied_accession is None:
        return None, None, None, error(
            "The accession number must contain 18 digits, with or without SEC dashes.",
            error_code="INVALID_ACCESSION",
        )
    if supplied_accession and url_accession and supplied_accession != url_accession:
        return None, None, None, error(
            "The accession_number and SEC URL identify different filings.",
            error_code="FILING_MISMATCH",
        )
    accession = url_accession or supplied_accession
    if not accession:
        return None, None, None, error(
            "Provide accession_number or a valid SEC Archives URL.",
            suggestions=["Use a dashed SEC accession number or an HTTPS www.sec.gov filing URL."],
            error_code="FILING_REQUIRED",
        )
    return accession, url_filename, "url" if url else "accession", None


@tool(
    name="edgar_document",
    description=(
        "List, search and read exact documents filed with an SEC filing. Use accession_number or an HTTPS "
        "www.sec.gov Archives URL, which binds the accession and filename and is validated as identity rather "
        "than fetched directly. Select attachments by sequence, exact filename or exhibit type; ambiguous "
        "types return candidate identities. Search locators can be passed to read via around. Reads return "
        "at most 6,000 characters per page. Searches return "
        "at most 1,000 matches per filing and reject matches longer than 2,048 characters. Regex searches "
        "have a 50 ms per-document time limit. "
        "A BDC filing "
        "does not necessarily contain a portfolio borrower's agreement. "
        "Search results carry {document, char_offset} locators for bounded reads. "
        "Exhibits incorporated by reference may be in an earlier filing.\n\n"
        "<!-- MCP_TOOL_CALL_EXAMPLE -->\n```json\n"
        '{"tool":"edgar_document","arguments":{"action":"list","accession_number":"0001628280-26-050307"}}\n'
        "```\n\n"
        "<!-- MCP_TOOL_CALL_EXAMPLE -->\n```json\n"
        '{"tool":"edgar_document","arguments":{"action":"search","accession_number":"0001628280-26-050307","document":"[exact-filename-from-list]","query":"loan agreement"}}\n'
        "```\n\n"
        "<!-- MCP_TOOL_CALL_EXAMPLE -->\n```json\n"
        '{"tool":"edgar_document","arguments":{"action":"read","accession_number":"0001628280-26-050307","document":"[exact-filename-from-list]"}}\n'
        "```\n\n"
        "<!-- MCP_TOOL_CALL_EXAMPLE -->\n```json\n"
        '{"tool":"edgar_document","arguments":{"action":"read","accession_number":"0001628280-26-050307","document":"[exact-filename-from-list]","cursor":"<page.next_cursor>"}}\n'
        "```\n\n"
        "<!-- MCP_TOOL_CALL_EXAMPLE -->\n```json\n"
        '{"tool":"edgar_document","arguments":{"action":"read","url":"https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/a10-qexhibit32103292025.htm"}}\n'
        "```"
    ),
    params={
        "action": {"type": "string", "enum": ["list", "search", "read"], "description": "Document action."},
        "accession_number": {"type": "string", "description": "SEC accession number, dashed or undashed."},
        "url": {"type": "string", "description": "HTTPS www.sec.gov filing or document URL under /Archives/."},
        "document": {"type": "string", "description": "Exact sequence, filename or exhibit type prefix."},
        "query": {"type": "string", "description": "Text or regular expression to search within filing documents."},
        "regex": {
            "type": "boolean",
            "description": "Treat query as a regular expression with a 50 ms per-document time limit.",
            "default": False,
        },
        "include_all": {"type": "boolean", "description": "Include XBRL and generated R files.", "default": False},
        "around": {
            "type": "object",
            "description": "Start a read centered on a search locator {document, char_offset}.",
            "properties": {
                "document": {"type": "string"},
                "char_offset": {"type": "integer", "minimum": 0},
            },
            "required": ["document", "char_offset"],
        },
        "cursor": {"type": "string", "description": "Continuation cursor from a prior list, search or read page."},
        "limit": {
            "type": "integer",
            "description": "Records per list/search page (default 20, max 50).",
            "default": 20,
        },
    },
    required=["action"],
)
async def edgar_document(
    action: str,
    accession_number: Optional[str] = None,
    url: Optional[str] = None,
    document: Optional[str] = None,
    query: Optional[str] = None,
    regex: bool = False,
    include_all: bool = False,
    around: Optional[dict] = None,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> ToolResponse:
    """List, search or read attachments while retaining exact SEC document identity."""
    if action not in {"list", "search", "read"}:
        return error("action must be one of: list, search, read.", error_code="INVALID_ACTION")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return error("limit must be a positive integer.", error_code="INVALID_LIMIT")
    limit = min(limit, 50)
    if action == "search" and (not isinstance(query, str) or not query):
        return error("query is required for action='search'.", error_code="QUERY_REQUIRED")
    if action == "read" and around is not None and cursor:
        return error("around and cursor cannot be used together.", error_code="AROUND_CURSOR_CONFLICT")
    if action == "read" and around is not None:
        if (
            not isinstance(around, dict)
            or not isinstance(around.get("document"), str)
            or isinstance(around.get("char_offset"), bool)
            or not isinstance(around.get("char_offset"), int)
            or around["char_offset"] < 0
        ):
            return error(
                "around must contain a document string and a non-negative integer char_offset.",
                error_code="INVALID_LOCATOR",
            )
    if action == "search" and regex:
        try:
            re.compile(query or "")
        except re.error as exc:
            return error(f"Invalid regular expression: {exc}", error_code="INVALID_QUERY")

    accession, url_filename, selected_by, input_error = _source_input(accession_number, url)
    if input_error:
        return input_error

    try:
        from edgar import find
        filing = find(search_id=accession)
    except Exception as exc:
        return error(f"Could not resolve SEC filing {accession}: {exc}", error_code="FILING_NOT_FOUND")
    if filing is None:
        return error(
            f"Filing {accession} was not found.",
            suggestions=["Check the accession number or use edgar_search to locate the filing."],
            error_code="FILING_NOT_FOUND",
        )

    try:
        attachments = _attachments(filing)
    except RuntimeError as exc:
        return error(str(exc), error_code="ATTACHMENTS_UNAVAILABLE")

    selector = document
    url_attachment = None
    if url_filename and action in {"read", "search"}:
        url_attachment, url_error = _resolve_attachment(attachments, url_filename)
        if url_error:
            return url_error
        if document is not None:
            document_attachment, document_error = _resolve_attachment(attachments, document)
            if document_error:
                return document_error
            if document_attachment.document != url_attachment.document:
                return error(
                    "The URL filename and document selector identify different attachments.",
                    error_code="DOCUMENT_MISMATCH",
                )
        if action == "read" and around is not None:
            around_attachment, around_error = _resolve_attachment(attachments, around["document"])
            if around_error:
                return around_error
            if around_attachment.document != url_attachment.document:
                return error(
                    "The URL filename and around.document identify different attachments.",
                    error_code="DOCUMENT_MISMATCH",
                )
        selector = url_attachment.document

    if action == "read" and around is not None:
        if selector and selector != around["document"]:
            explicit_attachment, select_error = _resolve_attachment(attachments, selector)
            around_attachment, around_error = _resolve_attachment(attachments, around["document"])
            if select_error:
                return select_error
            if around_error:
                return around_error
            if explicit_attachment.document != around_attachment.document:
                return error(
                    "document and around.document identify different attachments.",
                    error_code="DOCUMENT_MISMATCH",
                )
        selector = around["document"]
    if selector is None and url_filename and action in {"read", "search"}:
        selector = url_filename

    selected_attachment = None
    if selector is not None and action in {"read", "search"}:
        selected_attachment, selection_error = _resolve_attachment(attachments, selector)
        if selection_error:
            return selection_error
        if not include_all and _is_hidden_by_default(selected_attachment):
            return error(
                f"Document {selected_attachment.document!r} is hidden by the default XBRL "
                "and generated-file filter.",
                suggestions=["Retry with include_all=true to include XBRL and generated R files."],
                error_code="DOCUMENT_HIDDEN",
            )

    filer, source = _filing_identity(filing, selected_by or "accession", selected_attachment)

    if action == "list":
        records = [_identity(a) for a in _eligible(attachments, include_all)]
        page_query = {"action": "list", "include_all": bool(include_all)}
        items, page, page_error = _page_records(
            action="list", accession=accession, document=None, records=records,
            cursor=cursor, limit=limit, query=page_query,
        )
        if page_error:
            return page_error
        return success({
            "accession_number": accession,
            "documents": items,
            "page": page,
            "incorporated_by_reference_note": _LIST_NOTE,
            "evidence_scope_note": _EVIDENCE_SCOPE_NOTE,
            "filer": filer,
            "source": source,
        })

    if action == "search":
        targets = [selected_attachment] if selected_attachment is not None else _eligible(attachments, include_all)
        filter_document = selected_attachment.document if selected_attachment is not None else None
        try:
            matches, overflowed = _serialized_matches(
                filing,
                targets,
                query or "",
                bool(regex),
                document_filter=filter_document,
                include_all=bool(include_all),
            )
        except TimeoutError:
            return error(
                "Regex search timed out at the 50 ms per-document limit; partial results were discarded.",
                suggestions=[
                    "Simplify the regular expression to avoid excessive backtracking.",
                    "Narrow the search to one exact document or use a literal text query.",
                ],
                error_code="REGEX_TIMEOUT",
            )
        if overflowed:
            return error(
                "Search exceeded the limit of 1,000 matches per filing or found a match longer than "
                "2,048 characters.",
                suggestions=[
                    "Narrow the query or regular expression to reduce the number or size of matches.",
                    "Search one exact document at a time by setting document to its filename or sequence.",
                ],
                error_code="QUERY_TOO_BROAD",
            )
        page_query = {
            "action": "search",
            "query": query,
            "regex": bool(regex),
            "include_all": bool(include_all),
        }
        items, page, page_error = _page_records(
            action="search", accession=accession, document=filter_document, records=matches,
            cursor=cursor, limit=limit, query=page_query,
        )
        if page_error:
            return page_error
        return success({
            "accession_number": accession,
            "matches": items,
            "page": page,
            "evidence_scope_note": _EVIDENCE_SCOPE_NOTE,
            "filer": filer,
            "source": source,
        })

    if selected_attachment is None:
        return error(
            "A document selector is required for action='read'.",
            suggestions=["Provide document as a sequence number, filename or exhibit type, or use around."],
            error_code="DOCUMENT_REQUIRED",
        )

    text, unreadable_reason = _read_text(filing, selected_attachment)
    if unreadable_reason:
        return success({
            "accession_number": accession,
            "document": _identity(selected_attachment),
            "unreadable_reason": unreadable_reason,
            "evidence_scope_note": _EVIDENCE_SCOPE_NOTE,
            "filer": filer,
            "source": source,
        })

    assert text is not None
    fp = fingerprint([text])
    try:
        payload = decode_cursor(
            cursor,
            tool=_READ_TOOL,
            accession=accession,
            document=selected_attachment.document,
            query=None,
        ) if cursor else None
        if payload is not None:
            check_fingerprint(payload, fp)
    except Exception as exc:
        if hasattr(exc, "to_response"):
            return exc.to_response()
        return error(str(exc), error_code="INVALID_CURSOR")

    if payload is not None:
        offset = payload["off"]
    elif around is not None:
        char_offset = around["char_offset"]
        if char_offset > len(text):
            return error(
                f"around.char_offset {char_offset} is beyond the document's {len(text)} characters.",
                error_code="INVALID_LOCATOR",
            )
        offset = max(0, min(char_offset - TEXT_PAGE_CHARS // 2, len(text) - TEXT_PAGE_CHARS))
    else:
        offset = 0

    page_text, meta = paginate_text(text, offset=offset, budget=TEXT_PAGE_CHARS)
    next_cursor = None
    if meta["next_offset"] is not None:
        next_cursor, cursor_error = try_encode_cursor(
            tool=_READ_TOOL,
            accession=accession,
            document=selected_attachment.document,
            query=None,
            offset=meta["next_offset"],
            fp=fp,
        )
        if cursor_error:
            return cursor_error
    return success({
        "accession_number": accession,
        "document": _identity(selected_attachment),
        "text": page_text,
        "page": {
            "offset": offset,
            "total_chars": meta["total_chars"],
            "remaining_chars": meta["remaining_chars"],
            "next_cursor": next_cursor,
        },
        "evidence_scope_note": _EVIDENCE_SCOPE_NOTE,
        "filer": filer,
        "source": source,
    })
