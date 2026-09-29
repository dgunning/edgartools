"""
Filing Tool (edgar_filing)

The primary tool for examining any SEC filing. Takes an accession number or
SEC URL and returns structured context: what the filing is, key data, and
available actions. Uses to_context() from the filing's typed data object
when available (TenK, Form4, ThirteenF, etc.).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from urllib.parse import unquote, urlsplit

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    get_error_suggestions,
)

logger = logging.getLogger(__name__)

# Regex for dashed accession number: 0000320193-23-000077
_ACCESSION_DASHED = re.compile(r'(\d{10}-\d{2}-\d{6})')
# Regex for undashed accession number in paths: 000032019323000077
_ACCESSION_UNDASHED = re.compile(r'(?<!\d)(\d{18})(?!\d)')


def _extract_accession(text: str) -> Optional[str]:
    """Extract an accession number from a string, URL, or raw accession number."""
    if not text:
        return None
    text = text.strip()

    # Try dashed format first
    m = _ACCESSION_DASHED.search(text)
    if m:
        return m.group(1)

    # Try undashed format (18 consecutive digits)
    m = _ACCESSION_UNDASHED.search(text)
    if m:
        d = m.group(1)
        return f"{d[:10]}-{d[10:12]}-{d[12:]}"

    return None


def _sec_document_filename(value: Optional[str]) -> Optional[str]:
    """Return a document filename only for a direct SEC Archives document URL.

    The caller-provided URL is parsed locally and is never fetched.
    """
    if not value:
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme != "https" or parsed.netloc != "www.sec.gov":
        return None

    parts = parsed.path.split("/")
    if (
        len(parts) != 7
        or parts[1:4] != ["Archives", "edgar", "data"]
        or not parts[4].isdigit()
        or not re.fullmatch(r"\d{18}", parts[5])
    ):
        return None

    try:
        filename = unquote(parts[6], errors="strict")
    except (UnicodeDecodeError, ValueError):
        return None
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        return None
    return filename


def _document_hint(filing, input_value: Optional[str]) -> Optional[dict[str, Any]]:
    """Describe whether a direct SEC document URL names a filing attachment."""
    filename = _sec_document_filename(input_value)
    if filename is None:
        return None

    attachment = None
    try:
        for item in filing.attachments:
            if getattr(item, "document", None) == filename:
                attachment = item
                break
    except Exception:
        # Metadata failure is not evidence that the document is absent.
        return {
            "filename": filename,
            "matched": None,
            "status": "unavailable",
            "reason": "Attachment metadata could not be checked.",
        }

    hint = {"filename": filename, "matched": attachment is not None}
    if attachment is not None:
        sequence = getattr(attachment, "sequence_number", None)
        if sequence is not None:
            hint["sequence_number"] = str(sequence)
    return hint


@tool(
    name="edgar_filing",
    description="""Use this to examine any SEC filing. Returns structured context: what the filing is, key data, and available next steps. If the filing has a typed data object (10-K, 10-Q, 8-K, Form 4, 13F, DEF 14A, etc.), returns extracted financials, sections, ownership, transactions, etc.

Two ways to specify the filing:
1. By company + form type: identifier="AAPL", form="10-K" (gets the latest)
2. By accession number or URL: input="0000320193-23-000077"

Examples:
- Apple's latest 10-K: identifier="AAPL", form="10-K"
- Latest 8-K: identifier="TSLA", form="8-K"
- By accession: input="0000320193-23-000077"
- From URL: input="https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/..."

Use edgar_read for report sections such as MD&A. Use edgar_document for exact attachments and exhibits.

<!-- MCP_TOOL_CALL_EXAMPLE -->
```json
{"tool":"edgar_filing","arguments":{"input":"0000320193-23-000077","detail":"standard"}}
```
- Minimal overview: identifier="MSFT", form="10-Q", detail="minimal\"""",
    params={
        "identifier": {
            "type": "string",
            "description": "Company ticker (AAPL), CIK (320193), or name. Used with 'form' to get the latest filing."
        },
        "form": {
            "type": "string",
            "description": "Form type (10-K, 10-Q, 8-K, DEF 14A, 4, 13F-HR, etc.). Used with 'identifier'."
        },
        "input": {
            "type": "string",
            "description": "Accession number or URL containing an accession number (alternative to identifier+form)"
        },
        "detail": {
            "type": "string",
            "enum": ["minimal", "standard", "full"],
            "description": "Detail level for context output (default: standard)",
            "default": "standard"
        }
    },
    required=[]
)
async def edgar_filing(
    identifier: Optional[str] = None,
    form: Optional[str] = None,
    input: Optional[str] = None,
    detail: str = "standard",
) -> Any:
    """Get AI context for a filing by company+form or accession number."""
    try:
        filing = None

        # Path 1: identifier + form → get latest filing
        if identifier and form:
            try:
                from edgar.ai.mcp.tools.base import resolve_company
                company = resolve_company(identifier)
                # For annual/quarterly reports, prefer original filings over amendments
                # since amendments often have incomplete data
                _PREFER_ORIGINAL = {'10-K', '10-Q', '20-F', '40-F'}
                skip_amendments = form.replace('/A', '') in _PREFER_ORIGINAL
                filings = company.get_filings(form=form, amendments=not skip_amendments)
                if filings and len(filings) > 0:
                    filing = filings[0]
            except Exception as e:
                return error(
                    f"Could not find {form} filing for '{identifier}': {e}",
                    suggestions=[
                        "Check the ticker or CIK is correct",
                        "Use edgar_search to find the company first",
                    ]
                )

        # Path 2: accession number or URL
        elif input:
            accession = _extract_accession(input)
            if not accession:
                return error(
                    f"Could not find an accession number in: {input[:100]}",
                    suggestions=[
                        "Provide identifier + form (e.g., identifier='AAPL', form='10-K')",
                        "Or a dashed accession number like '0000320193-23-000077'",
                    ]
                )
            from edgar import find
            filing = find(search_id=accession)

        else:
            return error(
                "No filing specified",
                suggestions=[
                    "Provide identifier + form: identifier='AAPL', form='10-K'",
                    "Or provide input with an accession number or URL",
                ]
            )

        if filing is None:
            return error(
                "Filing not found",
                suggestions=[
                    "Check the accession number is correct",
                    "Use edgar_search to find filings by company or form type",
                ]
            )

        # Try to get the typed data object
        obj = None
        obj_type = None
        try:
            obj = filing.obj()
            if obj is not None:
                obj_type = type(obj).__name__
        except Exception:
            pass

        # Build context using to_context()
        if obj is not None and hasattr(obj, 'to_context'):
            context_text = obj.to_context(detail=detail)
            source = "data_object"
        else:
            context_text = filing.to_context(detail=detail)
            source = "filing"

        result = {
            "accession_number": filing.accession_no,
            "form": filing.form,
            "company": getattr(filing, 'company', None),
            "filed": str(filing.filing_date),
            "source": source,
            "context": context_text,
        }

        # Prefer report_date, which is already loaded by filings/search results.
        # Only consult period_of_report when it is absent; that property may
        # need to load the filing's SGML header.
        period_of_report = getattr(filing, "report_date", None)
        if not period_of_report:
            try:
                period_of_report = getattr(filing, "period_of_report", None)
            except Exception:
                period_of_report = None
        result["period_of_report"] = (
            str(period_of_report) if period_of_report is not None else None
        )
        try:
            result["url"] = getattr(filing, "url", None)
        except Exception:
            result["url"] = None

        document_hint = _document_hint(filing, input)
        if document_hint is not None:
            result["document_hint"] = document_hint

        if obj_type:
            result["data_object_type"] = obj_type

        next_steps = []
        if source == "filing":
            next_steps.append("Use edgar_read to extract specific sections from this filing")
        if obj_type:
            next_steps.append(f"Filing parsed as {obj_type} — see AVAILABLE ACTIONS in context")
            next_steps.append("Use edgar_read to extract section text (risk_factors, mda, business, etc.)")
        next_steps.append("Use edgar_company for full company profile")

        if document_hint is not None:
            if document_hint["matched"]:
                document_args = json.dumps({
                    "action": "read",
                    "accession_number": filing.accession_no,
                    "document": document_hint["filename"],
                })
                next_steps.append(
                    f"Use edgar_document with {document_args} to read the exact filing document."
                )
            elif document_hint["matched"] is False:
                list_args = json.dumps({
                    "action": "list",
                    "accession_number": filing.accession_no,
                })
                next_steps.append(
                    f"SEC URL filename {document_hint['filename']!r} was not found among this filing's "
                    f"attachments. Use edgar_document with {list_args} to choose an attached document."
                )
            else:
                list_args = json.dumps({
                    "action": "list",
                    "accession_number": filing.accession_no,
                })
                next_steps.append(
                    "Attachment metadata could not be checked, so the SEC URL filename was not verified. "
                    f"Use edgar_document with {list_args} to list this filing's documents."
                )

        return success(result, next_steps=next_steps)

    except Exception as e:
        logger.exception("Error in edgar_context")
        return error(str(e), suggestions=get_error_suggestions(e))
