"""
Custom exceptions for the HTML parser.
"""

from typing import Optional, Dict, Any


class ParsingError(Exception):
    """Base exception for parsing errors."""
    
    def __init__(self, 
                 message: str, 
                 context: Optional[Dict[str, Any]] = None,
                 suggestions: Optional[list] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.suggestions = suggestions or []
    
    def __str__(self):
        result = self.message
        if self.context:
            result += f"\nContext: {self.context}"
        if self.suggestions:
            result += f"\nSuggestions: {', '.join(self.suggestions)}"
        return result


class HTMLParsingError(ParsingError):
    """Error parsing HTML structure."""
    pass


class StyleParsingError(ParsingError):
    """Error parsing CSS styles."""
    pass


class XBRLParsingError(ParsingError):
    """Error parsing inline XBRL."""
    pass


class TableParsingError(ParsingError):
    """Error parsing table structure."""
    pass


class SectionDetectionError(ParsingError):
    """Error detecting document sections."""
    pass


class DocumentTooLargeError(ParsingError):
    """Document exceeds maximum size."""
    
    def __init__(self, size: int, max_size: int):
        super().__init__(
            f"Document size ({size:,} bytes) exceeds maximum ({max_size:,} bytes)",
            context={'size': size, 'max_size': max_size},
            suggestions=[
                "Use streaming parser for large documents",
                "Increase max_document_size in configuration",
                "Split document into smaller parts"
            ]
        )


class InvalidConfigurationError(ParsingError):
    """Invalid parser configuration."""
    pass


class NodeNotFoundError(ParsingError):
    """Requested node not found in document."""
    pass


class ExtractionError(ParsingError):
    """Error extracting content from document."""
    pass