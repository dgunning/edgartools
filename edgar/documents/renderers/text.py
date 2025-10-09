"""
Plain text renderer for parsed documents.
"""

from typing import Optional
from edgar.documents.document import Document
from edgar.documents.extractors.text_extractor import TextExtractor


class TextRenderer:
    """
    Renders parsed documents to plain text.
    
    This is a simple wrapper around TextExtractor for consistency
    with other renderers.
    """
    
    def __init__(self,
                 clean: bool = True,
                 include_tables: bool = True,
                 max_length: Optional[int] = None,
                 preserve_structure: bool = False):
        """
        Initialize text renderer.
        
        Args:
            clean: Clean and normalize text
            include_tables: Include table content
            max_length: Maximum text length
            preserve_structure: Preserve document structure
        """
        self.extractor = TextExtractor(
            clean=clean,
            include_tables=include_tables,
            include_metadata=False,
            include_links=False,
            max_length=max_length,
            preserve_structure=preserve_structure
        )
    
    def render(self, document: Document) -> str:
        """
        Render document to plain text.
        
        Args:
            document: Document to render
            
        Returns:
            Plain text
        """
        return self.extractor.extract(document)