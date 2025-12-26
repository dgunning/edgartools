"""
High-level API for LLM-optimized content extraction from SEC filings.

This module provides a simple interface for extracting filing content
as clean, token-efficient markdown suitable for LLM processing.

Features:
- XBRL statements: Uses EdgarTools rendering → DataFrame → optimized markdown
- Notes: Uses filing.reports.get_by_category("Notes") with LLM optimization
- Items: Uses Document sections or regex fallback
- Smart table preprocessing (currency/percent merging)
- Column deduplication
- Noise filtering

Example:
    >>> from edgar import Filing
    >>> from edgar.llm import extract_markdown
    >>>
    >>> filing = Filing(form='10-K', cik='0000320193', accession_no='...')
    >>>
    >>> # Extract everything optimized for LLM
    >>> markdown = extract_markdown(
    ...     filing,
    ...     item=["1", "7"],
    ...     statement=["IncomeStatement"],
    ...     notes=True
    ... )
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from edgar.core import log

__all__ = [
    'ExtractedSection',
    'extract_markdown',
    'extract_sections',
]


@dataclass
class ExtractedSection:
    """
    Extracted section with LLM-optimized markdown.

    Attributes:
        title: Section title
        markdown: Markdown content
        source: Source identifier (e.g., 'xbrl:IncomeStatement', 'item:1', 'notes:xbrl:5')
        is_xbrl: Whether content comes from XBRL data
    """
    title: str
    markdown: str
    source: str
    is_xbrl: bool = False


# Statement name mappings
_STATEMENT_TITLES = {
    "IncomeStatement": "Income Statement",
    "BalanceSheet": "Balance Sheet",
    "CashFlowStatement": "Cash Flow Statement",
    "StatementOfEquity": "Statement of Equity",
    "ComprehensiveIncome": "Comprehensive Income",
    "CoverPage": "Cover Page",
}

# Item boundary patterns for LLM section extraction
# NOTE: Authoritative source for 10-K/10-Q structure is:
#   - edgar.company_reports.ten_k.TenK.structure (all 23 10-K items)
#   - edgar.company_reports.ten_q.TenQ.structure (all 11 10-Q items)
# This dict provides boundaries for section extraction in extract_markdown()
_ITEM_BOUNDARIES = {
    "Item 1": ["Item 1A", "Item 1B", "Item 1C", "Item 2"],
    "Item 1A": ["Item 1B", "Item 1C", "Item 2"],
    "Item 1B": ["Item 1C", "Item 2"],
    "Item 1C": ["Item 2"],
    "Item 2": ["Item 3"],
    "Item 3": ["Item 4"],
    "Item 4": ["Item 5", "Part II"],
    "Item 5": ["Item 7"],  # Item 6 removed 2021
    "Item 7": ["Item 7A", "Item 8"],
    "Item 7A": ["Item 8"],
    "Item 8": ["Item 9", "Item 9A", "Item 9B"],
    "Item 9": ["Item 9A", "Item 9B", "Item 9C"],
    "Item 9A": ["Item 9B", "Item 9C"],
    "Item 9B": ["Item 9C", "Item 10", "Part III"],
    "Item 9C": ["Item 10", "Part III"],
    "Item 10": ["Item 11"],
    "Item 11": ["Item 12"],
    "Item 12": ["Item 13"],
    "Item 13": ["Item 14"],
    "Item 14": ["Item 15", "Part IV"],
    "Item 15": ["Item 16", "Signatures"],
    "Item 16": ["Signatures"],
}


def extract_markdown(
    filing,
    *,
    item: Optional[Union[str, Sequence[str]]] = None,
    statement: Optional[Union[str, Sequence[str]]] = None,
    notes: bool = False,
    include_header: bool = True,
    optimize_for_llm: bool = True,
    show_dimension: bool = True,
    show_filtered_data: bool = False,
    max_filtered_items: Optional[int] = 10
) -> str:
    """
    Extract filing content as LLM-optimized markdown.

    Strategy:
    1. XBRL statements → Use EdgarTools rendering + to_markdown_llm()
    2. Notes → Use filing.reports.get_by_category("Notes") + LLM processing
    3. Non-XBRL items → Use Document sections or regex fallback

    Args:
        filing: Filing object
        item: Item numbers to extract (e.g., "1", "7", ["1", "1A"])
        statement: Statements to extract ("IncomeStatement", "BalanceSheet", etc.)
        notes: Include financial statement notes
        include_header: Add filing metadata header
        optimize_for_llm: Apply LLM optimizations (cell merging, dedup, etc.)
        show_dimension: Include dimension, abstract, and level columns in statements (default: True)
        show_filtered_data: Append metadata about filtered/omitted data at end (default: False)
        max_filtered_items: Maximum filtered items to show in metadata (None = all, default: 10)

    Returns:
        Combined markdown string

    Example:
        >>> filing = Filing(form='10-K', cik='0000320193', accession_no='...')
        >>> md = extract_markdown(
        ...     filing,
        ...     item=["1", "7"],
        ...     statement=["IncomeStatement"],
        ...     notes=True
        ... )
    """
    sections, filtered_data = extract_sections(
        filing,
        item=item,
        statement=statement,
        notes=notes,
        optimize_for_llm=optimize_for_llm,
        show_dimension=show_dimension,
        track_filtered=show_filtered_data
    )

    parts = []

    if include_header:
        header = _build_header(filing, sections)
        if header:
            parts.append(header)
            parts.append("")

    for section in sections:
        parts.append(f"## SECTION: {section.title}")
        if section.is_xbrl:
            parts.append("<!-- Source: XBRL -->")
        parts.append(section.markdown)
        parts.append("")

    # Append filtered data metadata if requested
    if show_filtered_data and filtered_data:
        parts.append("")
        parts.append("---")
        parts.append("## FILTERED DATA METADATA")
        parts.append("")

        total_filtered = sum([
            filtered_data.get("xbrl_metadata_tables", 0),
            filtered_data.get("duplicate_tables", 0),
            filtered_data.get("filtered_text_blocks", 0)
        ])

        parts.append(f"Total items filtered: {total_filtered}")
        parts.append(f"- XBRL metadata tables: {filtered_data.get('xbrl_metadata_tables', 0)}")
        parts.append(f"- Duplicate tables: {filtered_data.get('duplicate_tables', 0)}")
        parts.append(f"- Filtered text blocks: {filtered_data.get('filtered_text_blocks', 0)}")

        if filtered_data.get("details"):
            parts.append("")
            parts.append("### Details:")
            # Show limited or all items based on max_filtered_items
            details_to_show = filtered_data["details"]
            if max_filtered_items is not None:
                details_to_show = details_to_show[:max_filtered_items]

            for i, detail in enumerate(details_to_show, 1):
                parts.append(f"{i}. Type: {detail['type']}")
                if "reason" in detail:
                    parts.append(f"   Reason: {detail['reason']}")
                if "preview" in detail:
                    parts.append(f"   Preview: {detail['preview']}")
                elif "title" in detail:
                    parts.append(f"   Title: {detail['title']}")

            # Show count if items were truncated
            total_details = len(filtered_data["details"])
            if max_filtered_items is not None and total_details > max_filtered_items:
                parts.append(f"   ... and {total_details - max_filtered_items} more items (use max_filtered_items=None to see all)")

    # Join parts and normalize line endings to Unix LF
    result = "\n".join(parts)

    # Normalize line endings: Windows CRLF → Unix LF
    result = result.replace('\r\n', '\n')  # CRLF to LF
    result = result.replace('\r', '\n')    # Old Mac CR to LF

    return result


def extract_sections(
    filing,
    *,
    item: Optional[Union[str, Sequence[str]]] = None,
    statement: Optional[Union[str, Sequence[str]]] = None,
    notes: bool = False,
    optimize_for_llm: bool = True,
    show_dimension: bool = True,
    track_filtered: bool = False
):
    """
    Extract sections as structured objects.

    Args:
        filing: Filing object
        item: Item numbers to extract
        statement: Statement names to extract
        notes: Include financial statement notes
        optimize_for_llm: Apply LLM optimizations
        show_dimension: Include dimension, abstract, level columns in statements
        track_filtered: Track filtered data and return metadata

    Returns:
        If track_filtered=True: Tuple of (List[ExtractedSection], dict) with filtered metadata
        If track_filtered=False: List[ExtractedSection] objects

    Example:
        >>> sections = extract_sections(filing, notes=True)
        >>> for section in sections:
        ...     print(f"{section.title} (XBRL: {section.is_xbrl})")
        ...     print(section.markdown)
    """
    sections = []
    all_filtered_data = {
        "xbrl_metadata_tables": 0,
        "duplicate_tables": 0,
        "filtered_text_blocks": 0,
        "details": []
    } if track_filtered else None

    # 1. Extract XBRL statements (if requested)
    if statement:
        sections.extend(_extract_xbrl_statements(
            filing,
            statement,
            optimize_for_llm,
            show_dimension
        ))

    # 2. Extract items (if requested)
    if item:
        sections.extend(_extract_items(
            filing,
            item,
            optimize_for_llm
        ))

    # 3. Extract notes (if requested)
    if notes:
        notes_sections, notes_filtered = _extract_notes(
            filing,
            optimize_for_llm,
            track_filtered
        )
        sections.extend(notes_sections)

        # Merge filtered data
        if track_filtered and notes_filtered:
            for key in ["xbrl_metadata_tables", "duplicate_tables", "filtered_text_blocks"]:
                all_filtered_data[key] += notes_filtered.get(key, 0)
            all_filtered_data["details"].extend(notes_filtered.get("details", []))

    if track_filtered:
        return (sections, all_filtered_data)
    return sections


def _normalize_list(value: Optional[Union[str, Sequence[str]]]) -> List[str]:
    """Normalize input to list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [v for v in value if v]


def _build_header(filing: 'Filing', sections: List['ExtractedSection']) -> str:
    """
    Build filing metadata header in YAML frontmatter format.

    Args:
        filing: Filing object
        sections: List of extracted sections (for section titles)

    Returns:
        YAML frontmatter block with filing metadata
    """
    # Extract basic filing info
    form = getattr(filing, 'form', None)
    accession_no = getattr(filing, 'accession_no', None)
    filing_date = getattr(filing, 'filing_date', None)

    # Try to get company name and ticker
    company_name = None
    ticker = None

    # Get company name (filing.company is a string)
    if hasattr(filing, 'company'):
        company_name = filing.company if isinstance(filing.company, str) else None

    # Try to get ticker from CIK
    if hasattr(filing, 'cik'):
        try:
            from edgar.reference.tickers import find_ticker
            cik = filing.cik
            ticker = find_ticker(cik)
        except Exception:
            # If reference lookup fails, try other methods
            pass

    # Fallback: try direct ticker attribute
    if not ticker and hasattr(filing, 'ticker'):
        ticker = filing.ticker

    # Get section titles
    section_titles = [s.title for s in sections] if sections else []

    # Build YAML frontmatter
    yaml_lines = ["---"]

    if form:
        yaml_lines.append(f"filing_type: {form}")

    if accession_no:
        yaml_lines.append(f"accession_number: {accession_no}")

    if filing_date:
        yaml_lines.append(f"filing_date: {filing_date}")

    if company_name:
        yaml_lines.append(f"company: {company_name}")

    if ticker:
        yaml_lines.append(f"ticker: {ticker}")

    if section_titles:
        if len(section_titles) == 1:
            yaml_lines.append(f"section: {section_titles[0]}")
        else:
            yaml_lines.append("sections:")
            for title in section_titles:
                yaml_lines.append(f"  - {title}")

    yaml_lines.append("format: markdown")
    yaml_lines.append("---")

    return "\n".join(yaml_lines)


def _extract_xbrl_statements(
    filing: 'Filing',
    statements: Union[str, Sequence[str]],
    optimize_for_llm: bool,
    show_dimension: bool = True
) -> List[ExtractedSection]:
    """Extract XBRL financial statements."""
    sections = []

    try:
        # Get financials from filing
        financials = None
        if hasattr(filing, 'financials'):
            financials = filing.financials
        elif hasattr(filing, 'obj'):
            report = filing.obj()
            if hasattr(report, 'financials'):
                financials = report.financials

        if not financials:
            log.warning("Cannot extract XBRL statements: No financials available in filing. "
                       "This may be a non-XBRL filing or missing financial data.")
            return sections

        for stmt_name in _normalize_list(statements):
            # Get statement from financials
            stmt = _get_statement(financials, stmt_name)
            if not stmt:
                log.warning(f"Statement '{stmt_name}' not found in financials. "
                           f"Available types: IncomeStatement, BalanceSheet, CashFlowStatement, "
                           f"StatementOfEquity, ComprehensiveIncome, CoverPage")
                continue

            # Render using EdgarTools
            try:
                rendered = stmt.render(standard=True)
                df = rendered.to_dataframe()

                if df is None or df.empty:
                    log.debug(f"Empty dataframe for {stmt_name}")
                    continue

                # Filter out dimension rows if requested
                if not show_dimension and 'dimension' in df.columns:
                    # Remove rows that have dimension values (keep only consolidated/main rows)
                    # The dimension column contains booleans: False=no dimension, True=has dimension
                    df = df[df['dimension'] == False]

                # Determine which columns to keep
                drop_cols = {"concept"}  # Always drop concept
                if not show_dimension:
                    # User wants to hide dimension columns
                    drop_cols.update({"level", "abstract", "dimension"})

                columns = [c for c in df.columns if c not in drop_cols]
                if columns:
                    df_clean = df[columns].fillna("").astype(str)
                    # Use pandas to_markdown if available, else CSV-style
                    try:
                        markdown = df_clean.to_markdown(index=False)
                    except AttributeError:
                        # Fallback to simple table
                        from edgar.llm_helpers import create_markdown_table
                        headers = list(df_clean.columns)
                        rows = df_clean.values.tolist()
                        markdown = create_markdown_table(headers, rows)
                else:
                    # Shouldn't happen, but fallback
                    markdown = df.to_markdown(index=False)

                sections.append(ExtractedSection(
                    title=_STATEMENT_TITLES.get(stmt_name, stmt_name),
                    markdown=markdown,
                    source=f'xbrl:{stmt_name}',
                    is_xbrl=True
                ))

            except Exception as e:
                log.warning(f"Failed to render {stmt_name}: {e}")
                continue

    except Exception as e:
        log.warning(f"XBRL extraction failed: {e}")

    return sections


def _get_statement(financials: 'Financials', stmt_name: str) -> Optional['Statement']:
    """Get statement from financials object."""
    mapping = {
        "IncomeStatement": lambda: financials.income_statement(),
        "BalanceSheet": lambda: financials.balance_sheet(),
        "CashFlowStatement": lambda: financials.cashflow_statement(),
        "StatementOfEquity": lambda: financials.statement_of_equity(),
        "ComprehensiveIncome": lambda: financials.comprehensive_income(),
        "CoverPage": lambda: financials.cover(),
    }

    getter = mapping.get(stmt_name)
    if getter:
        try:
            return getter()
        except Exception as e:
            log.debug(f"Failed to get {stmt_name}: {e}")
            return None

    return None


def _extract_items(
    filing: 'Filing',
    items: Union[str, Sequence[str]],
    optimize_for_llm: bool
) -> List[ExtractedSection]:
    """Extract item sections using Document sections or fallback."""
    sections = []

    for item_name in _normalize_list(items):
        # Try Document sections first
        try:
            doc = filing.obj().document
            section = doc.sections.get_item(item_name)

            if section:
                # Extract tables from section
                tables = section.tables()

                if tables:
                    # Deduplicate tables (section.tables() may return duplicates)
                    seen_table_hashes = set()
                    unique_tables = []

                    for table in tables:
                        # Create signature from HTML to detect exact duplicates
                        table_hash = hash(table.html())
                        if table_hash not in seen_table_hashes:
                            seen_table_hashes.add(table_hash)
                            unique_tables.append(table)

                    if optimize_for_llm:
                        # Use LLM-optimized rendering
                        table_mds = [t.to_markdown_llm() for t in unique_tables]
                        markdown = "\n\n".join(table_mds)
                    else:
                        # Standard rendering
                        from edgar.richtools import rich_to_text
                        table_renders = [rich_to_text(t.render(500)) for t in unique_tables]
                        markdown = "\n\n".join(table_renders)

                    sections.append(ExtractedSection(
                        title=item_name,
                        markdown=markdown,
                        source=f'item:{item_name}',
                        is_xbrl=False
                    ))
                    continue
                else:
                    # No tables - try HTML processing for subsection detection
                    markdown = None

                    if optimize_for_llm and hasattr(section, '_section_extractor') and section._section_extractor:
                        # Try to get section HTML for subsection detection
                        try:
                            section_html = section._section_extractor.get_section_html(
                                section.name,
                                include_subsections=True
                            )
                            if section_html:
                                from edgar.llm_helpers import process_content
                                markdown = process_content(section_html, section_title=item_name)
                        except Exception as e:
                            log.debug(f"HTML processing failed for {item_name}: {e}")

                    # Fallback to plain text if HTML processing didn't work
                    if not markdown:
                        text = section.text()

                        # Apply LLM optimizations (filter page numbers, TOC, etc.)
                        if optimize_for_llm and text:
                            from edgar.llm_helpers import postprocess_text
                            text = postprocess_text(text)

                        markdown = text

                    if markdown:
                        sections.append(ExtractedSection(
                            title=item_name,
                            markdown=markdown,
                            source=f'item:{item_name}',
                            is_xbrl=False
                        ))
                        continue

        except Exception as e:
            log.debug(f"Document section extraction failed for {item_name}: {e}")

        # Fallback: Use regex boundary extraction
        try:
            html = filing.html()
            if not html:
                log.warning(f"Cannot extract {item_name}: No HTML content available in filing")
                continue

            from edgar.llm_extraction import extract_item_with_boundaries
            content = extract_item_with_boundaries(
                html,
                item_name,
                _ITEM_BOUNDARIES.get(item_name, ["Item", "Signature"])
            )
            if content:
                from edgar.llm_helpers import process_content
                markdown = process_content(content, section_title=item_name)
                if markdown:
                    sections.append(ExtractedSection(
                        title=item_name,
                        markdown=markdown,
                        source=f'item:{item_name}:fallback',
                        is_xbrl=False
                    ))
                else:
                    log.warning(f"Extraction of {item_name} returned empty content after processing")
            else:
                log.warning(f"Could not locate {item_name} boundaries in filing HTML")
        except Exception as e:
            log.warning(f"Failed to extract {item_name}: {e}")

    return sections


def _extract_notes(
    filing: 'Filing',
    optimize_for_llm: bool,
    track_filtered: bool = False
) -> Union[List[ExtractedSection], Tuple[List[ExtractedSection], Dict]]:
    """
    Extract financial statement notes.

    Strategy 1: Use filing.reports.get_by_category("Notes") for XBRL filings
    Strategy 2: Use Document sections as fallback

    Returns:
        If track_filtered=False: List of ExtractedSection objects
        If track_filtered=True: Tuple of (sections list, filtered_metadata dict)
    """
    sections = []
    all_filtered_data = {
        "xbrl_metadata_tables": 0,
        "duplicate_tables": 0,
        "filtered_text_blocks": 0,
        "details": []
    } if track_filtered else None

    # Strategy 1: XBRL FilingSummary notes (preferred)
    try:
        if hasattr(filing, 'reports'):
            notes_reports = filing.reports.get_by_category("Notes")

            if notes_reports and len(notes_reports) > 0:
                for note_report in notes_reports:
                    html_content = note_report.content

                    if not html_content:
                        continue

                    if optimize_for_llm:
                        # Apply LLM processing
                        from edgar.llm_helpers import process_content
                        if track_filtered:
                            markdown, filtered_data = process_content(
                                html_content,
                                section_title=note_report.short_name,
                                track_filtered=True
                            )
                            # Merge filtered data
                            if filtered_data:
                                for key in ["xbrl_metadata_tables", "duplicate_tables", "filtered_text_blocks"]:
                                    all_filtered_data[key] += filtered_data.get(key, 0)
                                all_filtered_data["details"].extend(filtered_data.get("details", []))
                        else:
                            markdown = process_content(
                                html_content,
                                section_title=note_report.short_name
                            )
                    else:
                        # Standard extraction
                        try:
                            df = note_report.to_dataframe()
                            if df is not None and not df.empty:
                                markdown = df.to_markdown(index=False)
                            else:
                                markdown = note_report.text()
                        except Exception:
                            markdown = note_report.text()

                    if markdown and markdown.strip():
                        sections.append(ExtractedSection(
                            title=note_report.short_name or note_report.long_name or "Note",
                            markdown=markdown,
                            source=f'notes:xbrl:{note_report.position}',
                            is_xbrl=True
                        ))

                # If we found notes, return them
                if sections:
                    log.debug(f"Extracted {len(sections)} notes via FilingSummary")
                    if track_filtered:
                        return (sections, all_filtered_data)
                    return sections

    except Exception as e:
        log.debug(f"XBRL notes extraction failed: {e}")

    # Strategy 2: Fallback to Document sections
    try:
        doc = filing.obj().document

        # Look for sections with "note" in title
        for section_name, section in doc.sections.items():
            title_lower = section.title.lower() if section.title else ""
            if any(keyword in title_lower for keyword in [
                'note', 'footnote', 'notes to'
            ]):
                tables = section.tables()

                if tables:
                    if optimize_for_llm:
                        table_mds = [t.to_markdown_llm() for t in tables]
                        markdown = "\n\n".join(table_mds)
                    else:
                        from edgar.richtools import rich_to_text
                        table_renders = [rich_to_text(t.render(500)) for t in tables]
                        markdown = "\n\n".join(table_renders)

                    sections.append(ExtractedSection(
                        title=section.title,
                        markdown=markdown,
                        source=f'notes:document:{section.name}',
                        is_xbrl=False
                    ))

        if sections:
            log.debug(f"Extracted {len(sections)} notes via Document sections")

    except Exception as e:
        log.debug(f"Document notes extraction failed: {e}")

    if track_filtered:
        return (sections, all_filtered_data)
    return sections
