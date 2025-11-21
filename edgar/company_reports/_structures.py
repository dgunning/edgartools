"""Filing structure definitions and validation utilities."""
from typing import Dict

__all__ = ['FilingStructure', 'ItemOnlyFilingStructure', 'is_valid_item_for_filing']


class FilingStructure:

    def __init__(self, structure: Dict):
        self.structure = structure

    def get_part(self, part: str):
        return self.structure.get(part.upper())

    def get_item(self, item: str, part: str = None):
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

    def is_valid_item(self, item: str, part: str = None):
        return self.get_item(item, part) is not None


class ItemOnlyFilingStructure(FilingStructure):

    def get_part(self, part: str):
        return None

    def get_item(self, item: str, part: str = None):
        return self.structure.get(item.upper())


def is_valid_item_for_filing(filing_structure: Dict, item: str, part: str = None):
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
