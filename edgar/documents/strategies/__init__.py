"""
Parsing strategies for different content types.
"""

from edgar.documents.strategies.document_builder import DocumentBuilder
from edgar.documents.strategies.header_detection import HeaderDetectionStrategy
from edgar.documents.strategies.table_processing import TableProcessor
from edgar.documents.strategies.xbrl_extraction import XBRLExtractor

__all__ = [
    'DocumentBuilder',
    'HeaderDetectionStrategy', 
    'TableProcessor',
    'XBRLExtractor'
]