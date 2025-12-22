"""
Document processors for preprocessing and postprocessing.
"""

from edgar.documents.processors.postprocessor import DocumentPostprocessor
from edgar.documents.processors.preprocessor import HTMLPreprocessor

__all__ = [
    'HTMLPreprocessor',
    'DocumentPostprocessor'
]
