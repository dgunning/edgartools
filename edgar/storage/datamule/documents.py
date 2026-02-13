"""
Datamule document adapter.

Datamule tar files contain raw document content (HTML, XML, etc.) — not wrapped
in SGML tags. TarSGMLDocument subclasses SGMLDocument to serve the content
directly without SGML tag extraction.
"""

from dataclasses import dataclass

from edgar.sgml.sgml_parser import SGMLDocument

__all__ = ['TarSGMLDocument']


@dataclass
class TarSGMLDocument(SGMLDocument):
    """
    An SGMLDocument whose content comes directly from a datamule tar file.

    Unlike standard SGMLDocuments parsed from SGML-wrapped text, the content
    is the raw file bytes/text — no <TEXT>, <HTML>, or <XML> extraction needed.
    """

    @classmethod
    def create(cls, *, sequence: str, type: str, filename: str, description: str, raw_content: str) -> 'TarSGMLDocument':
        """Create a TarSGMLDocument with raw content (no SGML tag wrapping)."""
        doc = cls(
            sequence=sequence,
            type=type,
            filename=filename,
            description=description,
            _content_ref=raw_content,
            _content_start=0,
            _content_end=len(raw_content),
        )
        return doc

    @property
    def content(self):
        """Return raw content directly — datamule files have no SGML tag wrapping."""
        return self.raw_content
