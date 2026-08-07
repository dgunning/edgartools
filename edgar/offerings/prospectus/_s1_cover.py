"""
S-1 cover page field extraction.

Extracts cover page fields from S-1 registration statements including:
  - Company info (state of incorporation, EIN, SIC code)
  - Filer category checkboxes (accelerated, non-accelerated, etc.)
  - Rule checkboxes (Rule 415, 462b, 462e)
  - Registration number

S-1 cover pages follow a standardized SEC format that is more consistent
than 424B cover pages, making extraction more reliable.
"""

from __future__ import annotations

import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['extract_s1_cover_page']


def extract_s1_cover_page(filing: 'Filing', html: Optional[str] = None) -> dict:
    """
    Extract cover page fields from an S-1 registration statement.

    Args:
        filing: Filing object (used for metadata).
        html: Pre-fetched HTML string. If None, fetched from filing.

    Returns:
        dict suitable for S1CoverPage(**result).
    """
    if html is None:
        html = filing.html() or ''
    # S-1 cover pages can be very long — checkbox areas may extend to 40K+
    cover_text = html[:45000]

    result: dict = {}

    # Company name from filing metadata
    result['company_name'] = filing.company

    # Registration number — prefer header metadata over HTML parsing
    try:
        file_nums = filing.header.file_numbers
        result['registration_number'] = file_nums[0] if file_nums else None
    except Exception:
        result['registration_number'] = None
    if not result['registration_number']:
        reg_match = re.search(r'(333-\d{5,7})', cover_text)
        result['registration_number'] = reg_match.group(1) if reg_match else None

    # State, SIC, EIN — try structured table extraction first
    state, sic, ein = _extract_state_sic_ein_table(cover_text)
    result['state_of_incorporation'] = state
    result['sic_code'] = sic
    result['ein'] = ein

    # Extract filer checkboxes and rule checkboxes from the checkbox table
    checkboxes = _extract_all_checkboxes(cover_text)
    result['is_large_accelerated_filer'] = checkboxes.get('large_accelerated_filer')
    result['is_accelerated_filer'] = checkboxes.get('accelerated_filer')
    result['is_non_accelerated_filer'] = checkboxes.get('non_accelerated_filer')
    result['is_smaller_reporting_company'] = checkboxes.get('smaller_reporting_company')
    result['is_emerging_growth_company'] = checkboxes.get('emerging_growth_company')
    result['is_rule_415'] = bool(checkboxes.get('rule_415'))
    result['is_rule_462b'] = bool(checkboxes.get('rule_462b'))
    result['is_rule_462e'] = bool(checkboxes.get('rule_462e'))

    # Security description from cover
    result['security_description'] = _extract_security_description(cover_text)

    # Confidence scoring
    fields_found = sum(1 for v in [
        result['registration_number'], result['state_of_incorporation'],
        result['ein'], result['sic_code'],
        result['is_large_accelerated_filer'], result['is_smaller_reporting_company'],
    ] if v is not None)
    result['confidence'] = "high" if fields_found >= 4 else "medium" if fields_found >= 2 else "low"

    return result


# ---------------------------------------------------------------------------
# Checkbox extraction
# ---------------------------------------------------------------------------

# Unicode check marks: ☒ = \u2612, ☑ = \u2611, ✓ = \u2713, ✔ = \u2714, ☐ = \u2610
_CHECKED = re.compile(r'[\u2611\u2612\u2713\u2714]|&#9746;|&#9745;')
_UNCHECKED = re.compile(r'[\u2610]|&#9744;')


def _extract_all_checkboxes(html: str) -> dict:
    """Extract all checkbox values from S-1 cover page in a single pass.

    S-1 filings have two checkbox areas:
    1. Rule checkboxes (Rule 415, 462b, 462c, 462d) — appear early in the cover page
    2. Filer category table — a <TABLE> or <table> with rows like:
       [Large accelerated filer] [checkmark] [Accelerated filer] [checkmark]
       [Non-accelerated filer]   [checkmark] [Smaller reporting] [checkmark]

    We scan the HTML for checkmark entities (&#9744;/&#9746;) and map each
    to the nearest label that precedes it.
    """
    result = {}

    # Find all checkmark positions with their values
    checkmarks = []
    for m in re.finditer(r'&#9746;|&#9745;|[\u2611\u2612\u2713\u2714]', html):
        checkmarks.append((m.start(), True))
    for m in re.finditer(r'&#9744;|[\u2610]', html):
        checkmarks.append((m.start(), False))
    checkmarks.sort(key=lambda x: x[0])

    if not checkmarks:
        return result

    # Label patterns and their result keys
    label_patterns = [
        ('rule_415', re.compile(r'Rule\s*(?:&nbsp;|\xa0|\s)*415', re.IGNORECASE)),
        ('rule_462b', re.compile(r'Rule\s*(?:&nbsp;|\xa0|\s)*462\(b\)', re.IGNORECASE)),
        ('rule_462e', re.compile(r'Rule\s*(?:&nbsp;|\xa0|\s)*462\(e\)', re.IGNORECASE)),
        ('large_accelerated_filer', re.compile(
            r'Large(?:&nbsp;|\xa0|\s)+accelerated(?:&nbsp;|\xa0|\s)+filer', re.IGNORECASE)),
        ('non_accelerated_filer', re.compile(
            r'Non(?:&nbsp;|\xa0|\s)*-?(?:&nbsp;|\xa0|\s)*accelerated(?:&nbsp;|\xa0|\s)+filer', re.IGNORECASE)),
        ('smaller_reporting_company', re.compile(
            r'Smaller(?:&nbsp;|\xa0|\s)+reporting(?:&nbsp;|\xa0|\s)+company', re.IGNORECASE)),
        ('emerging_growth_company', re.compile(
            r'Emerging(?:&nbsp;|\xa0|\s)+growth(?:&nbsp;|\xa0|\s)+company', re.IGNORECASE)),
    ]

    # "Accelerated filer" is handled separately since it's a substring of
    # "Large accelerated filer" and "Non-accelerated filer"

    # For each label, find ALL occurrences and pick the one whose nearest
    # after-checkmark is closest (the actual checkbox table instance).
    # Filter out occurrences preceded by "If an/a" (follow-up question text)
    # and those in boilerplate definition paragraphs.
    labels_with_pos = []
    for key, pattern in label_patterns:
        best_match = None
        best_distance = float('inf')
        for m in pattern.finditer(html):
            # Skip follow-up question text: "If an emerging growth company..."
            before_text = html[max(0, m.start() - 20):m.start()].lower()
            if re.search(r'\bif\s+(?:an?\s+)?$', before_text):
                continue
            # Find nearest checkmark after this match
            for ck_pos, _ in checkmarks:
                if ck_pos < m.end():
                    continue
                dist = ck_pos - m.end()
                if dist < best_distance:
                    best_distance = dist
                    best_match = m
                break
        if best_match and best_distance <= 1500:
            labels_with_pos.append((best_match.end(), key))

    # For each label, find the nearest checkmark that comes AFTER it.
    # Distance can be up to 1500 chars due to verbose HTML styles in some filings.
    for label_end, key in labels_with_pos:
        if key in result:
            continue  # Already found
        for ck_pos, ck_val in checkmarks:
            if ck_pos < label_end:
                continue
            distance = ck_pos - label_end
            if distance > 1500:
                break  # Too far — not related
            result[key] = ck_val
            break

    # Handle standalone "Accelerated filer" — use the LAST non-excluded match
    # (the actual table cell, not boilerplate definition text)
    if 'accelerated_filer' not in result:
        accel_pattern = re.compile(r'Accelerated(?:&nbsp;|\xa0|\s)+filer', re.IGNORECASE)
        last_standalone = None
        for m in accel_pattern.finditer(html):
            before = html[max(0, m.start() - 30):m.start()].lower()
            if 'large' in before or 'non' in before:
                continue
            last_standalone = m

        if last_standalone:
            for ck_pos, ck_val in checkmarks:
                if ck_pos < last_standalone.end():
                    continue
                distance = ck_pos - last_standalone.end()
                if distance > 1500:
                    break
                result['accelerated_filer'] = ck_val
                break

    return result


# ---------------------------------------------------------------------------
# State / SIC / EIN extraction
# ---------------------------------------------------------------------------

def _extract_state_sic_ein_table(cover_text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract state, SIC code, and EIN from the S-1 cover page table.

    S-1 cover pages have a standard table layout:
    Row 1: [State value] | [SIC code] | [EIN value]
    Row 2: (State or other jurisdiction...) | (Standard Industrial Classification...) | (I.R.S. Employer...)

    We find the label row and look at the preceding <tr> for values.
    Also tries inline XBRL tags (dei:EntityIncorporationStateCountryCode).
    """
    state = None
    sic = None
    ein = None

    # Try inline XBRL first (most reliable)
    xbrl_state = re.search(
        r'name="dei:EntityIncorporationStateCountryCode"[^>]*>(?:<[^>]*>)*([^<]+)',
        cover_text, re.IGNORECASE
    )
    if xbrl_state:
        state = xbrl_state.group(1).strip()

    # Find the label row with "State or other jurisdiction"
    state_label_match = re.search(
        r'State\s+or\s+other\s+jurisdiction',
        cover_text, re.IGNORECASE
    )

    if state_label_match:
        # The label row and data row are adjacent <tr>s.
        # The last <tr> before the label text is the label row itself;
        # we need the one before that (the data row).
        before = cover_text[max(0, state_label_match.start() - 5000):state_label_match.start()]
        tr_matches = list(re.finditer(r'<tr[^>]*>', before, re.IGNORECASE))

        # Try the data row (second-to-last <tr>) first, then fall back to last
        for tr_idx in [-2, -1] if len(tr_matches) >= 2 else [-1] if tr_matches else []:
            if tr_idx == -2:
                end_pos = tr_matches[-1].start()
            else:
                end_pos = len(before)
            data_row = before[tr_matches[tr_idx].start():end_pos]

            # Extract all text content between > and < in the row
            cell_texts = []
            for text_match in re.finditer(r'>([^<]+)<', data_row):
                text = text_match.group(1).replace('&#160;', '').replace('\xa0', '').replace('&nbsp;', '').strip()
                if text and text != '|':
                    cell_texts.append(text)

            # Assign based on pattern matching
            for text in cell_texts:
                if not state and re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', text):
                    state = text
                elif not sic and re.match(r'^\d{4}$', text):
                    sic = text
                elif not ein and re.match(r'^\d{2}-\d{7}$', text):
                    ein = text

            if state or sic or ein:
                break  # Found data in this row

    # Fallback: EIN near "I.R.S." or "Employer Identification" label
    if not ein:
        ein_match = re.search(
            r'(?:I\.?R\.?S\.?|Employer\s+Identification)[^0-9]{0,80}(\d{2}-\d{7})',
            cover_text[:20000], re.IGNORECASE
        )
        if ein_match:
            ein = ein_match.group(1)

    # Fallback: SIC code — look for 4-digit number between state value and SIC label
    if not sic:
        sic_label_match = re.search(r'Standard\s+Industrial', cover_text, re.IGNORECASE)
        if sic_label_match:
            # Search backwards from the label for a 4-digit number in a tag
            before_sic = cover_text[max(0, sic_label_match.start() - 4000):sic_label_match.start()]
            sic_candidates = re.findall(r'>(\d{4})<', before_sic)
            if sic_candidates:
                sic = sic_candidates[-1]  # Take the closest one

    # Fallback: SIC code after label
    if not sic:
        sic_match = re.search(
            r'(?:Standard\s+Industrial\s+Classification\s+Code\s*(?:Number|No\.?)?\s*[:)]?\s*)(\d{4})',
            cover_text, re.IGNORECASE
        )
        if sic_match:
            sic = sic_match.group(1)

    return state, sic, ein


# ---------------------------------------------------------------------------
# Security description extraction
# ---------------------------------------------------------------------------

def _extract_security_description(cover_text: str) -> Optional[str]:
    """Extract the security description from the S-1 cover page."""
    # S-1 cover pages typically have a prominent security description
    for p in [
        # "2,000,000 Shares of Common Stock"
        r'(\d[\d,]*\s+(?:Shares|Units|Warrants?)\s+of\s+(?:Common|Preferred|Class [AB])?\s*(?:Stock|Shares)?(?:[^\n]{0,80}))',
        # "$100,000,000 -- 10,000,000 Units"
        r'(\$[\d,\.]+\s*[-\u2014\u2013]\s*\d[\d,]*\s+(?:Units?|Shares?)[^\n]{0,80})',
        # "Up to $14,490,000"
        r'(Up\s+to\s+\$[\d,\.]+\s*(?:(?:million|billion|aggregate|of)[\s\w]*)?(?:Common\s+Stock|Class\s+[AB]\s+Common\s+Stock|Ordinary\s+Shares|Units?))',
        # "$X aggregate principal amount"
        r'(\$[\d,\.]+\s+(?:aggregate principal amount|in principal)\s+[\w\s]+(?:Notes|Debentures))',
    ]:
        m = re.search(p, cover_text[:8000], re.IGNORECASE)
        if m:
            return re.sub(r'\s+', ' ', m.group(1)[:150]).strip()
    return None
