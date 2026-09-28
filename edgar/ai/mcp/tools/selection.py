"""
Shared filing selection for MCP tools.

Several intent tools (edgar_fund, edgar_notes, edgar_read, ...) all answer the
same underlying question — "which filing does the caller mean?" — from the
same three inputs: an explicit accession number, a reporting period, or
nothing (meaning "the latest"). Each tool used to answer it slightly
differently, so the same request could pick a different filing depending on
which tool handled it, and a wrong-period request could silently fall back to
the nearest period instead of saying so.

``resolve_report_filing`` is the one place that logic lives now. It has no
tool-specific behaviour — it takes an identifier/company plus the optional
selectors and returns a ``FilingSelection`` or raises ``FilingSelectionError``
with a response-ready error code. Once a tool has the resolved filing, it
builds the response's provenance block with ``format_source`` from
``edgar.ai.mcp.tools.base``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from edgar.ai.mcp.tools.base import error, resolve_company

logger = logging.getLogger(__name__)

# YYYY-MM-DD, matched literally before being parsed as a calendar date so a
# malformed shape ("06-30-2026") gets the same INVALID_ARGUMENTS treatment
# as a malformed value ("2026-02-30").
_PERIOD_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FilingSelectionError(Exception):
    """Raised when ``resolve_report_filing`` cannot resolve a filing.

    Carries everything a tool needs to hand back a proper error response
    without re-deriving the error code itself — call ``to_response()``.
    """

    def __init__(self, message: str, error_code: str, suggestions: Optional[list[str]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.suggestions = suggestions or []

    def to_response(self):
        """Build the standard MCP error response for this failure."""
        return error(self.message, suggestions=self.suggestions, error_code=self.error_code)


@dataclass(frozen=True)
class FilingSelection:
    """A resolved filing plus how it was chosen."""
    filing: Any
    selected_by: str  # "accession" | "period" | "latest"


def resolve_report_filing(
    identifier: Optional[str] = None,
    form: str = "10-K",
    accession_number: Optional[str] = None,
    period: Optional[str] = None,
    company=None,
) -> FilingSelection:
    """Resolve exactly one filing from an identifier/company plus selectors.

    Precedence is ``accession_number`` > ``period`` > latest original filing.
    An amendment (``/A``) is reachable only by accession number — the period
    and latest paths always filter to ``amendments=False``. A ``period`` that
    matches no filing never falls back to the nearest one; it raises with the
    available periods as suggestions instead.

    Args:
        identifier: Company ticker, CIK, or name. Ignored when ``company`` is
            given. Required (directly or via ``company``) for the period and
            latest paths; optional for the accession path, where it is only
            used to cross-check the accession's CIK.
        form: Form type to select within (default "10-K").
        accession_number: Exact accession number. Wins over everything else.
        period: ``YYYY-MM-DD`` that must exactly equal the ``report_date``
            (the submissions-JSON field behind ``period_of_report``) of an
            original filing of ``form``.
        company: A pre-resolved Company/Entity, for callers that already have
            one. Takes precedence over ``identifier``.

    Returns:
        FilingSelection with the chosen filing and how it was selected.

    Raises:
        FilingSelectionError: with one of FILING_NOT_FOUND, SELECTION_MISMATCH,
            INVALID_ARGUMENTS, PERIOD_NOT_FOUND, or COMPANY_NOT_FOUND.
    """
    if accession_number:
        return _resolve_by_accession(accession_number, identifier, company)

    resolved_company = _resolve_company(identifier, company)

    if period:
        return _resolve_by_period(resolved_company, form, period)

    return _resolve_latest(resolved_company, form)


def _resolve_company(identifier: Optional[str], company) -> Any:
    """Return ``company`` as given, or resolve ``identifier`` via base.py."""
    if company is not None:
        return company
    try:
        return resolve_company(identifier or "")
    except Exception as exc:
        raise FilingSelectionError(
            f"Could not find company: {exc}",
            error_code="COMPANY_NOT_FOUND",
            suggestions=[
                "Check the ticker or CIK is correct",
                "Use edgar_search to find the company first",
            ],
        ) from exc


def _resolve_by_accession(accession_number: str, identifier: Optional[str], company) -> FilingSelection:
    from edgar import find

    filing = find(search_id=accession_number)
    if filing is None:
        raise FilingSelectionError(
            f"No filing found for accession number '{accession_number}'.",
            error_code="FILING_NOT_FOUND",
            suggestions=["Check the accession number format: NNNNNNNNNN-NN-NNNNNN"],
        )

    if identifier or company is not None:
        resolved_company = _resolve_company(identifier, company)
        if int(resolved_company.cik) != int(filing.cik):
            raise FilingSelectionError(
                f"Accession '{accession_number}' belongs to CIK {filing.cik}, "
                f"not CIK {resolved_company.cik}.",
                error_code="SELECTION_MISMATCH",
                suggestions=[
                    "Drop the identifier and use the accession number alone",
                    "Verify the accession number belongs to this company",
                ],
            )

    return FilingSelection(filing=filing, selected_by="accession")


def _resolve_by_period(company, form: str, period: str) -> FilingSelection:
    if not _PERIOD_SHAPE.match(period):
        raise FilingSelectionError(
            f"Invalid period '{period}'. Expected YYYY-MM-DD.",
            error_code="INVALID_ARGUMENTS",
            suggestions=["Use YYYY-MM-DD format, e.g. 2026-06-30"],
        )
    try:
        date.fromisoformat(period)
    except ValueError as exc:
        raise FilingSelectionError(
            f"Invalid period '{period}': {exc}",
            error_code="INVALID_ARGUMENTS",
            suggestions=["Use YYYY-MM-DD format, e.g. 2026-06-30"],
        ) from exc

    # `report_date` is a plain field from the submissions JSON that
    # get_filings() already loaded — matching against it costs nothing extra.
    # `Filing.period_of_report` looks the same in a debugger but is a
    # property that calls self.sgml(), downloading the entire filing
    # submission (its full .txt) just to read one date. Iterating every
    # filing of a form through that property — which is exactly what
    # matching a period against a company's whole history does — turned one
    # lookup into dozens of multi-hundred-KB downloads. report_date is never
    # touched for this, and a filing with no report_date is simply not a
    # candidate; it is never "resolved" by falling back to the download.
    filings = list(company.get_filings(form=form, amendments=False, trigger_full_load=False))
    matches = _match_period(filings, period)

    if not matches:
        # Mirrors Entity.latest()'s pattern (edgar/entity/core.py): the first
        # page is whatever get_filings() already had loaded; only pay for the
        # full historical load when the period genuinely isn't on that page.
        filings = list(company.get_filings(form=form, amendments=False, trigger_full_load=True))
        matches = _match_period(filings, period)

    if not matches:
        raise FilingSelectionError(
            f"No {form} filing found with period_of_report == '{period}'.",
            error_code="PERIOD_NOT_FOUND",
            suggestions=_period_suggestions(filings, form),
        )

    filing = matches[0] if len(matches) == 1 else _most_recent(matches)
    return FilingSelection(filing=filing, selected_by="period")


def _resolve_latest(company, form: str) -> FilingSelection:
    # No period to search for, so there is nothing that would ever justify
    # paying for the full historical load here — the most recent page is
    # exactly where "latest" lives.
    filings = list(company.get_filings(form=form, amendments=False, trigger_full_load=False))
    if not filings:
        raise FilingSelectionError(
            f"No {form} filings found for this company.",
            error_code="FILING_NOT_FOUND",
            suggestions=["Try a different form type", "Check the company has filed this form"],
        )
    return FilingSelection(filing=_most_recent(filings), selected_by="latest")


def _most_recent(filings: list) -> Any:
    """The most recently filed among ``filings`` (ties keep first encountered)."""
    return max(filings, key=lambda f: str(f.filing_date))


def _report_date(filing) -> Optional[str]:
    """``filing.report_date`` as a non-empty string, or ``None``.

    Deliberately never touches ``period_of_report`` — see the comment in
    ``_resolve_by_period`` for why.
    """
    value = getattr(filing, "report_date", None)
    return str(value) if value else None


def _match_period(filings: list, period: str) -> list:
    """Filings whose report_date exactly equals ``period``."""
    return [f for f in filings if _report_date(f) == period]


def _period_suggestions(filings: list, form: str) -> list[str]:
    """Up to 8 available periods, most recently filed first."""
    ordered = sorted(filings, key=lambda f: str(f.filing_date), reverse=True)
    periods: list[str] = []
    for f in ordered:
        p_str = _report_date(f)
        if p_str is None:
            continue
        if p_str not in periods:
            periods.append(p_str)
        if len(periods) >= 8:
            break
    if not periods:
        return [f"No {form} filings found for this company"]
    return [f"Available {form} periods: {', '.join(periods)}"]
