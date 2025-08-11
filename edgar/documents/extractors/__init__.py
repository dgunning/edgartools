"""
Content extractors for documents.
"""

from edgar.documents.extractors.text_extractor import TextExtractor
from edgar.documents.extractors.section_extractor import SectionExtractor

__all__ = [
    'TextExtractor',
    'SectionExtractor'
]