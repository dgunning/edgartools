"""
Proxy Statement Text Extraction Guide
=====================================

This module demonstrates how to extract and convert XBRL text blocks from
SEC proxy statements (DEF 14A) into clean, readable text using edgartools.

Text blocks in proxy XBRL contain HTML-formatted content including:
- Executive compensation footnotes
- Pay vs Performance adjustments
- Named Executive Officer details
- Peer group information

Usage:
    from proxy_text_extraction import html_to_text, get_proxy_text_blocks

    # Get all text blocks from a proxy statement
    blocks = get_proxy_text_blocks("TSLA")

    # Convert any HTML fragment to text
    text = html_to_text("<div>Some HTML content</div>")
"""

from typing import Optional
from edgar import Company
from edgar.documents import HTMLParser, TextRenderer


# =============================================================================
# Core Utility Function
# =============================================================================

def html_to_text(html_fragment: str, wrap_html: bool = True) -> str:
    """
    Convert an HTML fragment to clean, formatted text using edgartools.

    This function uses the HTMLParser and TextRenderer from edgar.documents
    to produce well-formatted text output, including proper table rendering.

    Args:
        html_fragment: HTML content to convert (can be a fragment or full document)
        wrap_html: If True, wraps fragments in <html><body> tags for parsing

    Returns:
        Clean text representation of the HTML content

    Example:
        >>> html = '<div><p>Hello</p><table><tr><td>A</td><td>B</td></tr></table></div>'
        >>> print(html_to_text(html))
        Hello

          A      B
    """
    if not html_fragment:
        return ""

    # Wrap fragment in HTML structure if needed
    if wrap_html and not html_fragment.strip().lower().startswith('<html'):
        html_fragment = f"<html><body>{html_fragment}</body></html>"

    parser = HTMLParser()
    renderer = TextRenderer()

    doc = parser.parse(html_fragment)
    return renderer.render(doc)


# =============================================================================
# Available Text Block Concepts in Proxy Statements
# =============================================================================

# These are the XBRL concepts that contain HTML text blocks in proxy filings
PROXY_TEXT_BLOCK_CONCEPTS = {
    # Executive Compensation
    "NamedExecutiveOfficersFnTextBlock": "NEO names and footnotes by year",
    "AdjToPeoCompFnTextBlock": "PEO compensation adjustments with tables",
    "AdjToNonPeoNeoCompFnTextBlock": "Non-PEO NEO compensation adjustments",

    # Pay vs Performance
    "PvpTableTextBlock": "Full Pay vs Performance table",
    "CompActuallyPaidVsTotalShareholderRtnTextBlock": "Comp vs TSR analysis",
    "TotalShareholderRtnVsPeerGroupTextBlock": "TSR vs peer group comparison",
    "TabularListTableTextBlock": "Tabular list of performance measures",

    # Peer Group
    "PeerGroupIssuersFnTextBlock": "Peer group company list",

    # Awards and Timing
    "AwardTmgMethodTextBlock": "Award timing methodology",
    "AwardTmgMnpiDiscTextBlock": "MNPI disclosure for award timing",
    "AwardTmgHowMnpiCnsdrdTextBlock": "How MNPI was considered",

    # Other
    "NonGaapMeasureDescriptionTextBlock": "Non-GAAP measure descriptions",
}


# =============================================================================
# Text Block Extraction Functions
# =============================================================================

def get_proxy_text_blocks(
    ticker_or_cik: str,
    filing_index: int = 0,
    convert_to_text: bool = True
) -> dict[str, str]:
    """
    Extract all text blocks from a company's proxy statement.

    Args:
        ticker_or_cik: Company ticker symbol or CIK number
        filing_index: Index of filing to use (0 = most recent)
        convert_to_text: If True, converts HTML to text; if False, returns raw HTML

    Returns:
        Dictionary mapping concept names to their text/HTML content

    Example:
        >>> blocks = get_proxy_text_blocks("AAPL")
        >>> print(blocks.get("NamedExecutiveOfficersFnTextBlock", "Not found"))
    """
    company = Company(ticker_or_cik)
    filings = company.get_filings(form="DEF 14A")

    if not filings or len(filings) <= filing_index:
        return {}

    filing = filings[filing_index]
    xbrl = filing.xbrl()

    if not xbrl:
        return {}

    blocks = {}

    for concept in PROXY_TEXT_BLOCK_CONCEPTS.keys():
        try:
            results = xbrl.facts.search_facts(concept)
            if len(results) > 0:
                html_content = results.iloc[0]['value']
                if html_content:
                    if convert_to_text:
                        blocks[concept] = html_to_text(html_content)
                    else:
                        blocks[concept] = html_content
        except Exception:
            continue

    return blocks


def get_neo_names(ticker_or_cik: str, filing_index: int = 0) -> dict[int, list[str]]:
    """
    Extract Named Executive Officer names by fiscal year.

    Parses the NamedExecutiveOfficersFnTextBlock to extract NEO names
    for each year mentioned in the proxy statement.

    Note: The format of NEO names varies by company. This function uses a pattern
    that works for companies listing NEOs as "for YYYY, Name1, Name2 and Name3".
    Some companies (e.g., AAPL) use different formats and may return empty results.
    For those cases, use get_proxy_text_blocks() and parse the text manually.

    Args:
        ticker_or_cik: Company ticker symbol or CIK number
        filing_index: Index of filing to use (0 = most recent)

    Returns:
        Dictionary mapping fiscal year to list of NEO names

    Example:
        >>> names = get_neo_names("TSLA")
        >>> print(names)
        {2024: ['Vaibhav Taneja', 'Andrew Baglino', 'Tom Zhu'], ...}
    """
    import re

    blocks = get_proxy_text_blocks(ticker_or_cik, filing_index, convert_to_text=True)
    text = blocks.get("NamedExecutiveOfficersFnTextBlock", "")

    if not text:
        return {}

    # Pattern to match year and names like "(i) for 2024, Name1, Name2 and Name3,"
    # Captures: year, comma-separated names, last name before comma/period/parenthesis
    pattern = r'for (\d{4}),\s*((?:[A-Z][a-z]+\s+[A-Z][a-z]+(?:,\s*)?)+)\s+and\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
    matches = re.findall(pattern, text)

    result = {}
    for year, names_str, last_name in matches:
        # Split on comma and clean up
        names = [n.strip().rstrip(',') for n in names_str.split(',') if n.strip()]
        names.append(last_name.strip())
        # Filter out empty strings
        names = [n for n in names if n]
        result[int(year)] = names

    return result


def get_peo_name(ticker_or_cik: str, filing_index: int = 0) -> Optional[str]:
    """
    Extract the Principal Executive Officer (PEO/CEO) name.

    Args:
        ticker_or_cik: Company ticker symbol or CIK number
        filing_index: Index of filing to use (0 = most recent)

    Returns:
        PEO name or None if not found

    Example:
        >>> get_peo_name("TSLA")
        'Mr. Musk'
    """
    company = Company(ticker_or_cik)
    filings = company.get_filings(form="DEF 14A")

    if not filings or len(filings) <= filing_index:
        return None

    filing = filings[filing_index]
    xbrl = filing.xbrl()

    if not xbrl:
        return None

    try:
        results = xbrl.facts.search_facts('PeoName')
        if len(results) > 0:
            return results.iloc[0]['value']
    except Exception:
        pass

    return None


def get_peer_group_companies(ticker_or_cik: str, filing_index: int = 0) -> Optional[str]:
    """
    Extract the peer group company list from the proxy statement.

    Args:
        ticker_or_cik: Company ticker symbol or CIK number
        filing_index: Index of filing to use (0 = most recent)

    Returns:
        Text describing peer group companies, or None if not found
    """
    blocks = get_proxy_text_blocks(ticker_or_cik, filing_index)
    return blocks.get("PeerGroupIssuersFnTextBlock")


def get_performance_measures(ticker_or_cik: str, filing_index: int = 0) -> list[str]:
    """
    Extract the company's most important performance measures.

    These are the financial metrics the company uses to link executive
    compensation to performance.

    Args:
        ticker_or_cik: Company ticker symbol or CIK number
        filing_index: Index of filing to use (0 = most recent)

    Returns:
        List of performance measure names

    Example:
        >>> get_performance_measures("AAPL")
        ['Net Sales', 'Operating Income', 'Relative TSR']
    """
    company = Company(ticker_or_cik)
    filings = company.get_filings(form="DEF 14A")

    if not filings or len(filings) <= filing_index:
        return []

    filing = filings[filing_index]
    xbrl = filing.xbrl()

    if not xbrl:
        return []

    measures = []
    try:
        results = xbrl.facts.search_facts('MeasureName')
        if len(results) > 0:
            # Get unique measure names
            measures = results['value'].dropna().unique().tolist()
    except Exception:
        pass

    return measures


def get_governance_flags(ticker_or_cik: str, filing_index: int = 0) -> dict[str, bool]:
    """
    Extract governance-related boolean flags from the proxy.

    Args:
        ticker_or_cik: Company ticker symbol or CIK number
        filing_index: Index of filing to use (0 = most recent)

    Returns:
        Dictionary of governance flags and their values

    Example:
        >>> get_governance_flags("TSLA")
        {'insider_trading_policy_adopted': True, 'award_timing_mnpi_considered': False}
    """
    company = Company(ticker_or_cik)
    filings = company.get_filings(form="DEF 14A")

    if not filings or len(filings) <= filing_index:
        return {}

    filing = filings[filing_index]
    xbrl = filing.xbrl()

    if not xbrl:
        return {}

    flags = {}
    flag_concepts = [
        ("InsiderTrdPoliciesProcAdoptedFlag", "insider_trading_policy_adopted"),
        ("AwardTmgMnpiCnsdrdFlag", "award_timing_mnpi_considered"),
        ("AwardTmgPredtrmndFlag", "award_timing_predetermined"),
        ("MnpiDiscTimedForCompValFlag", "mnpi_timed_for_comp_value"),
    ]

    for concept, key in flag_concepts:
        try:
            results = xbrl.facts.search_facts(concept)
            if len(results) > 0:
                value = results.iloc[0]['value']
                # Convert string boolean to actual boolean
                if isinstance(value, str):
                    flags[key] = value.lower() in ('true', 'yes', '1')
                else:
                    flags[key] = bool(value)
        except Exception:
            continue

    return flags


# =============================================================================
# Demo / Example Usage
# =============================================================================

if __name__ == "__main__":
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else "TSLA"

    print(f"Proxy Statement Text Extraction - {ticker}")
    print("=" * 60)

    # Get PEO name
    peo = get_peo_name(ticker)
    print(f"\nPEO (CEO): {peo or 'Not found'}")

    # Get NEO names by year
    print("\nNamed Executive Officers by Year:")
    neo_names = get_neo_names(ticker)
    if neo_names:
        for year, names in sorted(neo_names.items(), reverse=True):
            print(f"  {year}: {', '.join(names)}")
    else:
        print("  (format varies - check text blocks manually)")

    # Get performance measures
    print("\nPerformance Measures:")
    measures = get_performance_measures(ticker)
    for m in measures:
        print(f"  - {m}")

    # Get governance flags
    print("\nGovernance Flags:")
    flags = get_governance_flags(ticker)
    for flag, value in flags.items():
        status = "Yes" if value else "No"
        print(f"  {flag}: {status}")

    # Get all text blocks (summary only)
    print("\n" + "=" * 60)
    print("Available Text Blocks:")
    print("=" * 60)

    blocks = get_proxy_text_blocks(ticker)
    for concept in blocks.keys():
        description = PROXY_TEXT_BLOCK_CONCEPTS.get(concept, "")
        print(f"  - {concept}: {description}")

    # Show one example in detail
    if "TabularListTableTextBlock" in blocks:
        print("\n" + "=" * 60)
        print("Example: TabularListTableTextBlock")
        print("=" * 60)
        print(blocks["TabularListTableTextBlock"])
