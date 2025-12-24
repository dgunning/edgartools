"""
Demonstration: Improved Title Extraction vs Current Method
"""
import re
from typing import Optional, Tuple
from bs4 import BeautifulSoup

print("="*70)
print("COMPARISON: Current vs Proposed Title Extraction")
print("="*70)

# Current implementation (simplified)
def current_method(html: str) -> Optional[str]:
    """Current derived_title extraction (first row spanning only)."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    if not table:
        return None

    rows = table.find_all('tr')
    if len(rows) < 2:
        return None

    # Only check FIRST row
    first_row = rows[0]
    cells = first_row.find_all(['th', 'td'])

    # Build row values
    row_vals = []
    for cell in cells:
        text = cell.get_text(strip=True)
        colspan = int(cell.get('colspan', 1))
        row_vals.extend([text] * colspan)

    # Check if single unique value
    unique_vals = set(v for v in row_vals if v.strip())
    if len(unique_vals) == 1:
        title_candidate = list(unique_vals)[0]
        # Magic numbers: 3 and 150
        if 3 < len(title_candidate) < 150:
            return title_candidate

    return None


# Proposed implementation
def proposed_method(html: str, context: dict = None) -> Tuple[Optional[str], str]:
    """
    Proposed multi-source title extraction.

    Returns: (title, source)
    """
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    if not table:
        return None, 'none'

    context = context or {}

    # Priority 1: <caption> tag
    caption = table.find('caption')
    if caption:
        text = caption.get_text(strip=True)
        if _is_valid_title(text):
            return text, 'caption_tag'

    # Priority 2: summary attribute
    summary = table.get('summary')
    if summary and _is_valid_title(summary):
        return summary, 'summary_attr'

    # Priority 3: Preceding heading from context
    if 'preceding_heading' in context:
        heading = context['preceding_heading']
        if _is_valid_title(heading):
            return heading, 'preceding_heading'

    # Priority 4: Improved spanning row (checks first 3 rows)
    spanning_title = _extract_spanning_row(table, max_rows=3)
    if spanning_title:
        return spanning_title, 'spanning_row'

    # Priority 5: Infer from content
    inferred = _infer_from_headers(table)
    if inferred:
        return inferred, 'inferred'

    # Priority 6: Section context
    if 'section_title' in context:
        section = context['section_title']
        if _is_valid_title(section) and section != "Table":
            return section, 'section_context'

    return None, 'none'


def _extract_spanning_row(table, max_rows: int = 3) -> Optional[str]:
    """Check first N rows for spanning title."""
    rows = table.find_all('tr')

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

            if colspan >= 3 and _is_valid_title(text):
                return text

        # Case 2: Multiple cells with identical text
        texts = [c.get_text(strip=True) for c in cells]
        unique_texts = set(t for t in texts if t)

        if len(unique_texts) == 1:
            text = list(unique_texts)[0]
            if _is_valid_title(text):
                return text

    return None


def _infer_from_headers(table) -> Optional[str]:
    """Infer title from table headers and content."""
    rows = table.find_all('tr')
    if not rows:
        return None

    # Get all text
    all_text = ' '.join([r.get_text(' ', strip=True).lower() for r in rows[:5]])

    # Financial statement patterns
    if 'revenue' in all_text and ('net income' in all_text or 'operating income' in all_text):
        return 'Income Statement'

    if 'assets' in all_text and 'liabilities' in all_text and 'equity' in all_text:
        return 'Balance Sheet'

    if 'cash flow' in all_text and 'operating activities' in all_text:
        return 'Cash Flow Statement'

    # Date patterns
    date_pattern = r'(year|quarter|month)s?\s+ended\s+\w+'
    match = re.search(date_pattern, all_text, re.IGNORECASE)
    if match:
        return match.group(0).title()

    return None


def _is_valid_title(text: str) -> bool:
    """Validate if text is a reasonable title."""
    if not text:
        return False

    text = text.strip()

    if len(text) < 2 or len(text) > 200:
        return False

    if not any(c.isalpha() for c in text):
        return False

    # Filter noise
    if re.match(r'^\d+$', text):  # Just numbers
        return False
    if re.match(r'^col_?\d+$', text, re.IGNORECASE):  # Placeholder
        return False

    return True


# ============================================================================
# TEST CASES
# ============================================================================

test_cases = [
    # Case 1: Table with <caption> tag
    {
        'name': 'HTML <caption> tag',
        'html': '''
        <table>
            <caption>Consolidated Balance Sheet</caption>
            <tr><th>Assets</th><th>2024</th><th>2023</th></tr>
            <tr><td>Cash</td><td>$100M</td><td>$90M</td></tr>
        </table>
        ''',
        'context': {}
    },

    # Case 2: Spanning first row (current method works)
    {
        'name': 'Spanning first row',
        'html': '''
        <table>
            <tr><th colspan="4">Year Ended December 31</th></tr>
            <tr><th></th><th>2024</th><th>2023</th><th>2022</th></tr>
            <tr><td>Revenue</td><td>$100M</td><td>$90M</td><td>$80M</td></tr>
        </table>
        ''',
        'context': {}
    },

    # Case 3: Title in SECOND row (current fails)
    {
        'name': 'Title in second row',
        'html': '''
        <table>
            <tr><td colspan="3"></td></tr>
            <tr><th colspan="3">Quarterly Revenue Summary</th></tr>
            <tr><th>Quarter</th><th>2024</th><th>2023</th></tr>
            <tr><td>Q1</td><td>$100M</td><td>$90M</td></tr>
        </table>
        ''',
        'context': {}
    },

    # Case 4: Inferred from content (current fails)
    {
        'name': 'Inferred from headers',
        'html': '''
        <table>
            <tr><th></th><th>2024</th><th>2023</th></tr>
            <tr><td>Total Assets</td><td>$500M</td><td>$450M</td></tr>
            <tr><td>Total Liabilities</td><td>$300M</td><td>$270M</td></tr>
            <tr><td>Stockholders' Equity</td><td>$200M</td><td>$180M</td></tr>
        </table>
        ''',
        'context': {}
    },

    # Case 5: Preceding heading in context (current fails)
    {
        'name': 'Preceding heading',
        'html': '''
        <table>
            <tr><th>Segment</th><th>Revenue</th></tr>
            <tr><td>North America</td><td>$100M</td></tr>
            <tr><td>Europe</td><td>$50M</td></tr>
        </table>
        ''',
        'context': {'preceding_heading': 'Revenue by Geographic Region'}
    },

    # Case 6: No title available (both fail gracefully)
    {
        'name': 'No title',
        'html': '''
        <table>
            <tr><th>A</th><th>B</th></tr>
            <tr><td>1</td><td>2</td></tr>
        </table>
        ''',
        'context': {}
    },

    # Case 7: Summary attribute (current fails)
    {
        'name': 'Summary attribute',
        'html': '''
        <table summary="Stock Compensation Expense">
            <tr><th>Type</th><th>2024</th><th>2023</th></tr>
            <tr><td>RSUs</td><td>$50M</td><td>$45M</td></tr>
        </table>
        ''',
        'context': {}
    },
]

# Run tests
print("\nTEST RESULTS:")
print("="*70)

for idx, test in enumerate(test_cases, 1):
    print(f"\nTest {idx}: {test['name']}")
    print("-"*70)

    current_title = current_method(test['html'])
    proposed_title, source = proposed_method(test['html'], test['context'])

    print(f"Current method:  {current_title or '(None)'}")
    print(f"Proposed method: {proposed_title or '(None)'} [from: {source}]")

    if current_title != proposed_title:
        if proposed_title and not current_title:
            print("[IMPROVEMENT] Proposed found title, current did not")
        elif not proposed_title and current_title:
            print("[REGRESSION] Current found title, proposed did not")
        else:
            print("[DIFFERENT] Methods found different titles")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)

print("""
CURRENT METHOD LIMITATIONS:
- Only checks FIRST row
- Requires exact colspan match
- No <caption> tag support
- No context awareness
- No content inference

PROPOSED METHOD IMPROVEMENTS:
- Checks first 3 rows
- Uses <caption> tag (HTML standard)
- Uses summary attribute
- Uses context (preceding headings)
- Infers from content (financial tables)
- Clear priority hierarchy
- Better validation
""")
