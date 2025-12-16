"""Filing structure definitions and validation utilities."""
from typing import Dict, List, Optional, Pattern

__all__ = ['FilingStructure', 'ItemOnlyFilingStructure', 'is_valid_item_for_filing', 'extract_items_from_sections']


class FilingStructure:

    def __init__(self, structure: Dict):
        self.structure = structure

    def get_part(self, part: str):
        return self.structure.get(part.upper())

    def get_item(self, item: str, part: Optional[str] = None):
        item = item.upper()
        if part:
            part_dict = self.get_part(part)
            if part_dict:
                return part_dict.get(item)
        else:
            for _, items in self.structure.items():
                if item in items:
                    return items[item]
        return None

    def is_valid_item(self, item: str, part: Optional[str] = None):
        return self.get_item(item, part) is not None


class ItemOnlyFilingStructure(FilingStructure):

    def get_part(self, part: str):
        return None

    def get_item(self, item: str, part: Optional[str] = None):
        return self.structure.get(item.upper())


def is_valid_item_for_filing(filing_structure: Dict, item: str, part: Optional[str] = None):
    """Return true if the item is valid"""
    item = item.upper()
    if part:
        part_dict = filing_structure.get(part.upper())
        if part_dict:
            return item in part_dict
    else:
        for _, items in filing_structure.items():
            if item in items:
                return True
    return False


def extract_items_from_sections(sections: Dict, item_pattern: Pattern[str]) -> List[str]:
    r"""
    Extract item numbers from filing sections using a regex pattern.

    This is a shared utility to eliminate code duplication between different
    filing types (8-K, 20-F, etc.) that have similar item extraction logic.

    Args:
        sections: Dictionary of sections with titles
        item_pattern: Compiled regex pattern to match item numbers in titles
                     (e.g., r'(Item\s+\d+\.\s*\d+)' for 8-K, r'(Item\s+\d+[A-Z]?)' for 20-F)

    Returns:
        List of extracted item strings (e.g., ["Item 2.02", "Item 9.01"])

    Examples:
        >>> pattern = re.compile(r'(Item\s+\d+\.\s*\d+)', re.IGNORECASE)
        >>> sections = {'item_2_02': Section(title='Item 2.02 - Results')}
        >>> extract_items_from_sections(sections, pattern)
        ['Item 2.02']
    """
    items = []
    for section in sections.values():
        title = section.title
        # Try to extract item number using the provided pattern
        match = item_pattern.match(title)
        if match:
            items.append(match.group(1))
        else:
            # Fallback: use first part of title before " - " or use full title
            if ' - ' in title:
                items.append(title.split(' - ')[0].strip())
            else:
                items.append(title)
    return items
