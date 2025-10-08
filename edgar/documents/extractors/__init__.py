"""
Content extractors for documents.
"""

from edgar.documents.extractors.section_extractor import SectionExtractor
from edgar.documents.extractors.text_extractor import TextExtractor
from edgar.documents.extractors.toc_section_detector import TOCSectionDetector
from edgar.documents.extractors.heading_section_detector import HeadingSectionDetector

__all__ = [
    'TextExtractor',
    'SectionExtractor',
    'TOCSectionDetector',
    'HeadingSectionDetector'
]
