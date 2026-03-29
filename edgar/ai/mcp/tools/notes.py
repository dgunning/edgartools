"""
Notes Tool (edgar_notes)

Drill into the notes and disclosures behind financial statement numbers.
Given a company and topic, returns structured note content: narrative text,
table data, which statement line items the note expands, and child tables.

This is the tool to call when an AI needs to explain WHY a number is what
it is — not just what the number is.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from edgar.ai.mcp.tools.base import (
    tool,
    success,
    error,
    resolve_company,
)

logger = logging.getLogger(__name__)


def _build_note_data(note, detail: str = 'standard') -> dict:
    """Build a structured dict from a Note object."""
    data = {
        'number': note.number,
        'title': note.title,
    }

    # Which statement line items this note explains
    if note.expands:
        data['expands'] = note.expands
    if note.expands_statements:
        data['expands_statements'] = note.expands_statements

    # Child tables
    if note.tables:
        tables = []
        for t in note.tables:
            table_info = {'role': t.role_or_type}
            try:
                rendered = t.render()
                if rendered:
                    table_info['title'] = rendered.title
            except Exception:
                pass
            # Try to get DataFrame summary from XBRL
            if detail == 'full':
                try:
                    df = t.to_dataframe()
                    if df is not None and not df.empty:
                        table_info['rows'] = len(df)
                        table_info['columns'] = list(df.columns[:10])
                        # Include first few rows as records
                        table_info['data'] = df.head(10).to_dict(orient='records')
                except Exception:
                    pass
            tables.append(table_info)
        data['tables'] = tables

    # AI-optimized context string
    data['context'] = note.to_context(detail=detail)

    return data


@tool(
    name="edgar_notes",
    description="""Drill into the notes and disclosures behind financial statement numbers. Use this when you need to explain WHY a number is what it is — debt terms, revenue recognition policies, lease schedules, contingencies, etc.

Returns the note's narrative text, which statement line items it explains, and structured table data.

Examples:
- What does Apple's debt note say? topic="debt", identifier="AAPL"
- Revenue recognition policy: topic="revenue", identifier="MSFT"
- All notes overview: identifier="TSLA" (no topic = table of contents)""",
    params={
        "identifier": {
            "type": "string",
            "description": "Company ticker (AAPL), CIK (320193), or name"
        },
        "topic": {
            "type": "string",
            "description": "Note topic to search for (e.g., 'debt', 'revenue', 'leases', 'contingencies'). Omit for table of contents."
        },
        "form": {
            "type": "string",
            "description": "Filing form type (default: 10-K). Use 10-Q for quarterly notes.",
            "default": "10-K"
        },
        "detail": {
            "type": "string",
            "enum": ["minimal", "standard", "full"],
            "description": "Detail level: minimal (titles only), standard (context + tables), full (includes DataFrame data)",
            "default": "standard"
        }
    },
    required=["identifier"]
)
async def edgar_notes(
    identifier: str,
    topic: Optional[str] = None,
    form: str = "10-K",
    detail: str = "standard",
) -> Any:
    """Get notes and disclosures for a company filing."""
    try:
        company = resolve_company(identifier)
    except Exception as e:
        return error(
            f"Could not find company '{identifier}': {e}",
            suggestions=["Check the ticker or CIK", "Use edgar_search to find the company"]
        )

    # Get the filing
    try:
        filings = company.get_filings(form=form, amendments=False)
        if not filings or len(filings) == 0:
            return error(
                f"No {form} filings found for {company}",
                suggestions=[f"Try form='10-Q' for quarterly", "Use edgar_search to check available filings"]
            )
        filing = filings[0]
    except Exception as e:
        return error(f"Error retrieving filings: {e}")

    # Get the typed object (TenK, TenQ, etc.)
    try:
        obj = filing.obj()
    except Exception as e:
        return error(
            f"Could not parse {form} filing: {e}",
            suggestions=["The filing may not have XBRL data", "Try a different filing"]
        )

    if not hasattr(obj, 'notes'):
        return error(
            f"{type(obj).__name__} does not support notes",
            suggestions=["Notes are available for 10-K and 10-Q filings"]
        )

    notes = obj.notes
    if not notes or len(notes) == 0:
        return error(
            f"No notes found in {form} filing for {company}",
            suggestions=["The filing may not have FilingSummary.xml", "Try a different filing period"]
        )

    result = {
        'company': str(company),
        'form': filing.form,
        'filed': str(filing.filing_date),
        'period': getattr(obj, 'period_of_report', None),
        'total_notes': len(notes),
    }

    if topic:
        # Search for specific notes
        matched = notes.search(topic)
        if not matched:
            # List available notes as suggestions
            available = [n.short_name for n in notes]
            return error(
                f"No notes matching '{topic}' in {company} {form}",
                suggestions=[f"Available notes: {', '.join(available[:10])}"]
            )

        result['topic'] = topic
        result['matched_notes'] = len(matched)
        result['notes'] = [_build_note_data(note, detail=detail) for note in matched]

        next_steps = []
        # Suggest drill-down for the primary match
        primary = matched[0]
        if primary.expands_statements:
            stmts = primary.expands_statements
            next_steps.append(
                f"Use edgar_company to see the {', '.join(stmts)} for {company}"
            )
        if len(matched) > 1:
            other_titles = [n.title for n in matched[1:3]]
            next_steps.append(f"Related notes also matched: {', '.join(other_titles)}")

        return success(result, next_steps=next_steps)

    else:
        # Table of contents — list all notes
        result['notes'] = []
        for note in notes:
            entry = {
                'number': note.number,
                'title': note.title,
                'tables': note.table_count,
                'policies': len(note.policies),
                'details': len(note.details),
            }
            if detail != 'minimal' and note.expands:
                entry['expands'] = note.expands[:5]
            result['notes'].append(entry)

        return success(
            result,
            next_steps=[
                f"Use edgar_notes with topic='debt' (or any note title) to drill into a specific note",
                f"Use edgar_company with include=['financials'] for {company} financial data",
            ]
        )
