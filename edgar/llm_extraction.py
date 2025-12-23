import re
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

from bs4 import BeautifulSoup

from edgar.financials import Financials

try:
    from edgar.sgml.filing_summary import Report
except Exception:  # pragma: no cover - optional import for typing
    Report = None

# =============================================================================
# Form Item Definitions
# =============================================================================

# 10-K Annual Report Item Definitions
# SEC Form 10-K has 16 items organized in 4 parts
FORM_10K_ITEMS = {
    "Item 1": {
        "title": "Business",
        "boundaries": ["Item 1A", "Item 1B", "Item 2"],
        "part": "Part I",
    },
    "Item 1A": {
        "title": "Risk Factors",
        "boundaries": ["Item 1B", "Item 2"],
        "part": "Part I",
    },
    "Item 1B": {
        "title": "Unresolved Staff Comments",
        "boundaries": ["Item 1C", "Item 2"],
        "part": "Part I",
    },
    "Item 1C": {
        "title": "Cybersecurity",
        "boundaries": ["Item 2"],
        "part": "Part I",
    },
    "Item 2": {
        "title": "Properties",
        "boundaries": ["Item 3"],
        "part": "Part I",
    },
    "Item 3": {
        "title": "Legal Proceedings",
        "boundaries": ["Item 4"],
        "part": "Part I",
    },
    "Item 4": {
        "title": "Mine Safety Disclosures",
        "boundaries": ["Part II", "Item 5"],
        "part": "Part I",
    },
    "Item 5": {
        "title": "Market for Registrant's Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities",
        "boundaries": ["Item 6", "Item 7"],
        "part": "Part II",
    },
    "Item 6": {
        "title": "[Reserved]",
        "boundaries": ["Item 7"],
        "part": "Part II",
    },
    "Item 7": {
        "title": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
        "boundaries": ["Item 7A", "Item 8"],
        "part": "Part II",
    },
    "Item 7A": {
        "title": "Quantitative and Qualitative Disclosures About Market Risk",
        "boundaries": ["Item 8"],
        "part": "Part II",
    },
    "Item 8": {
        "title": "Financial Statements and Supplementary Data",
        "boundaries": ["Item 9", "Item 9A"],
        "part": "Part II",
    },
    "Item 9": {
        "title": "Changes in and Disagreements With Accountants on Accounting and Financial Disclosure",
        "boundaries": ["Item 9A"],
        "part": "Part II",
    },
    "Item 9A": {
        "title": "Controls and Procedures",
        "boundaries": ["Item 9B"],
        "part": "Part II",
    },
    "Item 9B": {
        "title": "Other Information",
        "boundaries": ["Item 9C", "Part III", "Item 10"],
        "part": "Part II",
    },
    "Item 9C": {
        "title": "Disclosure Regarding Foreign Jurisdictions that Prevent Inspections",
        "boundaries": ["Part III", "Item 10"],
        "part": "Part II",
    },
    "Item 10": {
        "title": "Directors, Executive Officers and Corporate Governance",
        "boundaries": ["Item 11"],
        "part": "Part III",
    },
    "Item 11": {
        "title": "Executive Compensation",
        "boundaries": ["Item 12"],
        "part": "Part III",
    },
    "Item 12": {
        "title": "Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters",
        "boundaries": ["Item 13"],
        "part": "Part III",
    },
    "Item 13": {
        "title": "Certain Relationships and Related Transactions, and Director Independence",
        "boundaries": ["Item 14"],
        "part": "Part III",
    },
    "Item 14": {
        "title": "Principal Accountant Fees and Services",
        "boundaries": ["Part IV", "Item 15"],
        "part": "Part III",
    },
    "Item 15": {
        "title": "Exhibits and Financial Statement Schedules",
        "boundaries": ["Item 16", "Signature"],
        "part": "Part IV",
    },
    "Item 16": {
        "title": "Form 10-K Summary",
        "boundaries": ["Signature"],
        "part": "Part IV",
    },
}

# 10-Q Quarterly Report Item Definitions
# SEC Form 10-Q has items organized in 2 parts
FORM_10Q_ITEMS = {
    # Part I - Financial Information
    "Item 1": {
        "title": "Financial Statements",
        "boundaries": ["Item 2"],
        "part": "Part I",
    },
    "Item 2": {
        "title": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
        "boundaries": ["Item 3"],
        "part": "Part I",
    },
    "Item 3": {
        "title": "Quantitative and Qualitative Disclosures About Market Risk",
        "boundaries": ["Item 4"],
        "part": "Part I",
    },
    "Item 4": {
        "title": "Controls and Procedures",
        "boundaries": ["Part II", "Item 1"],
        "part": "Part I",
    },
    # Part II - Other Information
    "Part II Item 1": {
        "title": "Legal Proceedings",
        "boundaries": ["Item 1A", "Part II Item 1A", "Item 2", "Part II Item 2"],
        "part": "Part II",
        "aliases": ["Item 1"],
    },
    "Part II Item 1A": {
        "title": "Risk Factors",
        "boundaries": ["Item 2", "Part II Item 2"],
        "part": "Part II",
        "aliases": ["Item 1A"],
    },
    "Part II Item 2": {
        "title": "Unregistered Sales of Equity Securities and Use of Proceeds",
        "boundaries": ["Item 3", "Part II Item 3"],
        "part": "Part II",
        "aliases": ["Item 2"],
    },
    "Part II Item 3": {
        "title": "Defaults Upon Senior Securities",
        "boundaries": ["Item 4", "Part II Item 4"],
        "part": "Part II",
        "aliases": ["Item 3"],
    },
    "Part II Item 4": {
        "title": "Mine Safety Disclosures",
        "boundaries": ["Item 5", "Part II Item 5"],
        "part": "Part II",
        "aliases": ["Item 4"],
    },
    "Part II Item 5": {
        "title": "Other Information",
        "boundaries": ["Item 6", "Part II Item 6"],
        "part": "Part II",
        "aliases": ["Item 5"],
    },
    "Part II Item 6": {
        "title": "Exhibits",
        "boundaries": ["Signature"],
        "part": "Part II",
        "aliases": ["Item 6"],
    },
}

# 20-F Annual Report for Foreign Private Issuers
# Has sub-items (e.g., Item 3A, 3B, 3C, 3D)
FORM_20F_ITEMS = {
    # Part I
    "Item 1": {
        "title": "Identity of Directors, Senior Management and Advisers",
        "boundaries": ["Item 2"],
        "part": "Part I",
    },
    "Item 2": {
        "title": "Offer Statistics and Expected Timetable",
        "boundaries": ["Item 3"],
        "part": "Part I",
    },
    "Item 3": {
        "title": "Key Information",
        "boundaries": ["Item 4"],
        "part": "Part I",
        "sub_items": ["Item 3A", "Item 3B", "Item 3C", "Item 3D"],
    },
    "Item 3A": {
        "title": "[Reserved]",
        "boundaries": ["Item 3B"],
        "part": "Part I",
        "parent": "Item 3",
    },
    "Item 3B": {
        "title": "Capitalization and Indebtedness",
        "boundaries": ["Item 3C"],
        "part": "Part I",
        "parent": "Item 3",
    },
    "Item 3C": {
        "title": "Reasons for the Offer and Use of Proceeds",
        "boundaries": ["Item 3D"],
        "part": "Part I",
        "parent": "Item 3",
    },
    "Item 3D": {
        "title": "Risk Factors",
        "boundaries": ["Item 4"],
        "part": "Part I",
        "parent": "Item 3",
    },
    "Item 4": {
        "title": "Information on the Company",
        "boundaries": ["Item 4A", "Item 5"],
        "part": "Part I",
        "sub_items": ["Item 4A", "Item 4B", "Item 4C", "Item 4D"],
    },
    "Item 4A": {
        "title": "Unresolved Staff Comments",
        "boundaries": ["Item 4B", "Item 5"],
        "part": "Part I",
        "parent": "Item 4",
    },
    "Item 4B": {
        "title": "Business Overview",
        "boundaries": ["Item 4C"],
        "part": "Part I",
        "parent": "Item 4",
    },
    "Item 4C": {
        "title": "Organizational Structure",
        "boundaries": ["Item 4D"],
        "part": "Part I",
        "parent": "Item 4",
    },
    "Item 4D": {
        "title": "Property, Plants and Equipment",
        "boundaries": ["Item 5"],
        "part": "Part I",
        "parent": "Item 4",
    },
    "Item 5": {
        "title": "Operating and Financial Review and Prospects",
        "boundaries": ["Item 6"],
        "part": "Part I",
        "sub_items": ["Item 5A", "Item 5B", "Item 5C", "Item 5D", "Item 5E", "Item 5F"],
    },
    "Item 5A": {
        "title": "Operating Results",
        "boundaries": ["Item 5B"],
        "part": "Part I",
        "parent": "Item 5",
    },
    "Item 5B": {
        "title": "Liquidity and Capital Resources",
        "boundaries": ["Item 5C"],
        "part": "Part I",
        "parent": "Item 5",
    },
    "Item 5C": {
        "title": "Research and Development, Patents and Licenses",
        "boundaries": ["Item 5D"],
        "part": "Part I",
        "parent": "Item 5",
    },
    "Item 5D": {
        "title": "Trend Information",
        "boundaries": ["Item 5E"],
        "part": "Part I",
        "parent": "Item 5",
    },
    "Item 5E": {
        "title": "Critical Accounting Estimates",
        "boundaries": ["Item 5F", "Item 6"],
        "part": "Part I",
        "parent": "Item 5",
    },
    "Item 5F": {
        "title": "Off-Balance Sheet Arrangements",
        "boundaries": ["Item 6"],
        "part": "Part I",
        "parent": "Item 5",
    },
    "Item 6": {
        "title": "Directors, Senior Management and Employees",
        "boundaries": ["Item 7"],
        "part": "Part I",
        "sub_items": ["Item 6A", "Item 6B", "Item 6C", "Item 6D", "Item 6E"],
    },
    "Item 6A": {
        "title": "Directors and Senior Management",
        "boundaries": ["Item 6B"],
        "part": "Part I",
        "parent": "Item 6",
    },
    "Item 6B": {
        "title": "Compensation",
        "boundaries": ["Item 6C"],
        "part": "Part I",
        "parent": "Item 6",
    },
    "Item 6C": {
        "title": "Board Practices",
        "boundaries": ["Item 6D"],
        "part": "Part I",
        "parent": "Item 6",
    },
    "Item 6D": {
        "title": "Employees",
        "boundaries": ["Item 6E"],
        "part": "Part I",
        "parent": "Item 6",
    },
    "Item 6E": {
        "title": "Share Ownership",
        "boundaries": ["Item 7"],
        "part": "Part I",
        "parent": "Item 6",
    },
    "Item 7": {
        "title": "Major Shareholders and Related Party Transactions",
        "boundaries": ["Item 8"],
        "part": "Part I",
        "sub_items": ["Item 7A", "Item 7B", "Item 7C"],
    },
    "Item 7A": {
        "title": "Major Shareholders",
        "boundaries": ["Item 7B"],
        "part": "Part I",
        "parent": "Item 7",
    },
    "Item 7B": {
        "title": "Related Party Transactions",
        "boundaries": ["Item 7C"],
        "part": "Part I",
        "parent": "Item 7",
    },
    "Item 7C": {
        "title": "Interests of Experts and Counsel",
        "boundaries": ["Item 8"],
        "part": "Part I",
        "parent": "Item 7",
    },
    "Item 8": {
        "title": "Financial Information",
        "boundaries": ["Item 9"],
        "part": "Part I",
        "sub_items": ["Item 8A", "Item 8B"],
    },
    "Item 8A": {
        "title": "Consolidated Statements and Other Financial Information",
        "boundaries": ["Item 8B"],
        "part": "Part I",
        "parent": "Item 8",
    },
    "Item 8B": {
        "title": "Significant Changes",
        "boundaries": ["Item 9"],
        "part": "Part I",
        "parent": "Item 8",
    },
    "Item 9": {
        "title": "The Offer and Listing",
        "boundaries": ["Item 10"],
        "part": "Part I",
        "sub_items": ["Item 9A", "Item 9B", "Item 9C"],
    },
    "Item 9A": {
        "title": "Offer and Listing Details",
        "boundaries": ["Item 9B"],
        "part": "Part I",
        "parent": "Item 9",
    },
    "Item 9B": {
        "title": "Plan of Distribution",
        "boundaries": ["Item 9C"],
        "part": "Part I",
        "parent": "Item 9",
    },
    "Item 9C": {
        "title": "Markets",
        "boundaries": ["Item 10"],
        "part": "Part I",
        "parent": "Item 9",
    },
    "Item 10": {
        "title": "Additional Information",
        "boundaries": ["Item 11"],
        "part": "Part I",
        "sub_items": ["Item 10A", "Item 10B", "Item 10C", "Item 10D", "Item 10E", "Item 10F", "Item 10G", "Item 10H"],
    },
    "Item 10A": {
        "title": "Share Capital",
        "boundaries": ["Item 10B"],
        "part": "Part I",
        "parent": "Item 10",
    },
    "Item 10B": {
        "title": "Memorandum and Articles of Association",
        "boundaries": ["Item 10C"],
        "part": "Part I",
        "parent": "Item 10",
    },
    "Item 10C": {
        "title": "Material Contracts",
        "boundaries": ["Item 10D"],
        "part": "Part I",
        "parent": "Item 10",
    },
    "Item 10D": {
        "title": "Exchange Controls",
        "boundaries": ["Item 10E"],
        "part": "Part I",
        "parent": "Item 10",
    },
    "Item 10E": {
        "title": "Taxation",
        "boundaries": ["Item 10F"],
        "part": "Part I",
        "parent": "Item 10",
    },
    "Item 10F": {
        "title": "Dividends and Paying Agents",
        "boundaries": ["Item 10G"],
        "part": "Part I",
        "parent": "Item 10",
    },
    "Item 10G": {
        "title": "Statement by Experts",
        "boundaries": ["Item 10H"],
        "part": "Part I",
        "parent": "Item 10",
    },
    "Item 10H": {
        "title": "Documents on Display",
        "boundaries": ["Item 11"],
        "part": "Part I",
        "parent": "Item 10",
    },
    "Item 11": {
        "title": "Quantitative and Qualitative Disclosures About Market Risk",
        "boundaries": ["Item 12"],
        "part": "Part I",
    },
    "Item 12": {
        "title": "Description of Securities Other than Equity Securities",
        "boundaries": ["Part II", "Item 13"],
        "part": "Part I",
        "sub_items": ["Item 12A", "Item 12B", "Item 12C", "Item 12D"],
    },
    "Item 12A": {
        "title": "Debt Securities",
        "boundaries": ["Item 12B"],
        "part": "Part I",
        "parent": "Item 12",
    },
    "Item 12B": {
        "title": "Warrants and Rights",
        "boundaries": ["Item 12C"],
        "part": "Part I",
        "parent": "Item 12",
    },
    "Item 12C": {
        "title": "Other Securities",
        "boundaries": ["Item 12D"],
        "part": "Part I",
        "parent": "Item 12",
    },
    "Item 12D": {
        "title": "American Depositary Shares",
        "boundaries": ["Part II", "Item 13"],
        "part": "Part I",
        "parent": "Item 12",
    },
    # Part II
    "Item 13": {
        "title": "Defaults, Dividend Arrearages and Delinquencies",
        "boundaries": ["Item 14"],
        "part": "Part II",
    },
    "Item 14": {
        "title": "Material Modifications to the Rights of Security Holders and Use of Proceeds",
        "boundaries": ["Item 15"],
        "part": "Part II",
    },
    "Item 15": {
        "title": "Controls and Procedures",
        "boundaries": ["Item 16"],
        "part": "Part II",
    },
    "Item 16": {
        "title": "Reserved",
        "boundaries": ["Item 16A"],
        "part": "Part II",
        "sub_items": ["Item 16A", "Item 16B", "Item 16C", "Item 16D", "Item 16E", "Item 16F", "Item 16G", "Item 16H", "Item 16I", "Item 16J", "Item 16K"],
    },
    "Item 16A": {
        "title": "Audit Committee Financial Expert",
        "boundaries": ["Item 16B"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16B": {
        "title": "Code of Ethics",
        "boundaries": ["Item 16C"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16C": {
        "title": "Principal Accountant Fees and Services",
        "boundaries": ["Item 16D"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16D": {
        "title": "Exemptions from the Listing Standards for Audit Committees",
        "boundaries": ["Item 16E"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16E": {
        "title": "Purchases of Equity Securities by the Issuer and Affiliated Purchasers",
        "boundaries": ["Item 16F"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16F": {
        "title": "Change in Registrant's Certifying Accountant",
        "boundaries": ["Item 16G"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16G": {
        "title": "Corporate Governance",
        "boundaries": ["Item 16H"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16H": {
        "title": "Mine Safety Disclosure",
        "boundaries": ["Item 16I"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16I": {
        "title": "Disclosure Regarding Foreign Jurisdictions that Prevent Inspections",
        "boundaries": ["Item 16J"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16J": {
        "title": "Insider Trading Policies",
        "boundaries": ["Item 16K"],
        "part": "Part II",
        "parent": "Item 16",
    },
    "Item 16K": {
        "title": "Cybersecurity",
        "boundaries": ["Part III", "Item 17"],
        "part": "Part II",
        "parent": "Item 16",
    },
    # Part III
    "Item 17": {
        "title": "Financial Statements",
        "boundaries": ["Item 18"],
        "part": "Part III",
    },
    "Item 18": {
        "title": "Financial Statements",
        "boundaries": ["Item 19"],
        "part": "Part III",
    },
    "Item 19": {
        "title": "Exhibits",
        "boundaries": ["Signature"],
        "part": "Part III",
    },
}

# Master form registry
FORM_ITEM_REGISTRY = {
    "10-K": FORM_10K_ITEMS,
    "10-K/A": FORM_10K_ITEMS,
    "10-Q": FORM_10Q_ITEMS,
    "10-Q/A": FORM_10Q_ITEMS,
    "20-F": FORM_20F_ITEMS,
    "20-F/A": FORM_20F_ITEMS,
}


def _get_form_items(form_type: Optional[str]) -> Optional[dict]:
    """Get item definitions for a specific form type."""
    if not form_type:
        return None
    # Normalize form type (handle variations)
    normalized = form_type.upper().strip()
    return FORM_ITEM_REGISTRY.get(normalized)


def _get_item_boundaries(form_type: Optional[str], item_name: str) -> List[str]:
    """Get boundary items for a specific item in a form.

    Returns the list of items that mark the end of the specified item's content.
    Falls back to generic boundaries if form-specific ones aren't available.
    """
    form_items = _get_form_items(form_type)

    if form_items and item_name in form_items:
        return form_items[item_name].get("boundaries", []) + ["Signature"]

    # Fallback to legacy boundaries
    return _ITEM_BOUNDARIES.get(item_name, ["Item", "Signature"])


def _get_item_title(form_type: Optional[str], item_name: str) -> str:
    """Get the official title for an item."""
    form_items = _get_form_items(form_type)

    if form_items and item_name in form_items:
        return form_items[item_name].get("title", item_name)

    return item_name


def get_form_items(form_type: str) -> List[str]:
    """Get all available item names for a form type.

    Args:
        form_type: The SEC form type (e.g., "10-K", "10-Q", "20-F")

    Returns:
        List of item names available for this form type

    Example:
        >>> get_form_items("10-K")
        ['Item 1', 'Item 1A', 'Item 1B', 'Item 1C', 'Item 2', ...]
    """
    form_items = _get_form_items(form_type)
    if not form_items:
        return []
    return list(form_items.keys())


def get_item_info(form_type: str, item_name: str) -> Optional[dict]:
    """Get detailed information about a specific item.

    Args:
        form_type: The SEC form type (e.g., "10-K", "10-Q", "20-F")
        item_name: The item name (e.g., "Item 7A")

    Returns:
        Dictionary with item info (title, boundaries, part, sub_items, parent)
        or None if not found

    Example:
        >>> get_item_info("10-K", "Item 7")
        {'title': "Management's Discussion...", 'boundaries': ['Item 7A', 'Item 8'], 'part': 'Part II'}
    """
    form_items = _get_form_items(form_type)
    if not form_items:
        return None

    normalized = _normalize_item_name(item_name, form_type)
    return form_items.get(normalized)


def _normalize_item_name(item_name: str, form_type: Optional[str] = None) -> str:
    """Normalize item name to match form definitions.

    Handles variations like:
    - "item 1" -> "Item 1"
    - "Item1" -> "Item 1"
    - "ITEM 1A" -> "Item 1A"
    - "Item 3.D" -> "Item 3D" (for 20-F)
    """
    if not item_name:
        return item_name

    # Basic normalization
    normalized = item_name.strip()

    # Handle "Item 3.D" -> "Item 3D" for 20-F sub-items (do this first)
    normalized = re.sub(r"(?i)(item\s*\d+)\.([A-Za-z])", r"\1\2", normalized)

    # Handle various formats: "item 1", "Item1", "ITEM 1A", "Item 1.A"
    match = re.match(r"(?i)(item)\s*(\d+)\s*\.?\s*([A-Za-z]?)", normalized)
    if match:
        prefix, num, suffix = match.groups()
        normalized = f"Item {num}{suffix.upper()}"

    # Handle 10-Q Part II items
    if form_type and form_type.upper().startswith("10-Q"):
        # Check if this might be a Part II item
        part2_match = re.match(r"(?i)(?:part\s*(?:ii|2)\s+)?(item\s+\d+[A-Za-z]?)", normalized)
        if part2_match:
            item_part = part2_match.group(1)
            # Normalize the item part
            item_match = re.match(r"(?i)item\s*(\d+)([A-Za-z]?)", item_part)
            if item_match:
                num, suffix = item_match.groups()
                normalized = f"Item {num}{suffix.upper()}"

    return normalized


__all__ = [
    "ExtractedSection",
    "extract_markdown",
    "extract_sections",
    "extract_filing_markdown",
    "extract_filing_sections",
    # Form item utilities
    "get_form_items",
    "get_item_info",
    "FORM_10K_ITEMS",
    "FORM_10Q_ITEMS",
    "FORM_20F_ITEMS",
    "FORM_ITEM_REGISTRY",
]


@dataclass
class ExtractedSection:
    title: str
    markdown: str
    source: str


def extract_filing_markdown(
    filing,
    *,
    item: Optional[Union[str, Sequence[str]]] = None,
    category: Optional[Union[str, Sequence[str]]] = None,
    statement: Optional[Union[str, Sequence[str]]] = None,
    notes: bool = False,
    max_reports: Optional[int] = None,
    include_header: bool = True,
) -> str:
    sections = extract_filing_sections(
        filing,
        item=item,
        category=category,
        statement=statement,
        notes=notes,
        max_reports=max_reports,
    )

    parts: List[str] = []
    if include_header:
        header = _build_header(filing)
        if header:
            parts.append(header)
        parts.append("FORMAT: Text is plain paragraphs. Tables are Markdown.")

    for section in sections:
        parts.append(f"## SECTION: {section.title}")
        if section.markdown:
            parts.append(section.markdown)

    return "\n\n".join(part for part in parts if part)


def extract_filing_sections(
    filing,
    *,
    item: Optional[Union[str, Sequence[str]]] = None,
    category: Optional[Union[str, Sequence[str]]] = None,
    statement: Optional[Union[str, Sequence[str]]] = None,
    notes: bool = False,
    max_reports: Optional[int] = None,
) -> List[ExtractedSection]:
    if _is_report_like(filing):
        return _extract_report_sections(filing)
    if isinstance(filing, Financials):
        statements = _normalize_list(statement)
        return _extract_financials_sections(filing, statements)

    items = _normalize_list(item)
    categories = _normalize_list(category)
    statements = _normalize_list(statement)

    if not items and not categories and not statements:
        statements = ["AllStatements"]
        if notes:
            categories = ["Notes"]
    elif notes and "Notes" not in categories:
        categories.append("Notes")

    sections: List[ExtractedSection] = []

    for item_name in items:
        sections.extend(_extract_item_sections(filing, item_name))

    for category_name in categories:
        sections.extend(_extract_category_sections(filing, category_name, max_reports))

    for statement_name in statements:
        sections.extend(
            _extract_statement_sections(filing, statement_name, max_reports)
        )

    return sections


def extract_markdown(
    source,
    *,
    item: Optional[Union[str, Sequence[str]]] = None,
    category: Optional[Union[str, Sequence[str]]] = None,
    statement: Optional[Union[str, Sequence[str]]] = None,
    notes: bool = False,
    max_reports: Optional[int] = None,
    include_header: bool = True,
) -> str:
    return extract_filing_markdown(
        source,
        item=item,
        category=category,
        statement=statement,
        notes=notes,
        max_reports=max_reports,
        include_header=include_header,
    )


def extract_sections(
    source,
    *,
    item: Optional[Union[str, Sequence[str]]] = None,
    category: Optional[Union[str, Sequence[str]]] = None,
    statement: Optional[Union[str, Sequence[str]]] = None,
    notes: bool = False,
    max_reports: Optional[int] = None,
) -> List[ExtractedSection]:
    return extract_filing_sections(
        source,
        item=item,
        category=category,
        statement=statement,
        notes=notes,
        max_reports=max_reports,
    )


def _normalize_list(value: Optional[Union[str, Sequence[str]]]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [v for v in value if v]


def _extract_item_sections(filing, item_name: str) -> List[ExtractedSection]:
    # Get form type for form-aware extraction
    form_type = getattr(filing, "form", None)

    # Normalize the item name
    normalized_item = _normalize_item_name(item_name, form_type)

    # Get the official title for this item
    official_title = _get_item_title(form_type, normalized_item)

    html_content, section_title = _extract_item_html(filing, normalized_item, form_type)
    if html_content:
        display_title = section_title or official_title or normalized_item
        markdown = process_content(html_content, section_title=display_title)
        return [
            ExtractedSection(
                title=display_title,
                markdown=markdown,
                source=f"item:{normalized_item}",
            )
        ]

    text_content = _extract_item_text(filing, normalized_item)
    if text_content:
        display_title = official_title or normalized_item
        markdown = process_content(text_content, section_title=display_title)
        return [
            ExtractedSection(
                title=display_title,
                markdown=markdown,
                source=f"item:{normalized_item}",
            )
        ]

    return []


def _extract_item_html(
    filing, item_name: str, form_type: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    try:
        report = filing.obj()
    except Exception:
        report = None

    if report is not None and hasattr(report, "document"):
        try:
            doc = report.document
            section = doc.sections.get_item(item_name)
            if section is None:
                section = doc.sections.get(item_name)
            if section is not None:
                html = section.node.html()
                if _has_meaningful_html(html):
                    return html, section.title or item_name
        except Exception:
            pass

    html = filing.html()
    if not html:
        return None, None

    # Use form-aware boundaries
    stop_targets = _get_item_boundaries(form_type, item_name)
    html_content = extract_item_with_boundaries(html, item_name, stop_targets, form_type)
    if html_content:
        return html_content, item_name

    return None, None


def _has_meaningful_html(html: Optional[str]) -> bool:
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("table"):
        return True
    return bool(clean_text(soup.get_text()))


def _extract_item_text(filing, item_name: str) -> Optional[str]:
    try:
        report = filing.obj()
    except Exception:
        report = None

    if report is not None:
        try:
            return report[item_name]
        except Exception:
            return None
    return None


def _extract_category_sections(
    filing, category_name: str, max_reports: Optional[int]
) -> List[ExtractedSection]:
    reports = None
    try:
        reports = filing.reports
    except Exception:
        reports = None

    if not reports:
        return []

    category_reports = reports.get_by_category(category_name)
    if not category_reports:
        return []

    sections: List[ExtractedSection] = []
    is_statements = category_name.strip().lower() == "statements"
    for idx, report in enumerate(category_reports):
        if max_reports is not None and idx >= max_reports:
            break
        title = report.short_name or report.long_name or category_name
        if is_statements:
            markdown = _report_to_markdown(report, section_title=title)
        else:
            markdown = process_content(report.content, section_title=title)
        sections.append(
            ExtractedSection(
                title=title,
                markdown=markdown,
                source=f"category:{category_name}",
            )
        )
    return sections


def _extract_statement_sections(
    filing, statement_name: str, max_reports: Optional[int]
) -> List[ExtractedSection]:
    canonical = _normalize_statement_name(statement_name)
    if canonical is None:
        return []

    if canonical == "AllStatements":
        return _extract_category_sections(filing, "Statements", max_reports)

    reports = None
    try:
        reports = filing.reports
    except Exception:
        reports = None

    if reports:
        statement_reports = _match_statement_reports(reports, canonical)
        if statement_reports:
            sections: List[ExtractedSection] = []
            for idx, report in enumerate(statement_reports):
                if max_reports is not None and idx >= max_reports:
                    break
                title = report.short_name or report.long_name or statement_name
                markdown = _report_to_markdown(report, section_title=title)
                sections.append(
                    ExtractedSection(
                        title=title,
                        markdown=markdown,
                        source=f"statement:{canonical}",
                    )
                )
            return sections

    financials = Financials.extract(filing)
    if financials is None:
        return []

    statement_obj = _get_statement_from_financials(financials, canonical)
    if statement_obj is None:
        return []

    markdown = _statement_to_markdown(statement_obj)
    if not markdown:
        return []

    return [
        ExtractedSection(
            title=statement_name,
            markdown=markdown,
            source=f"statement:{canonical}",
        )
    ]


def _extract_financials_sections(
    financials: Financials, statements: List[str]
) -> List[ExtractedSection]:
    if not statements:
        statements = ["AllStatements"]

    sections: List[ExtractedSection] = []
    for statement_name in statements:
        canonical = _normalize_statement_name(statement_name)
        if canonical is None:
            continue
        canonical_list = (
            _STATEMENT_ORDER if canonical == "AllStatements" else [canonical]
        )
        for canonical_name in canonical_list:
            statement_obj = _get_statement_from_financials(
                financials, canonical_name
            )
            if statement_obj is None:
                continue
            markdown = _statement_to_markdown(statement_obj)
            if not markdown:
                continue
            title = _STATEMENT_TITLES.get(canonical_name, statement_name)
            sections.append(
                ExtractedSection(
                    title=title,
                    markdown=markdown,
                    source=f"statement:{canonical_name}",
                )
            )
    return sections


def _extract_report_sections(report) -> List[ExtractedSection]:
    title = _report_title(report)
    markdown = _report_to_markdown(report, section_title=title)
    if not markdown:
        return []
    return [
        ExtractedSection(
            title=title,
            markdown=markdown,
            source=f"report:{title}",
        )
    ]


def _get_statement_from_financials(financials: Financials, canonical: str):
    mapping = {
        "IncomeStatement": financials.income_statement,
        "BalanceSheet": financials.balance_sheet,
        "CashFlowStatement": financials.cashflow_statement,
        "StatementOfEquity": financials.statement_of_equity,
        "ComprehensiveIncome": financials.comprehensive_income,
        "CoverPage": financials.cover,
    }
    getter = mapping.get(canonical)
    return getter() if getter else None


def _statement_to_markdown(statement_obj) -> str:
    try:
        rendered = statement_obj.render(standard=True)
        df = rendered.to_dataframe()
    except Exception:
        try:
            df = statement_obj.to_dataframe()
        except Exception:
            return ""

    if df is None or df.empty:
        return ""

    drop_cols = {"concept", "level", "abstract", "dimension"}
    columns = [c for c in df.columns if c not in drop_cols]
    if not columns:
        return ""

    rows = df[columns].fillna("").astype(str).values.tolist()
    return create_markdown_table(columns, rows)


def _dataframe_to_markdown(df) -> str:
    if df is None:
        return ""
    try:
        if df.empty:
            return ""
    except Exception:
        return ""

    try:
        df_out = df.copy()
    except Exception:
        df_out = df

    index_name = getattr(df_out.index, "name", None)
    is_range = df_out.index.__class__.__name__ == "RangeIndex"
    if index_name or not is_range:
        df_out = df_out.reset_index()
        first_col = df_out.columns[0]
        if first_col in ("index", None) or index_name is None:
            df_out = df_out.rename(columns={first_col: "label"})
        else:
            df_out = df_out.rename(columns={first_col: index_name})

    columns = [str(c) for c in df_out.columns]
    rows = df_out.fillna("").astype(str).values.tolist()
    return create_markdown_table(columns, rows)


def _report_to_markdown(report, section_title: Optional[str] = None) -> str:
    markdown = ""
    if hasattr(report, "to_dataframe"):
        try:
            df = report.to_dataframe()
        except Exception:
            df = None
        markdown = _dataframe_to_markdown(df)

    if markdown:
        return markdown

    content = getattr(report, "content", None)
    if not content and hasattr(report, "text"):
        content = report.text()
    return process_content(content, section_title=section_title)


_STATEMENT_ORDER = [
    "IncomeStatement",
    "BalanceSheet",
    "CashFlowStatement",
    "StatementOfEquity",
    "ComprehensiveIncome",
    "CoverPage",
]

_STATEMENT_TITLES = {
    "IncomeStatement": "Income Statement",
    "BalanceSheet": "Balance Sheet",
    "CashFlowStatement": "Cash Flow Statement",
    "StatementOfEquity": "Statement of Equity",
    "ComprehensiveIncome": "Comprehensive Income",
    "CoverPage": "Cover Page",
}

_STATEMENT_KEYWORDS = {
    "IncomeStatement": [
        "income statement",
        "statement of income",
        "statement of operations",
        "statement of earnings",
        "operations",
        "earnings",
        "profit and loss",
        "p&l",
    ],
    "BalanceSheet": [
        "balance sheet",
        "statement of financial position",
        "financial position",
    ],
    "CashFlowStatement": [
        "cash flow statement",
        "statement of cash flows",
        "cash flows",
    ],
    "StatementOfEquity": [
        "statement of equity",
        "statement of stockholders equity",
        "statement of shareholders equity",
        "stockholders equity",
        "shareholders equity",
    ],
    "ComprehensiveIncome": [
        "comprehensive income",
        "statement of comprehensive income",
    ],
    "CoverPage": [
        "cover page",
        "cover",
    ],
}


def _normalize_statement_name(statement_name: str) -> Optional[str]:
    if not statement_name:
        return None

    normalized = re.sub(r"[^a-z0-9]+", " ", statement_name.lower()).strip()
    if normalized in {"statements", "all statements", "all"}:
        return "AllStatements"

    for canonical, keywords in _STATEMENT_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return canonical

    return None


def _match_statement_reports(reports, canonical: str):
    keywords = _STATEMENT_KEYWORDS.get(canonical, [])
    if not keywords:
        return []

    matches = []
    for report in reports.get_by_category("Statements"):
        haystack = f"{report.short_name or ''} {report.long_name or ''}".lower()
        if any(keyword in haystack for keyword in keywords):
            matches.append(report)
    return matches


def _is_report_like(source) -> bool:
    if Report is not None:
        try:
            if isinstance(source, Report):
                return True
        except Exception:
            pass
    return hasattr(source, "content") and (
        hasattr(source, "short_name") or hasattr(source, "long_name")
    )


def _report_title(report) -> str:
    for attr in ("short_name", "long_name", "menu_category", "html_file_name"):
        value = getattr(report, attr, None)
        if value:
            return str(value)
    return "Report"


def _build_header(source) -> str:
    form = getattr(source, "form", None)
    accession_no = getattr(source, "accession_no", None)
    filing_date = getattr(source, "filing_date", None)
    if form and accession_no and filing_date:
        return f"START_DOCUMENT: {form} {accession_no} {filing_date}"
    if isinstance(source, Financials):
        return _financials_header(source)
    if _is_report_like(source):
        return f"START_DOCUMENT: Report {_report_title(source)}"
    return "START_DOCUMENT: SEC Data"


def _financials_header(financials: Financials) -> str:
    entity_name = None
    doc_type = None
    period_end = None
    xb = getattr(financials, "xb", None)
    if xb is not None:
        try:
            entity_info = xb.entity_info or {}
        except Exception:
            entity_info = {}
        entity_name = entity_info.get("entity_name") or getattr(xb, "entity_name", None)
        doc_type = entity_info.get("document_type")
        period_end = entity_info.get("document_period_end_date")
    parts = ["START_DOCUMENT: Financials"]
    if entity_name:
        parts.append(str(entity_name))
    if doc_type:
        parts.append(str(doc_type))
    if period_end:
        parts.append(str(period_end))
    return " ".join(parts)


# -----------------------------
# Identity / Text Utilities
# -----------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def is_noise_text(text: str) -> bool:
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
    t = clean_text(text).lower()
    if not t:
        return True
    return t in list(recent)[-window:]


# -----------------------------
# Table Pre-processing
# -----------------------------
def is_xbrl_metadata_table(soup_table) -> bool:
    text = soup_table.get_text().lower()

    if "namespace prefix" in text or "xbrli:string" in text:
        return True

    if "us-gaap_" in text:
        if "$" in text and re.search(r"20\d{2}", text):
            return False
        return True

    return False


def is_width_grid_row(tr) -> bool:
    tds = tr.find_all(["td", "th"])
    if not tds:
        return False
    if tr.get_text(strip=True):
        return False

    width_cells = 0
    for td in tds:
        style = (td.get("style") or "").lower()
        if "width" in style:
            width_cells += 1

    return width_cells >= 6 and (width_cells / max(1, len(tds))) >= 0.6


def preprocess_currency_cells(table_soup):
    rows = table_soup.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        i = 0
        while i < len(cells):
            cell = cells[i]
            txt = clean_text(cell.get_text())
            if txt in ["$"] and i + 1 < len(cells):
                next_cell = cells[i + 1]
                next_cell.string = txt + clean_text(next_cell.get_text())
                next_cell["colspan"] = str(int(next_cell.get("colspan", 1)) + 1)
                cell.decompose()
            i += 1


def preprocess_percent_cells(table_soup):
    rows = table_soup.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        i = len(cells) - 1
        while i > 0:
            cell = cells[i]
            txt = clean_text(cell.get_text())
            if txt in ["%", "%)", "pts"]:
                prev_cell = cells[i - 1]
                prev_txt = clean_text(prev_cell.get_text())
                if prev_txt:
                    prev_cell.string = prev_txt + txt
                    prev_cell["colspan"] = str(
                        int(prev_cell.get("colspan", 1))
                        + int(cell.get("colspan", 1))
                    )
                    cell.decompose()
            i -= 1


def build_row_values(cells, max_cols):
    row_values = []
    for cell in cells:
        try:
            colspan = int(cell.get("colspan", 1))
        except (TypeError, ValueError):
            colspan = 1
        txt = clean_text(cell.get_text(" ", strip=True)).replace("|", r"\|")
        row_values.append(txt)
        for _ in range(colspan - 1):
            row_values.append(txt)

    if len(row_values) < max_cols:
        row_values.extend([""] * (max_cols - len(row_values)))
    return row_values[:max_cols]


# -----------------------------
# JSON -> Markdown Logic
# -----------------------------
def _normalize_table_value(value: str) -> str:
    return clean_text(str(value)).lower()


def _table_signature(records, derived_title, max_rows: int = 8):
    if not records:
        return None
    keys = sorted({key for record in records for key in record.keys()})
    if not keys:
        return None
    row_sig = []
    for record in records[:max_rows]:
        row_sig.append(tuple(_normalize_table_value(record.get(key, "")) for key in keys))
    title_sig = _normalize_table_value(derived_title or "")
    return (title_sig, tuple(keys), tuple(row_sig), len(records))


def create_markdown_table(headers, rows):
    if not headers or not rows:
        return ""
    md = f"| {' | '.join(map(str, headers))} |\n"
    md += f"| {' | '.join(['---'] * len(headers))} |\n"
    for row in rows:
        padded_row = list(row) + [""] * (len(headers) - len(row))
        cleaned_row = [str(x) if x is not None else "" for x in padded_row]
        md += f"| {' | '.join(cleaned_row)} |\n"
    return md


def list_of_dicts_to_table(data_list):
    if not data_list:
        return ""
    all_keys = set().union(*(d.keys() for d in data_list))

    def natural_keys(text):
        return [
            int(c) if c.isdigit() else c.lower()
            for c in re.split(r"(\d+)", text)
        ]

    sorted_keys = sorted(list(all_keys), key=natural_keys)
    label_key = next(
        (k for k in sorted_keys if k.lower() in ["label", "metric", "name"]), None
    )

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

    if header_rows:
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
            best_key = max(
                candidate_keys,
                key=lambda k: sum(
                    1
                    for row in data_rows
                    if str(row.get(k, "")).strip() not in ["", "-"]
                ),
            )

            if sum(
                1 for row in data_rows if str(row.get(best_key, "")).strip()
            ) == 0:
                continue

            header_str = " - ".join([p for p in signature if p]) or best_key
            final_headers.append(header_str)
            final_keys.append(best_key)
    else:
        final_headers = sorted_keys
        final_keys = sorted_keys
        if label_key and label_key in final_headers:
            final_headers.insert(0, final_headers.pop(final_headers.index(label_key)))
            final_keys.insert(0, final_keys.pop(final_keys.index(label_key)))

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
            if idx == locked_index:
                keep_headers.append(header)
                keep_keys.append(key)
                continue

            values = tuple(
                _normalize_table_value(item.get(key, "")) for item in data_rows
            )
            if all(is_blank_value(value) for value in values):
                continue

            header_norm = _normalize_table_value(header)
            signature = (
                "" if is_placeholder_header(header) else header_norm,
                values,
            )
            if signature in seen:
                continue
            seen.add(signature)
            keep_headers.append(header)
            keep_keys.append(key)

        final_headers = keep_headers
        final_keys = keep_keys

    table_rows = []
    for item in data_rows:
        row = [item.get(k, "") for k in final_keys]
        table_rows.append(row)

    return create_markdown_table(final_headers, table_rows)


# -----------------------------
# HTML -> JSON Converter
# -----------------------------
def html_to_json(table_soup):
    table_soup_copy = BeautifulSoup(str(table_soup), "html.parser")
    preprocess_currency_cells(table_soup_copy)
    preprocess_percent_cells(table_soup_copy)

    rows = table_soup_copy.find_all("tr")
    if not rows:
        return None, [], None
    rows = [r for r in rows if not is_width_grid_row(r)]
    if not rows:
        return None, [], None

    max_cols = 0
    widths = []
    for row in rows:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        width = 0
        for cell in cells:
            try:
                colspan = int(cell.get("colspan", 1))
            except (TypeError, ValueError):
                colspan = 1
            width += colspan
        widths.append(width)
        max_cols = max(max_cols, width)

    if max_cols == 0:
        return None, [], None
    if len(widths) >= 5:
        sorted_widths = sorted(widths)
        p90 = sorted_widths[int(0.9 * (len(sorted_widths) - 1))]
        if p90 >= 2 and max_cols > p90 * 2:
            max_cols = p90

    matrix = []
    row_flags = []
    output_blocks = []

    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        row_has_th = any(cell.name == "th" for cell in cells)
        row_text = " ".join([c.get_text(" ", strip=True) for c in cells])

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
    if max_cols >= 50:
        total_cells = len(matrix) * max_cols
        filled = sum(1 for row in matrix for val in row if val.strip())
        if total_cells and (filled / total_cells) < 0.05:
            return output_blocks, [], None

    derived_title = None
    if len(matrix) > 1:
        first_row = matrix[0]
        unique_vals = set(v for v in first_row if v.strip())
        if len(unique_vals) == 1:
            title_candidate = list(unique_vals)[0]
            if 3 < len(title_candidate) < 150:
                derived_title = title_candidate
                matrix.pop(0)

    def is_numericish(s):
        return bool(re.search(r"[\d]", s)) or ("$" in s)

    def is_labelish(s):
        return bool(re.search(r"[A-Za-z]", s)) and not is_numericish(s)

    def is_date_heading(value: str) -> bool:
        if not value:
            return False
        value = value.strip()
        if _looks_like_date_heading(value):
            return True
        return bool(year_re.search(value))

    label_scores = []
    for c in range(max_cols):
        score = sum(1 for r in matrix if is_labelish(r[c]))
        label_scores.append(score)
    label_col = max(range(max_cols), key=lambda c: (label_scores[c], -c))

    year_re = re.compile(r"\b(20\d{2}|19\d{2})\b")

    records = []
    for row_index, row in enumerate(matrix):
        row_has_th = row_flags[row_index]
        record = {}
        is_header = row_has_th
        label_override = None
        label_source_col = None
        row_for_data = row

        for c in range(max_cols):
            if c == label_col:
                continue
            if row[c] == row[label_col]:
                continue
            if year_re.search(row[c]):
                is_header = True
                break

        label_text = (row[label_col] or "").lower()

        if not is_header and not label_text:
            data_values = [
                row[c]
                for c in range(max_cols)
                if c != label_col and row[c].strip()
            ]
            if data_values and len(set(data_values)) == 1:
                is_header = True
            elif data_values:
                has_numeric = any(is_numericish(value) for value in data_values)
                label_values = [value for value in data_values if is_labelish(value)]
                if label_values and len(set(label_values)) >= 2 and not has_numeric:
                    is_header = True

        if not row_has_th and label_text and any(
            is_numericish(row[c]) and not year_re.search(row[c])
            for c in range(max_cols)
            if c != label_col and row[c].strip()
        ):
            is_header = False
        if not row_has_th and (
            "balance" in label_text or "total" in label_text or "as of" in label_text
        ):
            is_header = False

        if is_header:
            label_value = (row[label_col] or "").strip()
            data_cols = [c for c in range(max_cols) if c != label_col]
            data_values = [row[c] for c in data_cols]
            if label_value and is_date_heading(label_value):
                if data_values and not data_values[-1].strip():
                    if any(is_date_heading(v) for v in data_values if v.strip()):
                        row_for_data = list(row)
                        shifted = [label_value] + data_values[:-1]
                        for c, value in zip(data_cols, shifted):
                            row_for_data[c] = value

        if not is_header and not label_text:
            for c in range(max_cols):
                if c == label_col:
                    continue
                if not row[c].strip():
                    continue
                if year_re.search(row[c]):
                    continue
                if is_labelish(row[c]):
                    label_override = row[c]
                    label_source_col = c
                    break

        if is_header:
            record["label"] = ""
        else:
            record["label"] = label_override or row[label_col]

        for c in range(max_cols):
            if c != label_col:
                if is_header:
                    record[f"col_{c}"] = row_for_data[c]
                elif c == label_source_col:
                    record[f"col_{c}"] = ""
                elif row_for_data[c] == row[label_col]:
                    record[f"col_{c}"] = ""
                else:
                    record[f"col_{c}"] = row_for_data[c]
        records.append(record)

    return output_blocks, records, derived_title


def _extract_bold_heading(element) -> Optional[str]:
    if element.name not in ["p", "div"]:
        return None
    if element.find("table"):
        return None
    bold_tags = element.find_all(["strong", "b"])
    bold_text = ""
    if bold_tags:
        bold_text = clean_text(
            " ".join(tag.get_text(" ", strip=True) for tag in bold_tags)
        )
    else:
        spans = element.find_all("span")
        if not spans:
            return None
        if not any(_span_is_bold(span) for span in spans):
            return None
        bold_text = clean_text(
            " ".join(span.get_text(" ", strip=True) for span in spans)
        )
    if not bold_text:
        return None
    full_text = clean_text(element.get_text(" ", strip=True))
    if full_text != bold_text:
        return None
    if len(full_text) > 120:
        return None
    if full_text.endswith("."):
        return None
    if _looks_like_date_heading(full_text):
        return None
    return full_text


def _span_is_bold(span) -> bool:
    style = (span.get("style") or "").lower()
    if "font-weight" not in style:
        return False
    match = re.search(r"font-weight\s*:\s*([^;]+)", style)
    if not match:
        return False
    value = match.group(1).strip()
    if value.isdigit():
        try:
            return int(value) >= 600
        except ValueError:
            return False
    return value in ["bold", "bolder"]


def _looks_like_date_heading(text: str) -> bool:
    date_patterns = [
        r"^[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}$",
        r"^\d{4}$",
    ]
    return any(re.fullmatch(pattern, text) for pattern in date_patterns)


# -----------------------------
# HTML Content Processing
# -----------------------------
def process_content(content, section_title=None):
    if not content:
        return ""

    raw_str = str(content)
    is_html = bool(re.search(r"<(table|div|p|h[1-6])", raw_str, re.IGNORECASE))

    if not is_html:
        return f"\n{raw_str.strip()}\n"

    soup = BeautifulSoup(raw_str, "html.parser")
    for tag in soup(["script", "style", "head", "meta"]):
        tag.decompose()

    output_parts = []
    processed_tables = set()
    table_signatures = set()
    recent_text = deque(maxlen=32)
    normalized_section = clean_text(section_title or "").lower()
    table_counter = 0

    elements = soup.find_all(
        ["p", "div", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6"]
    )

    for element in elements:
        if element.find_parent("table") in processed_tables:
            continue

        if element.name == "table":
            if element.find("table"):
                continue
            if is_xbrl_metadata_table(element):
                continue

            text_blocks, records, derived_title = html_to_json(element)

            for block in text_blocks:
                if block["type"] == "text" and not is_noise_text(block["content"]):
                    output_parts.append(block["content"])

            if records:
                signature = _table_signature(records, derived_title)
                if signature and signature in table_signatures:
                    processed_tables.add(element)
                    continue
                if signature:
                    table_signatures.add(signature)
                table_counter += 1
                md_table = list_of_dicts_to_table(records)
                if md_table:
                    header_str = (
                        f"#### Table: {derived_title}"
                        if derived_title
                        else f"#### Table {table_counter}: {section_title or 'Data'}"
                    )
                    output_parts.append(f"\n{header_str}\n{md_table}\n")

            processed_tables.add(element)
            continue

        if element.name in ["p", "div"]:
            heading_text = _extract_bold_heading(element)
            if heading_text:
                if normalized_section and heading_text.lower() == normalized_section:
                    continue
                if not is_noise_text(heading_text):
                    output_parts.append(f"\n### {heading_text}\n")
                continue

        if element.name in ["ul", "ol"]:
            lines = [
                f"- {clean_text(li.get_text())}"
                for li in element.find_all("li")
                if clean_text(li.get_text())
            ]
            if lines:
                output_parts.append("\n".join(lines))
            continue

        if element.name.startswith("h"):
            txt = clean_text(element.get_text())
            if txt and not is_noise_text(txt):
                output_parts.append(f"\n### {txt}\n")
            continue

        if element.find("table"):
            continue
        text = clean_text(element.get_text())
        if len(text) <= 5 or is_noise_text(text):
            continue
        if normalized_section and text.lower() == normalized_section:
            continue
        if should_skip_duplicate(text, recent_text):
            continue

        output_parts.append(text)
        recent_text.append(text.lower())

    return "\n\n".join(output_parts)


# -----------------------------
# Regex Boundary Extractor
# -----------------------------
def _build_item_pattern(item_name: str, form_type: Optional[str] = None) -> str:
    """Build a regex pattern for matching an item name.

    Handles variations like:
    - "Item 1" -> matches "Item 1", "ITEM 1", "Item  1"
    - "Item 1A" -> matches "Item 1A", "Item 1.A", "Item1A"
    - "Item 3D" -> matches "Item 3D", "Item 3.D" (for 20-F)
    - "Part II Item 1" -> matches variations for 10-Q
    """
    # Parse the item name
    match = re.match(r"(?i)((?:Part\s+(?:I+|[12])\s+)?Item)\s*(\d+)([A-Za-z]?)", item_name)
    if not match:
        # Fallback to simple replacement
        return item_name.replace(" ", r"\s+")

    prefix, num, suffix = match.groups()

    # Build flexible pattern
    if suffix:
        # Handle sub-items like "Item 1A" or "Item 3D"
        # Match: Item 1A, Item 1.A, Item1A, ITEM 1A, etc.
        pattern = rf"{prefix.replace(' ', r'\s*')}\s*{num}\.?\s*{suffix}"
    else:
        # Handle main items like "Item 1"
        # Match: Item 1, ITEM 1, Item  1, etc.
        pattern = rf"{prefix.replace(' ', r'\s*')}\s*{num}"

    # For 10-Q, also match "Part II" prefixed versions for Part II items
    if form_type and form_type.upper().startswith("10-Q"):
        if "Part II" in item_name or "Part 2" in item_name:
            # Already has Part prefix
            pass
        else:
            # Add optional Part prefix for matching
            pattern = rf"(?:Part\s+(?:II|2)\s+)?{pattern}"

    return pattern


def extract_item_with_boundaries(
    full_html: str,
    item_start: str,
    item_end_list: List[str],
    form_type: Optional[str] = None,
) -> Optional[str]:
    """Extract content between item boundaries using regex.

    Args:
        full_html: The complete HTML content to search
        item_start: The item name to find (e.g., "Item 7A")
        item_end_list: List of items that mark the end boundary
        form_type: Optional form type for form-specific pattern matching

    Returns:
        The extracted HTML content, or None if not found
    """
    # Build the start pattern
    # Note: (?:\s|<|:|&) handles whitespace, tags, colons, and HTML entities like &#160;
    start_pattern = _build_item_pattern(item_start, form_type)
    start_pat = re.compile(
        rf"(?:>|\n)\s*{start_pattern}\.?(?:\s|<|:|&)",
        re.IGNORECASE,
    )

    # Build the end pattern from all boundary items
    end_patterns = []
    for item in item_end_list:
        end_patterns.append(_build_item_pattern(item, form_type))

    end_pat_str = "|".join(end_patterns)
    end_pat = re.compile(
        rf"(?:>|\n)\s*(?:{end_pat_str})(?:\s|<|:|\.|\&)",
        re.IGNORECASE,
    )

    starts = [m for m in start_pat.finditer(full_html)]

    if not starts:
        return None

    candidates = []

    for start_match in starts:
        start_pos = start_match.start()
        tag_start = full_html.rfind("<", 0, start_pos)
        if tag_start != -1:
            start_pos = tag_start
        end_match = end_pat.search(full_html, pos=start_match.end())

        if end_match:
            end_pos = end_match.start()
            tag_end = full_html.rfind("<", start_match.end(), end_pos)
            if tag_end != -1:
                end_pos = tag_end
            content = full_html[start_pos:end_pos]
            candidates.append(content)

    if not candidates:
        return None

    return max(candidates, key=len)


# Legacy item boundaries - kept for backwards compatibility
# New code should use FORM_ITEM_REGISTRY instead
_ITEM_BOUNDARIES = {
    "Item 1": ["Item 1A", "Item 1B", "Item 2"],
    "Item 1A": ["Item 1B", "Item 2"],
    "Item 7": ["Item 7A", "Item 8"],
    "Item 7A": ["Item 8"],
    "Item 8": ["Item 9", "Item 9A"],
}
