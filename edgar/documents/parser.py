"""
Main HTML parser implementation.
"""

import time
from typing import List, Union

import lxml.html
from lxml import etree
from lxml.html import HtmlElement

from edgar.documents.config import ParserConfig
from edgar.documents.document import Document, DocumentMetadata
from edgar.documents.exceptions import (
    HTMLParsingError, DocumentTooLargeError, InvalidConfigurationError
)
from edgar.documents.nodes import DocumentNode
from edgar.documents.processors.postprocessor import DocumentPostprocessor
from edgar.documents.processors.preprocessor import HTMLPreprocessor
from edgar.documents.strategies.document_builder import DocumentBuilder
from edgar.documents.types import XBRLFact
from edgar.documents.utils import get_cache_manager
from edgar.documents.utils.html_utils import remove_xml_declaration, create_lxml_parser


class HTMLParser:
    """
    Main HTML parser class.
    
    Orchestrates the parsing pipeline with configurable strategies
    and processors.
    """
    
    def __init__(self, config: ParserConfig = None):
        """
        Initialize parser with configuration.
        
        Args:
            config: Parser configuration
        """
        self.config = config or ParserConfig()
        self._validate_config()
        
        # Initialize components
        self.cache_manager = get_cache_manager()
        self.preprocessor = HTMLPreprocessor(self.config)
        self.postprocessor = DocumentPostprocessor(self.config)
        
        # Initialize strategies
        self._init_strategies()
    
    def _validate_config(self):
        """Validate configuration."""
        if self.config.max_document_size <= 0:
            raise InvalidConfigurationError("max_document_size must be positive")
        
        if self.config.streaming_threshold and self.config.max_document_size:
            if self.config.streaming_threshold > self.config.max_document_size:
                raise InvalidConfigurationError(
                    "streaming_threshold cannot exceed max_document_size"
                )
    
    def _init_strategies(self):
        """Initialize parsing strategies based on configuration."""
        self.strategies = {}
        
        # Header detection strategy
        if self.config.detect_sections:
            from edgar.documents.strategies.header_detection import HeaderDetectionStrategy
            self.strategies['header_detection'] = HeaderDetectionStrategy(self.config)
        
        # Table processing strategy
        if self.config.table_extraction:
            from edgar.documents.strategies.table_processing import TableProcessor
            self.strategies['table_processing'] = TableProcessor(self.config)
        
        # XBRL extraction strategy
        if self.config.extract_xbrl:
            from edgar.documents.strategies.xbrl_extraction import XBRLExtractor
            self.strategies['xbrl_extraction'] = XBRLExtractor()
    
    def parse(self, html: Union[str, bytes]) -> Document:
        """
        Parse HTML into Document.
        
        Args:
            html: HTML content as string or bytes
            
        Returns:
            Parsed Document object
            
        Raises:
            DocumentTooLargeError: If document exceeds size limit
            HTMLParsingError: If parsing fails
        """
        start_time = time.time()
        
        # Validate input type
        if html is None:
            raise TypeError("HTML input cannot be None")

        if not isinstance(html, (str, bytes)):
            raise TypeError(f"HTML must be string or bytes, got {type(html).__name__}")

        # Convert bytes to string if needed
        if isinstance(html, bytes):
            html = html.decode('utf-8', errors='replace')

        # Handle empty HTML
        if not html.strip():
            # Return empty document
            root = DocumentNode()
            metadata = DocumentMetadata(
                size=0,
                parse_time=time.time() - start_time,
                parser_version="2.0.0"
            )
            return Document(root=root, metadata=metadata)
        
        # Check document size
        doc_size = len(html.encode('utf-8'))
        if doc_size > self.config.max_document_size:
            raise DocumentTooLargeError(doc_size, self.config.max_document_size)
        
        # Check if streaming is needed
        if doc_size > self.config.streaming_threshold:
            return self._parse_streaming(html)
        
        try:
            # Store original HTML BEFORE preprocessing (needed for TOC analysis)
            original_html = html

            # Extract XBRL data BEFORE preprocessing (to preserve ix:hidden content)
            xbrl_facts = []
            if self.config.extract_xbrl:
                xbrl_facts = self._extract_xbrl_pre_process(html)

            # Preprocessing (will remove ix:hidden for rendering)
            html = self.preprocessor.process(html)
            
            # Parse with lxml
            tree = self._parse_html(html)
            
            # Extract metadata
            metadata = self._extract_metadata(tree, html)
            metadata.preserve_whitespace = self.config.preserve_whitespace

            # Store ORIGINAL unmodified HTML for section extraction (TOC analysis)
            # Must be the raw HTML before preprocessing
            metadata.original_html = original_html

            # Add XBRL facts to metadata if found
            if xbrl_facts:
                metadata.xbrl_data = {'facts': xbrl_facts}
            
            # Build document
            document = self._build_document(tree, metadata)

            # Store config reference for section extraction
            document._config = self.config

            # Postprocessing
            document = self.postprocessor.process(document)
            
            # Record parse time
            document.metadata.parse_time = time.time() - start_time
            document.metadata.size = doc_size
            
            return document
            
        except Exception as e:
            if isinstance(e, (DocumentTooLargeError, HTMLParsingError)):
                raise
            raise HTMLParsingError(
                f"Failed to parse HTML: {str(e)}",
                context={'error_type': type(e).__name__}
            )
    
    def _parse_html(self, html: str) -> HtmlElement:
        """Parse HTML with lxml."""
        try:
            # Remove XML declaration if present
            html = remove_xml_declaration(html)

            parser = create_lxml_parser(
                remove_blank_text=not self.config.preserve_whitespace,
                remove_comments=True,
                recover=True,
                encoding='utf-8'
            )
            
            # Parse HTML
            tree = lxml.html.fromstring(html, parser=parser)
            
            # Ensure we have a proper document structure
            if tree.tag != 'html':
                # Wrap in html/body if needed
                html_tree = lxml.html.Element('html')
                body = etree.SubElement(html_tree, 'body')
                body.append(tree)
                tree = html_tree
            
            return tree
            
        except Exception as e:
            raise HTMLParsingError(
                f"lxml parsing failed: {str(e)}",
                context={'parser': 'lxml.html'}
            )
    
    def _extract_metadata(self, tree: HtmlElement, html: str) -> DocumentMetadata:
        """Extract metadata from HTML tree."""
        metadata = DocumentMetadata()
        
        # Use filing type from config if provided (avoids expensive detection)
        if self.config.form:
            metadata.form = self.config.form
        
        # Try to extract from meta tags
        for meta in tree.xpath('//meta'):
            name = meta.get('name', '').lower()
            content = meta.get('content', '')
            
            if name == 'company':
                metadata.company = content
            elif name == 'filing-type':
                metadata.form = content
            elif name == 'cik':
                metadata.cik = content
            elif name == 'filing-date':
                metadata.filing_date = content
            elif name == 'accession-number':
                metadata.accession_number = content
        
        # Try to extract from title
        title_elem = tree.find('.//title')
        if title_elem is not None and title_elem.text:
            # Parse title for filing info
            title = title_elem.text.strip()
            # Example: "APPLE INC - 10-K - 2023-09-30"
            parts = title.split(' - ')
            if len(parts) >= 2:
                if not metadata.company:
                    metadata.company = parts[0].strip()
                if not metadata.form:
                    metadata.form = parts[1].strip()
        
        # Try to extract from document content
        if not metadata.form:
            # Look for form type in first 1000 chars
            text_start = html[:1000].upper()
            for form_type in ['10-K', '10-Q', '8-K', 'DEF 14A', 'S-1']:
                if form_type in text_start:
                    metadata.form = form_type
                    break
        
        return metadata
    
    def _build_document(self, tree: HtmlElement, metadata: DocumentMetadata) -> Document:
        """Build document from parsed tree."""
        # Create document builder with strategies
        builder = DocumentBuilder(self.config, self.strategies)
        
        # Build document node tree
        root_node = builder.build(tree)
        
        # Create document
        document = Document(root=root_node, metadata=metadata)
        
        return document
    
    def _parse_streaming(self, html: str) -> Document:
        """Parse large document in streaming mode."""
        from edgar.documents.utils.streaming import StreamingParser
        
        streaming_parser = StreamingParser(self.config, self.strategies)
        return streaming_parser.parse(html)
    
    def _extract_xbrl_pre_process(self, html: str) -> List[XBRLFact]:
        """
        Extract XBRL facts before preprocessing.
        This ensures we capture XBRL data from ix:hidden elements.
        """
        try:
            # Parse HTML without preprocessing to preserve all XBRL content
            parser = create_lxml_parser(
                remove_blank_text=False,
                remove_comments=False,
                recover=True,
                encoding='utf-8'
            )
            
            # Remove XML declaration if present
            html = remove_xml_declaration(html)

            tree = lxml.html.fromstring(html, parser=parser)
            
            # Use XBRL extractor
            from edgar.documents.strategies.xbrl_extraction import XBRLExtractor
            extractor = XBRLExtractor()
            
            facts = []
            
            # Find all XBRL elements (including those in ix:hidden)
            # Simple approach: find all elements with ix: prefix
            for element in tree.iter():
                if element.tag and isinstance(element.tag, str) and 'ix:' in element.tag.lower():
                    # Skip container elements
                    local_name = element.tag.split(':')[-1].lower() if ':' in element.tag else element.tag.lower()
                    if local_name in ['nonnumeric', 'nonfraction', 'continuation', 'footnote', 'fraction']:
                        fact = extractor.extract_fact(element)
                        if fact:
                            # Mark if fact was in hidden section or header
                            parent = element.getparent()
                            while parent is not None:
                                if parent.tag:
                                    tag_lower = parent.tag.lower()
                                    if 'ix:hidden' in tag_lower or 'ix:header' in tag_lower:
                                        fact.metadata = fact.metadata or {}
                                        fact.metadata['hidden'] = True
                                        break
                                parent = parent.getparent()
                            facts.append(fact)
            
            return facts
            
        except Exception as e:
            # Log error but don't fail parsing
            import logging
            logging.warning(f"Failed to extract XBRL data: {e}")
            return []
    
    def parse_file(self, file_path: str) -> Document:
        """
        Parse HTML from file.
        
        Args:
            file_path: Path to HTML file
            
        Returns:
            Parsed Document object
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            html = f.read()
        
        document = self.parse(html)
        document.metadata.source = file_path
        
        return document
    
    def parse_url(self, url: str) -> Document:
        """
        Parse HTML from URL.
        
        Args:
            url: URL to fetch and parse
            
        Returns:
            Parsed Document object
        """
        import requests
        
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        document = self.parse(response.text)
        document.metadata.url = url
        
        return document
    
    @classmethod
    def create_for_performance(cls) -> 'HTMLParser':
        """Create parser optimized for performance."""
        config = ParserConfig.for_performance()
        return cls(config)
    
    @classmethod
    def create_for_accuracy(cls) -> 'HTMLParser':
        """Create parser optimized for accuracy."""
        config = ParserConfig.for_accuracy()
        return cls(config)
    
    @classmethod
    def create_for_ai(cls) -> 'HTMLParser':
        """Create parser optimized for AI processing."""
        config = ParserConfig.for_ai()
        return cls(config)