"""
Content extractors for documents.
"""

from edgar.documents.extractors.section_extractor import SectionExtractor
from edgar.documents.extractors.text_extractor import TextExtractor

__all__ = [
    'TextExtractor',
    'SectionExtractor'
]
