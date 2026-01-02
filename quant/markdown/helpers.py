"""
LLM optimization helpers for table and content extraction.

Ported from tools/llm_extraction.py with EdgarTools integration.
These functions optimize HTML tables and content for LLM token efficiency.

Key features:
- Smart table cell preprocessing (currency/percent merging)
- Intelligent column deduplication
- Noise filtering (XBRL metadata, verbose labels)
- Duplicate detection
- Markdown generation optimized for LLM readability
"""

import re
from collections import deque
from typing import Optional, Tuple

from bs4 import BeautifulSoup

__all__ = [
    'preprocess_currency_cells',
    'preprocess_percent_cells',
    'is_width_grid_row',
    'is_xbrl_metadata_table',
    'html_to_json',
    'list_of_dicts_to_table',
    'create_markdown_table',
    'process_content',
    'clean_text',
    'is_noise_text',
    'postprocess_text',
]


# -----------------------------
# Text Utilities
# -----------------------------

def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def is_noise_text(text: str) -> bool:
    """Check if text is XBRL metadata or other noise."""
    text_lower = (text or "").lower()

    noise_patterns = [
        "reference 1:",
        "http://fasb.org",
        "http://www.xbrl.org",
        "no definition available",
        "namespace prefix:",
        "balance type:",
        "period type:",
        "axis:",
        "domain:",
        "documentation of verbose label",
        "documentation of label",
        "verbose label",
        "auth_ref",
    ]

    return any(p in text_lower for p in noise_patterns)


def should_skip_duplicate(text: str, recent: deque, window: int = 8) -> bool:
    """Check if text is a recent duplicate."""
    t = clean_text(text).lower()
    if not t:
        return True
    return t in list(recent)[-window:]


def is_page_number(text: str) -> bool:
    """Detect if text is a standalone page number (1-999)."""
    text_clean = clean_text(text)
    return bool(re.fullmatch(r'\d{1,3}', text_clean))


def is_header_footer_text(text: str) -> bool:
    """Detect common header/footer text that should be filtered."""
    text_lower = clean_text(text).lower()

    # Common header/footer patterns
    patterns = [
        r'^table of contents?$',
        r'^page \d+$',
        r'^\d+$',  # Standalone page numbers
        r'^continued$',
        r'^end of page$',
    ]

    return any(re.match(pattern, text_lower) for pattern in patterns)


def format_page_reference(text: str, next_text: str = None) -> Optional[str]:
    """
    Format page number references.

    If text is a bare page number followed by "Table of Contents",
    replace with "page XX" or remove entirely based on context.

    Returns:
        None if should be removed, formatted string otherwise
    """
    if is_page_number(text):
        # Check if next text is "Table of Contents"
        if next_text and "table of contents" in clean_text(next_text).lower():
            # Skip both the page number and TOC text
            return None
        # Format as "page XX"
        return f"page {clean_text(text)}"
    return text


def postprocess_text(text: str) -> str:
    """
    Post-process extracted text to filter page numbers and TOC references.

    Removes:
    - Bare page numbers followed by "Table of Contents"
    - Standalone "Table of Contents" text
    - Formats standalone page numbers as "page XX"

    Args:
        text: Text content to process

    Returns:
        Cleaned text with filtered page references
    """
    if not text:
        return text

    lines = text.split('\n')
    processed_lines = []
    skip_next = False

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        line_clean = line.strip()

        # Skip standalone "Table of Contents"
        if line_clean.lower() == 'table of contents':
            continue

        # Check for bare page number
        if is_page_number(line_clean):
            # Look ahead for "Table of Contents"
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.lower() == 'table of contents':
                    # Skip both this line and next
                    skip_next = True
                    continue
            # Standalone page number - format as "page XX"
            processed_lines.append(f"page {line_clean}")
        else:
            processed_lines.append(line)

    return '\n'.join(processed_lines)


# -----------------------------
# Subsection Detection
# -----------------------------

def is_subsection_heading(element) -> tuple[bool, str]:
    """
    Detect if an element is a subsection heading.

    Subsection headings are typically:
    - <span> tags with font-weight:700 (bold) or font-style:italic
    - Standalone in parent div (no siblings except whitespace)
    - Short text (< 80 chars) starting with capital letter
    - Parent div has top margin

    Returns:
        tuple[bool, str]: (is_subsection, heading_level)
        heading_level is "###" for bold or "####" for italic
    """
    # Must be a span or div tag
    if element.name not in ('span', 'div'):
        return False, ""

    # Get text
    text = element.get_text().strip()

    # Must be short (< 80 chars) and start with capital
    if not text or len(text) > 80:
        return False, ""

    if not text[0].isupper():
        return False, ""

    # Check for noise patterns
    if text.lower() in ('table of contents', 'page'):
        return False, ""

    # Exclude form headers and common SEC filing text
    text_lower = text.lower()

    # Exact match filters (these are complete section names to exclude)
    exact_noise = [
        'united states', 'securities and exchange commission', 'washington',
        'commission file number', 'form 10-k', 'form 10-q',
        'signatures', 'part i', 'part ii', 'part iii', 'part iv',
        'table of contents'
    ]
    if any(keyword == text_lower for keyword in exact_noise):
        return False, ""

    # Prefix match filters (exclude if text starts with these)
    prefix_noise = ['exhibit', 'index to']
    if any(text_lower.startswith(keyword) for keyword in prefix_noise):
        return False, ""

    # Exclude very short text (likely abbreviations or form codes)
    if len(text) < 4:
        return False, ""

    # For div elements, check if it contains a single span child
    if element.name == 'div':
        # Check if this div contains a single span as subsection
        spans = element.find_all('span', recursive=False)
        if len(spans) == 1:
            span = spans[0]
            span_text = span.get_text().strip()
            # Check if span text matches the div text (meaning it's the only content)
            if span_text == text:
                element = span  # Use the span for style checking
            else:
                return False, ""
        else:
            return False, ""

    # Must have siblings check (for span elements)
    parent = element.parent
    if parent:
        # Get all children, filtering out whitespace-only text nodes
        # Note: NavigableString has name=None, Tag elements have name set
        children = [
            child for child in parent.children
            if (hasattr(child, 'name') and child.name is not None) or (isinstance(child, str) and child.strip())
        ]

        # If more than one non-whitespace child, it's not standalone
        if len(children) > 1:
            return False, ""

        # Check parent style for top margin (indicates section break)
        parent_style = parent.get('style', '')
        if 'margin-top' not in parent_style:
            return False, ""

        # Exclude centered text (usually form headers)
        if 'text-align:center' in parent_style:
            return False, ""

    # Check style attributes for bold or italic
    style = element.get('style', '')

    # Determine heading level based on style
    is_bold = 'font-weight:700' in style or 'font-weight:bold' in style
    is_italic = 'font-style:italic' in style

    if is_bold:
        return True, "###"  # Level 1 subsection
    elif is_italic:
        return True, "####"  # Level 2 subsection

    return False, ""


# -----------------------------
# Table Preprocessing
# --------------------------------------

def is_xbrl_metadata_table(soup_table) -> bool:
    """Detect XBRL metadata tables (should be skipped)."""
    text = soup_table.get_text().lower()

    if "namespace prefix" in text or "xbrli:string" in text:
        return True

    if "us-gaap_" in text:
        # Check if it's actual financial data (has $ and years)
        if "$" in text and re.search(r"20\d{2}", text):
            return False
        return True

    return False


# -----------------------------
# Table Title Extraction
# -----------------------------

def _is_valid_title(text: str) -> bool:
    """
    Validate if text is a reasonable table title.

    Args:
        text: Candidate title string

    Returns:
        True if text is a valid title
    """
    if not text:
        return False

    text = text.strip()

    # Length check (flexible, not magic numbers)
    if len(text) < 2 or len(text) > 200:
        return False

    # Must contain at least one letter
    if not any(c.isalpha() for c in text):
        return False

    # Filter noise patterns
    noise_patterns = [
        r'^\d+$',  # Just numbers
        r'^col_?\d+$',  # Placeholder columns
        r'^\$?[\d,]+\.?\d*$',  # Just a number/currency
        r'^[\s\-_]+$',  # Just whitespace/separators
    ]

    for pattern in noise_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return False

    return True


def _extract_from_caption_tag(table_element) -> Optional[str]:
    """Extract title from HTML <caption> tag (HTML standard)."""
    caption = table_element.find('caption')
    if caption:
        text = caption.get_text(strip=True)
        if _is_valid_title(text):
            return text
    return None


def _extract_from_spanning_row(table_element, max_rows: int = 3) -> Optional[str]:
    """
    Extract title from spanning row in first N rows.

    Improvements over original:
    - Checks first N rows (not just first)
    - More flexible colspan detection
    - Better validation
    - Non-destructive

    Args:
        table_element: BeautifulSoup table element
        max_rows: Maximum number of rows to check

    Returns:
        Title string if found, None otherwise
    """
    rows = table_element.find_all('tr')

    for row_idx in range(min(max_rows, len(rows))):
        row = rows[row_idx]
        cells = row.find_all(['th', 'td'])

        if not cells:
            continue

        # Case 1: Single cell with large colspan
        if len(cells) == 1:
            cell = cells[0]
            colspan = int(cell.get('colspan', 1))
            text = cell.get_text(strip=True)

            # If colspan is large (3+) and text is valid
            if colspan >= 3 and _is_valid_title(text):
                return text

        # Case 2: Multiple cells with identical text (merged visually)
        texts = [c.get_text(strip=True) for c in cells]
        unique_texts = set(t for t in texts if t)

        if len(unique_texts) == 1:
            text = list(unique_texts)[0]
            if _is_valid_title(text):
                return text

    return None


def _infer_from_content(table_element) -> Optional[str]:
    """
    Infer table title from content analysis.

    Strategies:
    - Financial statement detection (Revenue + Net Income = Income Statement)
    - Date-based patterns ("Year Ended", "Quarter Ended")
    - Segment/category patterns

    Args:
        table_element: BeautifulSoup table element

    Returns:
        Inferred title if pattern matched, None otherwise
    """
    rows = table_element.find_all('tr')
    if not rows:
        return None

    # Get text from first few rows
    all_text = ' '.join([r.get_text(' ', strip=True).lower() for r in rows[:5]])

    # Financial statement patterns
    financial_patterns = {
        'Income Statement': ['revenue', 'net income'],
        'Statement of Operations': ['revenue', 'operating income'],
        'Balance Sheet': ['assets', 'liabilities', 'equity'],
        'Cash Flow Statement': ['cash flow', 'operating activities'],
        'Statement of Cash Flows': ['cash provided', 'operating activities'],
    }

    for statement_name, keywords in financial_patterns.items():
        if all(kw in all_text for kw in keywords):
            return statement_name

    # Date-based patterns
    date_pattern = r'(year|years|quarter|quarters|month|months|period)s?\s+ended\s+\w+'
    match = re.search(date_pattern, all_text, re.IGNORECASE)
    if match:
        return match.group(0).title()

    # Segment/geographic patterns
    if 'segment' in all_text and 'revenue' in all_text:
        return 'Segment Information'
    if 'geographic' in all_text or 'region' in all_text:
        return 'Geographic Information'

    return None


def extract_table_title(
    table_element,
    section_title: Optional[str] = None,
    context: Optional[dict] = None
) -> Tuple[Optional[str], str]:
    """
    Extract table title from multiple sources with priority hierarchy.

    This replaces the brittle derived_title logic with a robust multi-source approach.

    Priority order:
    1. HTML <caption> tag (HTML standard)
    2. HTML summary attribute
    3. Preceding heading from context
    4. Spanning row (improved - checks first 3 rows)
    5. Inferred from content
    6. Section title from context

    Args:
        table_element: BeautifulSoup table element
        section_title: Optional section title
        context: Optional context dict with 'preceding_heading', etc.

    Returns:
        Tuple of (title, source) where source indicates where title came from
        For debugging and quality tracking
    """
    context = context or {}

    # Priority 1: HTML <caption> tag (HTML standard)
    caption_title = _extract_from_caption_tag(table_element)
    if caption_title:
        return caption_title, 'caption_tag'

    # Priority 2: HTML summary attribute
    summary = table_element.get('summary')
    if summary and _is_valid_title(summary):
        return summary, 'summary_attr'

    # Priority 3: Preceding heading from context
    if 'preceding_heading' in context:
        heading = context['preceding_heading']
        if _is_valid_title(heading):
            return heading, 'preceding_heading'

    # Priority 4: Spanning row (improved - checks first 3 rows)
    spanning_title = _extract_from_spanning_row(table_element, max_rows=3)
    if spanning_title:
        return spanning_title, 'spanning_row'

    # Priority 5: Infer from table content
    inferred_title = _infer_from_content(table_element)
    if inferred_title:
        return inferred_title, 'inferred'

    # Priority 6: Section title from context
    if section_title and _is_valid_title(section_title) and section_title != "Table":
        return section_title, 'section_context'

    # No title found
    return None, 'none'


def is_width_grid_row(tr) -> bool:
    """Detect layout rows (empty cells with width styling)."""
    tds = tr.find_all(["td", "th"])
    if not tds:
        return False
    if tr.get_text(strip=True):  # Has text content
        return False

    width_cells = 0
    for td in tds:
        style = (td.get("style") or "").lower()
        if "width" in style:
            width_cells += 1

    return width_cells >= 6 and (width_cells / max(1, len(tds))) >= 0.6


def preprocess_currency_cells(table_soup):
    """
    Merge standalone currency symbols with adjacent values.

    Example: [$] [100] -> [$100] with colspan adjustment

    Note: Modifies the BeautifulSoup table in-place.
    Safe for SEC financial tables where all rows have consistent structure.
    """
    rows = table_soup.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        i = 0
        while i < len(cells):
            cell = cells[i]
            txt = clean_text(cell.get_text())
            # If standalone $ symbol and has next cell
            if txt in ["$"] and i + 1 < len(cells):
                next_cell = cells[i + 1]
                # Merge: prepend $ to next cell content
                next_cell.string = txt + clean_text(next_cell.get_text())
                # Adjust colspan (next cell now spans both positions)
                next_cell["colspan"] = str(int(next_cell.get("colspan", 1)) + 1)
                # Remove the $ cell
                cell.decompose()
            i += 1


def preprocess_percent_cells(table_soup):
    """
    Merge standalone percent symbols with adjacent values.

    Example: [5] [%] -> [5%] with colspan adjustment

    Note: Scans right-to-left to merge % with preceding cell.
    """
    rows = table_soup.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        i = len(cells) - 1
        while i > 0:
            cell = cells[i]
            txt = clean_text(cell.get_text())
            # If standalone % symbol and has previous cell
            if txt in ["%", "%)", "pts"]:
                prev_cell = cells[i - 1]
                prev_txt = clean_text(prev_cell.get_text())
                if prev_txt:
                    # Merge: append % to previous cell
                    prev_cell.string = prev_txt + txt
                    # Adjust colspan
                    prev_cell["colspan"] = str(
                        int(prev_cell.get("colspan", 1))
                        + int(cell.get("colspan", 1))
                    )
                    # Remove the % cell
                    cell.decompose()
            i -= 1


def build_row_values(cells, max_cols):
    """Build row value list with colspan expansion."""
    row_values = []
    for cell in cells:
        try:
            colspan = int(cell.get("colspan", 1))
        except (TypeError, ValueError):
            colspan = 1
        txt = clean_text(cell.get_text(" ", strip=True)).replace("|", r"\|")
        row_values.append(txt)
        # Repeat value for colspan
        for _ in range(colspan - 1):
            row_values.append(txt)

    # Pad to max_cols
    if len(row_values) < max_cols:
        row_values.extend([""] * (max_cols - len(row_values)))
    return row_values[:max_cols]


# -----------------------------
# HTML to JSON Conversion
# -----------------------------

def html_to_json(table_soup):
    """
    Convert HTML table to JSON intermediate format.

    Returns:
        (text_blocks, records, derived_title) tuple where:
        - text_blocks: List of long-form text extracted from table
        - records: List of dicts with 'label' and 'col_N' keys
        - derived_title: Extracted table title if found

    This intermediate format enables intelligent column deduplication
    and header merging before markdown generation.
    """
    table_soup_copy = BeautifulSoup(str(table_soup), "html.parser")
    preprocess_currency_cells(table_soup_copy)
    preprocess_percent_cells(table_soup_copy)

    rows = table_soup_copy.find_all("tr")
    if not rows:
        return None, [], None

    # Filter layout rows
    rows = [r for r in rows if not is_width_grid_row(r)]
    if not rows:
        return None, [], None

    # Calculate max columns
    max_cols = 0
    widths = []
    for row in rows:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        width = sum(int(cell.get("colspan", 1)) for cell in cells)
        widths.append(width)
        max_cols = max(max_cols, width)

    if max_cols == 0:
        return None, [], None

    # Use 90th percentile to handle outliers
    if len(widths) >= 5:
        sorted_widths = sorted(widths)
        p90 = sorted_widths[int(0.9 * (len(sorted_widths) - 1))]
        if p90 >= 2 and max_cols > p90 * 2:
            max_cols = p90

    matrix = []
    row_flags = []
    output_blocks = []

    # Build matrix
    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        row_has_th = any(cell.name == "th" for cell in cells)
        row_text = " ".join([c.get_text(" ", strip=True) for c in cells])

        # Extract long text as separate blocks
        if len(row_text) > 300:
            if not is_noise_text(row_text):
                output_blocks.append(
                    {"type": "text", "content": clean_text(row_text)}
                )
            continue

        row_vals = build_row_values(cells, max_cols)
        if not any(v.strip() for v in row_vals):
            continue
        matrix.append(row_vals)
        row_flags.append(row_has_th)

    if not matrix:
        return output_blocks, [], None

    # Skip sparse tables (>50 cols with <5% filled)
    if max_cols >= 50:
        total_cells = len(matrix) * max_cols
        filled = sum(1 for row in matrix for val in row if val.strip())
        if total_cells and (filled / total_cells) < 0.05:
            return output_blocks, [], None

    # Extract derived title (first row with single unique value spanning all columns)
    derived_title = None
    if len(matrix) > 1:
        first_row = matrix[0]
        unique_vals = set(v for v in first_row if v.strip())
        if len(unique_vals) == 1:
            title_candidate = list(unique_vals)[0]
            if 3 < len(title_candidate) < 150:
                derived_title = title_candidate
                matrix.pop(0)
                row_flags.pop(0)

    # Detect label column (column with most text content)
    def is_numericish(s):
        """Check if string is primarily numeric data (pure numbers, currency, percentages)."""
        s_stripped = s.strip()
        if not s_stripped:
            return False

        # Remove common formatting
        s_clean = s_stripped.replace('$', '').replace(',', '').replace('%', '').replace('(', '').replace(')', '').strip()

        # Check if it's a pure number (possibly with decimal)
        try:
            float(s_clean)
            return True
        except ValueError:
            pass

        # Check if it's mostly digits (more than 50% digits)
        if s_clean:
            digit_ratio = sum(c.isdigit() for c in s_clean) / len(s_clean)
            if digit_ratio > 0.5:
                return True

        return False

    def is_labelish(s):
        """Check if string looks like a row label rather than data.

        Recognizes:
        - Pure text: "Revenue", "Assets"
        - Text with numbers: "Q1", "Item 1", "Note 5"
        - Excludes: pure numbers, currency values, percentages
        """
        s_stripped = s.strip()
        if not s_stripped:
            return False

        # Must contain at least one letter
        if not re.search(r'[A-Za-z]', s_stripped):
            return False

        # Exclude if it's primarily numeric
        if is_numericish(s_stripped):
            return False

        return True

    # Calculate label scores only from data rows (not header rows with th tags)
    # NOTE: This heuristic-based label detection could be simplified if
    # TableNode.has_row_headers metadata were available at this level.
    # Current approach: count "labelish" values per column and prefer leftmost.
    label_scores = []
    for c in range(max_cols):
        # Only count labelish values in rows without th tags (data rows)
        score = sum(
            1 for i, row in enumerate(matrix)
            if not row_flags[i] and is_labelish(row[c])
        )
        label_scores.append(score)

    # If no clear label column from data rows, fall back to all rows
    if max(label_scores) == 0:
        for c in range(max_cols):
            score = sum(1 for r in matrix if is_labelish(r[c]))
            label_scores[c] = score

    # Select label column: highest score, prefer leftmost column on ties
    # (Most tables have row headers in the first column)
    label_col = max(range(max_cols), key=lambda c: (label_scores[c], -c))

    year_re = re.compile(r"\b(20\d{2}|19\d{2})\b")

    # Convert matrix to records with intelligent header detection
    records = []
    for row_index, row in enumerate(matrix):
        row_has_th = row_flags[row_index]
        record = {}
        is_header = row_has_th

        # Detect headers by content (year patterns, date headings)
        for c in range(max_cols):
            if c == label_col:
                continue
            if row[c] == row[label_col]:
                continue
            if year_re.search(row[c]):
                is_header = True
                break

        # Empty label + numeric values might still be header
        label_text = (row[label_col] or "").lower()
        if not is_header and not label_text:
            data_values = [
                row[c]
                for c in range(max_cols)
                if c != label_col and row[c].strip()
            ]
            if data_values and len(set(data_values)) == 1:
                is_header = True

        # Build record
        if is_header:
            record["label"] = ""
        else:
            record["label"] = row[label_col]

        for c in range(max_cols):
            if c != label_col:
                record[f"col_{c}"] = row[c]

        records.append(record)

    return output_blocks, records, derived_title


# -----------------------------
# JSON to Markdown Conversion
# -----------------------------

def _normalize_table_value(value: str) -> str:
    """Normalize value for comparison."""
    return clean_text(str(value)).lower()


def _is_total_row(row_dict, label_key):
    """
    Detect if a row is a total row based on its label.

    Args:
        row_dict: Dictionary representing the row
        label_key: Key for the label column

    Returns:
        bool: True if this appears to be a total row
    """
    if not label_key or label_key not in row_dict:
        return False

    label_text = str(row_dict.get(label_key, "")).lower().strip()

    if not label_text:
        return False

    # Check for total keywords
    total_keywords = ['total', 'sum', 'subtotal', 'grand total', 'net total']

    # Check for exact match or starts with total keyword
    for keyword in total_keywords:
        if label_text == keyword or label_text.startswith(keyword + ' '):
            return True

    return False


def create_markdown_table(headers, rows, alignments=None):
    """
    Create markdown table from headers and rows with optional alignment.

    Args:
        headers: List of header strings
        rows: List of row data (lists)
        alignments: Optional list of 'left', 'right', 'center' for each column
                   If None, all columns are left-aligned

    Returns:
        str: Markdown formatted table
    """
    if not headers or not rows:
        return ""

    # Build header row
    md = f"| {' | '.join(map(str, headers))} |\n"

    # Build separator row with alignment
    if alignments:
        separators = []
        for align in alignments:
            if align == 'right':
                separators.append('---:')
            elif align == 'center':
                separators.append(':---:')
            else:  # left or None
                separators.append('---')
        md += f"| {' | '.join(separators)} |\n"
    else:
        md += f"| {' | '.join(['---'] * len(headers))} |\n"

    # Build data rows
    for row in rows:
        padded_row = list(row) + [""] * (len(headers) - len(row))
        cleaned_row = [str(x) if x is not None else "" for x in padded_row]
        md += f"| {' | '.join(cleaned_row)} |\n"
    return md


def list_of_dicts_to_table(data_list):
    """
    Convert list of dicts to markdown table with intelligent column handling.

    Features:
    - Deduplicates columns with identical signatures
    - Filters placeholder columns (col_0, col_1, etc.)
    - Merges multi-row headers intelligently
    - Removes blank value columns
    - Auto-detects numeric columns for right-alignment
    """
    if not data_list:
        return ""

    all_keys = set().union(*(d.keys() for d in data_list))

    def natural_keys(text):
        return [
            int(c) if c.isdigit() else c.lower()
            for c in re.split(r"(\d+)", text)
        ]

    def is_numeric_column(values):
        """Detect if a column contains primarily numeric data."""
        if not values:
            return False

        numeric_count = 0
        total_count = 0

        for val in values:
            val_str = str(val).strip()
            if not val_str or val_str == '-':
                continue

            total_count += 1
            # Check for numeric patterns: numbers, currency, percentages
            # Remove common formatting: $, commas, parentheses, %, and scale indicators (M, K, B, T)
            cleaned = re.sub(r'[\$,\(\)%]', '', val_str).strip()
            # Remove scale indicators (Millions, Thousands, Billions, Trillions)
            cleaned = re.sub(r'[MKBT]$', '', cleaned, flags=re.IGNORECASE).strip()

            # Check if it's a number (possibly with minus sign or decimal)
            if re.match(r'^-?\d+\.?\d*$', cleaned):
                numeric_count += 1

        # Consider numeric if >70% of non-empty values are numeric
        if total_count == 0:
            return False
        return (numeric_count / total_count) > 0.7

    sorted_keys = sorted(list(all_keys), key=natural_keys)
    label_key = next(
        (k for k in sorted_keys if k.lower() in ["label", "metric", "name"]), None
    )

    # Separate header rows from data rows
    header_rows = []
    data_rows = []

    if label_key:
        for item in data_list:
            if not str(item.get(label_key, "")).strip():
                header_rows.append(item)
            else:
                data_rows.append(item)
    else:
        data_rows = data_list

    # Build headers
    if header_rows:
        # Group columns by header signature
        column_groups = {}
        value_keys = [k for k in sorted_keys if k != label_key]

        for key in value_keys:
            signature = tuple(str(row.get(key, "")).strip() for row in header_rows)
            if signature not in column_groups:
                column_groups[signature] = []
            column_groups[signature].append(key)

        final_headers = [label_key if label_key else "Row"]
        final_keys = [label_key] if label_key else []
        processed_signatures = set()

        for key in value_keys:
            signature = tuple(str(row.get(key, "")).strip() for row in header_rows)
            if signature in processed_signatures:
                continue
            processed_signatures.add(signature)

            candidate_keys = column_groups[signature]
            # Choose key with most non-empty data
            best_key = max(
                candidate_keys,
                key=lambda k: sum(
                    1
                    for row in data_rows
                    if str(row.get(k, "")).strip() not in ["", "-"]
                ),
            )

            # Skip empty columns
            if sum(
                1 for row in data_rows if str(row.get(best_key, "")).strip()
            ) == 0:
                continue

            # Build header string from signature
            header_str = " - ".join([p for p in signature if p]) or best_key
            final_headers.append(header_str)
            final_keys.append(best_key)
    else:
        # No multi-row headers
        final_headers = sorted_keys
        final_keys = sorted_keys
        if label_key and label_key in final_headers:
            final_headers.insert(0, final_headers.pop(final_headers.index(label_key)))
            final_keys.insert(0, final_keys.pop(final_keys.index(label_key)))

    # Filter placeholder headers and duplicate columns
    if data_rows and final_headers and final_keys:
        def is_placeholder_header(header):
            header_text = clean_text(str(header)).lower()
            if not header_text:
                return True
            if re.fullmatch(r"col_?\d+", header_text):
                return True
            if header_text == "row":
                return True
            return False

        def is_blank_value(value):
            if not value:
                return True
            return bool(re.fullmatch(r"-+", value))

        keep_headers = []
        keep_keys = []
        seen = set()
        locked_index = 0

        for idx, (header, key) in enumerate(zip(final_headers, final_keys)):
            # Always keep first column (labels)
            if idx == locked_index:
                keep_headers.append(header)
                keep_keys.append(key)
                continue

            # Get column values
            values = tuple(
                _normalize_table_value(item.get(key, "")) for item in data_rows
            )

            # Skip all-blank columns
            if all(is_blank_value(value) for value in values):
                continue

            # Skip columns that duplicate the label column
            if idx > locked_index and label_key:
                label_values = tuple(
                    _normalize_table_value(item.get(label_key, "")) for item in data_rows
                )
                if values == label_values:
                    # This column duplicates the label column
                    continue

            # Build signature (header + values)
            header_norm = _normalize_table_value(header)
            signature = (
                "" if is_placeholder_header(header) else header_norm,
                values,
            )

            # Skip duplicates
            if signature in seen:
                continue
            seen.add(signature)

            keep_headers.append(header)
            keep_keys.append(key)

        final_headers = keep_headers
        final_keys = keep_keys

    # Build table rows with total row highlighting
    table_rows = []
    for item in data_rows:
        # Check if this is a total row
        is_total = _is_total_row(item, label_key)

        # Build row, bolding values if it's a total row
        if is_total:
            row = [f"**{item.get(k, '')}**" if item.get(k, '') else "" for k in final_keys]
        else:
            row = [item.get(k, "") for k in final_keys]
        table_rows.append(row)

    # Detect numeric columns for right-alignment
    alignments = []
    for idx, key in enumerate(final_keys):
        # First column (labels) should be left-aligned
        if idx == 0 and label_key and key == label_key:
            alignments.append('left')
        else:
            # Extract column values (without bold formatting)
            column_values = [str(item.get(key, "")).replace("**", "") for item in data_rows]
            # Check if numeric
            if is_numeric_column(column_values):
                alignments.append('right')
            else:
                alignments.append('left')

    return create_markdown_table(final_headers, table_rows, alignments)


# -----------------------------
# Content Processing
# -----------------------------

def process_content(content, section_title=None, track_filtered=False):
    """
    Process HTML content to LLM-optimized markdown.

    Features:
    - Extracts tables with intelligent preprocessing
    - Filters XBRL metadata tables
    - Deduplicates tables via signature matching
    - Extracts headings and text
    - Optimizes for token efficiency

    Args:
        content: HTML content to process
        section_title: Title of the section
        track_filtered: If True, return (markdown, filtered_metadata) tuple

    Returns:
        str if track_filtered=False, else (str, dict) with filtered metadata
    """
    if not content:
        return ("", {}) if track_filtered else ""

    raw_str = str(content)
    is_html = bool(re.search(r"<(table|div|p|h[1-6])", raw_str, re.IGNORECASE))

    if not is_html:
        result = f"\n{raw_str.strip()}\n"
        return (result, {}) if track_filtered else result

    soup = BeautifulSoup(raw_str, "html.parser")
    for tag in soup(["script", "style", "head", "meta"]):
        tag.decompose()

    output_parts = []
    processed_tables = set()
    table_signatures = set()
    recent_text = deque(maxlen=32)
    normalized_section = clean_text(section_title or "").lower()
    table_counter = 0

    # Track filtered items
    filtered_metadata = {
        "xbrl_metadata_tables": 0,
        "duplicate_tables": 0,
        "filtered_text_blocks": 0,
        "details": []
    } if track_filtered else None

    elements = soup.find_all(
        ["p", "div", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6"]
    )

    skip_next = False  # Flag to skip elements (e.g., TOC after page number)

    for idx, element in enumerate(elements):
        # Skip if marked by previous iteration
        if skip_next:
            skip_next = False
            continue
        # Skip if already processed as part of another table
        if element.find_parent("table") in processed_tables:
            continue

        # Process tables
        if element.name == "table":
            # Skip nested tables
            if element.find("table"):
                continue
            # Skip XBRL metadata
            if is_xbrl_metadata_table(element):
                if filtered_metadata is not None:
                    filtered_metadata["xbrl_metadata_tables"] += 1
                    table_text = element.get_text()[:100]
                    filtered_metadata["details"].append({
                        "type": "xbrl_metadata_table",
                        "reason": "Contains XBRL namespace/type metadata (non-financial content)",
                        "preview": clean_text(table_text)
                    })
                continue

            # Extract table title using improved multi-source extraction
            table_title, title_source = extract_table_title(
                element,
                section_title=section_title,
                context={}  # Could be enhanced with preceding_heading in future
            )

            # Convert to JSON intermediate format (for backward compat, still returns derived_title)
            text_blocks, records, derived_title = html_to_json(element)

            # Add text blocks
            for block in text_blocks:
                if block["type"] == "text" and not is_noise_text(block["content"]):
                    output_parts.append(block["content"])

            # Process table records
            if records:
                # Generate signature for deduplication
                def _table_signature(records, title, max_rows=8):
                    if not records:
                        return None
                    keys = sorted({key for record in records for key in record.keys()})
                    if not keys:
                        return None
                    row_sig = []
                    for record in records[:max_rows]:
                        row_sig.append(tuple(_normalize_table_value(record.get(key, "")) for key in keys))
                    title_sig = _normalize_table_value(title or "")
                    return (title_sig, tuple(keys), tuple(row_sig), len(records))

                signature = _table_signature(records, table_title)

                # Skip duplicate tables
                if signature and signature in table_signatures:
                    if filtered_metadata is not None:
                        filtered_metadata["duplicate_tables"] += 1
                        filtered_metadata["details"].append({
                            "type": "duplicate_table",
                            "reason": "Duplicate of earlier table (identical structure and data)",
                            "title": table_title or "Untitled"
                        })
                    processed_tables.add(element)
                    continue
                if signature:
                    table_signatures.add(signature)

                # Convert to markdown
                table_counter += 1
                md_table = list_of_dicts_to_table(records)
                if md_table:
                    # Generate header with improved title
                    if table_title:
                        header_str = f"#### Table: {table_title}"
                    else:
                        header_str = f"#### Table {table_counter}: {section_title or 'Data'}"

                    output_parts.append(f"\n{header_str}\n{md_table}\n")

            processed_tables.add(element)
            continue

        # Process headings
        if element.name.startswith("h"):
            txt = clean_text(element.get_text())
            if txt and not is_noise_text(txt):
                output_parts.append(f"\n### {txt}\n")
            continue

        # Check for subsection headings (bold/italic spans in standalone divs)
        is_subsection, heading_level = is_subsection_heading(element)
        if is_subsection:
            txt = clean_text(element.get_text())
            if txt and not is_noise_text(txt):
                output_parts.append(f"\n{heading_level} {txt}\n")
            continue

        # Process lists
        if element.name in ["ul", "ol"]:
            lines = [
                f"- {clean_text(li.get_text())}"
                for li in element.find_all("li")
                if clean_text(li.get_text())
            ]
            if lines:
                output_parts.append("\n".join(lines))
            continue

        # Process paragraphs and divs
        if element.find("table"):  # Skip containers with tables
            continue
        text = clean_text(element.get_text())
        if len(text) <= 5 or is_noise_text(text):
            continue
        if normalized_section and text.lower() == normalized_section:
            continue

        # Filter header/footer text (Table of Contents, etc.)
        if is_header_footer_text(text):
            continue

        # Check for page number + TOC combination
        if is_page_number(text):
            # Look ahead to see if next element is "Table of Contents"
            next_text = None
            if idx + 1 < len(elements):
                next_element = elements[idx + 1]
                next_text = clean_text(next_element.get_text())
                if "table of contents" in next_text.lower():
                    # Skip both this page number and the next TOC text
                    skip_next = True
                    continue
            # Standalone page number without TOC - format as "page XX"
            text = f"page {text}"

        if should_skip_duplicate(text, recent_text):
            continue

        output_parts.append(text)
        recent_text.append(text.lower())

    result = "\n\n".join(output_parts)

    if track_filtered:
        return (result, filtered_metadata)
    return result
