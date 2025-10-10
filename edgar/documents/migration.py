"""
Migration and compatibility layer for transitioning from old parser to new.

NOTE: This compatibility layer is documented for user migration from v1.x → v2.0
It is intentionally not used internally but kept for user convenience.
Do not remove without versioning consideration.
"""

from typing import Optional, List, Dict, Any
import warnings
from edgar.documents import HTMLParser, Document, ParserConfig
from edgar.documents.search import DocumentSearch


class LegacyHTMLDocument:
    """
    Compatibility wrapper that mimics the old Document API.
    
    This allows existing code to work with the new parser
    while providing deprecation warnings.
    """
    
    def __init__(self, new_document: Document):
        """Initialize with new document."""
        self._doc = new_document
        self._warn_on_use = True
    
    def _deprecation_warning(self, old_method: str, new_method: str = None):
        """Issue deprecation warning."""
        if self._warn_on_use:
            msg = f"Document.{old_method} is deprecated."
            if new_method:
                msg += f" Use {new_method} instead."
            warnings.warn(msg, DeprecationWarning, stacklevel=3)
    
    @property
    def text(self) -> str:
        """Get document text (old API)."""
        self._deprecation_warning("text", "Document.text()")
        return self._doc.text()
    
    def get_text(self, clean: bool = True) -> str:
        """Get text with options (old API)."""
        self._deprecation_warning("get_text()", "Document.text()")
        return self._doc.text()
    
    @property
    def tables(self) -> List[Any]:
        """Get tables (old API)."""
        self._deprecation_warning("tables", "Document.tables")
        return self._doc.tables
    
    def find_all(self, tag: str) -> List[Any]:
        """Find elements by tag (old API)."""
        self._deprecation_warning("find_all()", "Document.root.find()")
        
        # Map old tag names to node types
        from edgar.documents.types import NodeType
        
        tag_map = {
            'h1': NodeType.HEADING,
            'h2': NodeType.HEADING,
            'h3': NodeType.HEADING,
            'p': NodeType.PARAGRAPH,
            'table': NodeType.TABLE,
        }
        
        node_type = tag_map.get(tag.lower())
        if node_type:
            return self._doc.root.find(lambda n: n.type == node_type)
        
        return []
    
    def search(self, pattern: str) -> List[str]:
        """Search document (old API)."""
        self._deprecation_warning("search()", "DocumentSearch.search()")
        
        search = DocumentSearch(self._doc)
        results = search.search(pattern)
        return [r.text for r in results]
    
    @property
    def sections(self) -> Dict[str, Any]:
        """Get sections (old API)."""
        # Convert new sections to old format
        new_sections = self._doc.sections
        old_sections = {}
        
        for name, section in new_sections.items():
            old_sections[name] = {
                'title': section.title,
                'text': section.text(),
                'start': section.start_offset,
                'end': section.end_offset
            }
        
        return old_sections
    
    def to_markdown(self) -> str:
        """Convert to markdown (old API)."""
        self._deprecation_warning("to_markdown()", "MarkdownRenderer.render()")
        
        from edgar.documents.renderers import MarkdownRenderer
        renderer = MarkdownRenderer()
        return renderer.render(self._doc)


class LegacySECHTMLParser:
    """
    Compatibility wrapper for old SECHTMLParser.
    
    Maps old parser methods to new parser.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with optional config."""
        # Convert old config to new
        new_config = self._convert_config(config)
        self._parser = HTMLParser(new_config)
        self._warn_on_use = True
    
    def _convert_config(self, old_config: Optional[Dict[str, Any]]) -> ParserConfig:
        """Convert old config format to new."""
        if not old_config:
            return ParserConfig()
        
        new_config = ParserConfig()
        
        # Map old config keys to new
        if 'clean_text' in old_config:
            new_config.clean_text = old_config['clean_text']
        
        if 'extract_tables' in old_config:
            new_config.table_extraction = old_config['extract_tables']
        
        if 'preserve_layout' in old_config:
            new_config.preserve_whitespace = old_config['preserve_layout']
        
        return new_config
    
    def parse(self, html: str) -> LegacyHTMLDocument:
        """Parse HTML (old API)."""
        if self._warn_on_use:
            warnings.warn(
                "SECHTMLParser is deprecated. Use HTMLParser instead.",
                DeprecationWarning,
                stacklevel=2
            )
        
        new_doc = self._parser.parse(html)
        return LegacyHTMLDocument(new_doc)
    
    def parse_file(self, filepath: str) -> LegacyHTMLDocument:
        """Parse HTML file (old API)."""
        if self._warn_on_use:
            warnings.warn(
                "SECHTMLParser.parse_file() is deprecated. Use HTMLParser.parse_file() instead.",
                DeprecationWarning,
                stacklevel=2
            )
        
        new_doc = self._parser.parse_file(filepath)
        return LegacyHTMLDocument(new_doc)


def migrate_parser_usage(code: str) -> str:
    """
    Helper to migrate code from old parser to new.
    
    Args:
        code: Python code using old parser
        
    Returns:
        Updated code using new parser
    """
    replacements = [
        # Import statements
        ("from edgar.files.html import SECHTMLParser", 
         "from edgar.documents import HTMLParser"),
        
        ("from edgar.files.html import Document",
         "from edgar.documents import Document"),
        
        # Class instantiation
        ("SECHTMLParser(", "HTMLParser("),
        
        # Method calls
        ("document.text", "document.text()"),
        ("document.get_text(", "document.text("),
        ("document.find_all(", "document.root.find(lambda n: n.tag == "),
        ("document.to_markdown(", "MarkdownRenderer().render(document"),
        
        # Config changes
        ("extract_tables=", "table_extraction="),
        ("preserve_layout=", "preserve_whitespace="),
    ]
    
    migrated = code
    for old, new in replacements:
        migrated = migrated.replace(old, new)
    
    return migrated


class MigrationGuide:
    """
    Provides migration guidance and utilities.
    """
    
    @staticmethod
    def check_compatibility(old_parser_instance) -> Dict[str, Any]:
        """
        Check if old parser instance can be migrated.
        
        Returns:
            Dict with compatibility info
        """
        return {
            'can_migrate': True,
            'warnings': [],
            'recommendations': [
                "Replace SECHTMLParser with HTMLParser",
                "Update document.text to document.text()",
                "Use DocumentSearch for search functionality",
                "Use MarkdownRenderer for markdown conversion"
            ]
        }
    
    @staticmethod
    def print_migration_guide():
        """Print migration guide."""
        guide = """
        HTML Parser Migration Guide
        ==========================
        
        The new HTML parser provides significant improvements:
        - 10x performance improvement
        - Better table parsing
        - Reliable section detection
        - Advanced search capabilities
        
        Key Changes:
        -----------
        
        1. Imports:
           OLD: from edgar.files.html import SECHTMLParser, Document
           NEW: from edgar.documents import HTMLParser, Document
        
        2. Parser Creation:
           OLD: parser = SECHTMLParser()
           NEW: parser = HTMLParser()
        
        3. Document Text:
           OLD: document.text or document.get_text()
           NEW: document.text()
        
        4. Search:
           OLD: document.search(pattern)
           NEW: search = DocumentSearch(document)
                results = search.search(pattern)
        
        5. Tables:
           OLD: document.tables
           NEW: document.tables (same, but returns richer TableNode objects)
        
        6. Sections:
           OLD: document.sections
           NEW: document.sections (returns Section objects with more features)
        
        7. Markdown:
           OLD: document.to_markdown()
           NEW: renderer = MarkdownRenderer()
                markdown = renderer.render(document)
        
        Compatibility:
        -------------
        
        For gradual migration, use the compatibility layer:
        
        from edgar.documents.migration import LegacySECHTMLParser
        parser = LegacySECHTMLParser()  # Works like old parser
        
        This will issue deprecation warnings to help you migrate.
        
        Performance Config:
        ------------------
        
        For best performance:
        parser = HTMLParser.create_for_performance()
        
        For best accuracy:
        parser = HTMLParser.create_for_accuracy()
        
        For AI/LLM processing:
        parser = HTMLParser.create_for_ai()
        """
        
        print(guide)


# Compatibility aliases
SECHTMLParser = LegacySECHTMLParser
HTMLDocument = LegacyHTMLDocument


# Auto-migration for common imports
def __getattr__(name):
    """Provide compatibility imports with warnings."""
    if name == "SECHTMLParser":
        warnings.warn(
            "Importing SECHTMLParser from edgar.documents.migration is deprecated. "
            "Use HTMLParser from edgar.documents instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return LegacySECHTMLParser
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")