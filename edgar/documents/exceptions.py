"""
Custom exceptions for the HTML parser.
"""

# ParsingError is one of the four branches of the tree in edgar.exceptions
# (bead edgartools-07lk.10). Its message/context/suggestions shape moved up into
# EdgarError, so the subclasses below re-base with no change to their
# signatures. Imported rather than redefined: same object, so every existing
# `except ParsingError:` and `from edgar.documents.exceptions import
# ParsingError` keeps working.
from edgar.exceptions import ParsingError


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
