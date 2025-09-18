"""
Streaming parser for large HTML documents.
"""

import io
from typing import Any, Dict

from lxml import etree
from lxml.html import HtmlElement

from edgar.documents.config import ParserConfig
from edgar.documents.document import Document, DocumentMetadata
from edgar.documents.exceptions import DocumentTooLargeError, HTMLParsingError
from edgar.documents.nodes import ContainerNode, DocumentNode, HeadingNode, ParagraphNode, SectionNode, TextNode
from edgar.documents.table_nodes import TableNode
from edgar.documents.types import SemanticType


class StreamingParser:
    """
    Streaming parser for large HTML documents.

    Processes documents in chunks to minimize memory usage
    while maintaining parse quality.
    """

    # Chunk size for streaming (1MB)
    CHUNK_SIZE = 1024 * 1024

    # Maximum node buffer before flush
    MAX_NODE_BUFFER = 1000

    def __init__(self, config: ParserConfig, strategies: Dict[str, Any]):
        """
        Initialize streaming parser.

        Args:
            config: Parser configuration
            strategies: Parsing strategies to use
        """
        self.config = config
        self.strategies = strategies
        self._reset_state()

    def _reset_state(self):
        """Reset parser state."""
        self.current_section = None
        self.node_buffer = []
        self.metadata = DocumentMetadata()
        self.root = DocumentNode()
        self.current_parent = self.root
        self.tag_stack = []
        self.text_buffer = []
        self.in_table = False
        self.table_buffer = []
        self.bytes_processed = 0

    def parse(self, html: str) -> Document:
        """
        Parse HTML in streaming mode.

        Args:
            html: HTML content to parse

        Returns:
            Parsed Document

        Raises:
            DocumentTooLargeError: If document exceeds size limit
            HTMLParsingError: If parsing fails
        """
        self._reset_state()

        try:
            # Create streaming parser
            parser = etree.iterparse(
                io.BytesIO(html.encode('utf-8')),
                events=('start', 'end'),
                html=True,
                recover=True,
                encoding='utf-8'
            )

            # Process events
            for event, elem in parser:
                self._process_event(event, elem)

                # Check size limit
                self.bytes_processed += len(etree.tostring(elem, encoding='unicode', method='html'))
                if self.bytes_processed > self.config.max_document_size:
                    raise DocumentTooLargeError(self.bytes_processed, self.config.max_document_size)

                # Flush buffer if needed
                if len(self.node_buffer) >= self.MAX_NODE_BUFFER:
                    self._flush_buffer()

                # Clean up processed elements to save memory
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

            # Final flush
            self._flush_buffer()

            # Create document
            document = Document(root=self.root, metadata=self.metadata)

            # Apply post-processing
            from edgar.documents.processors.postprocessor import DocumentPostprocessor
            postprocessor = DocumentPostprocessor(self.config)
            document = postprocessor.process(document)

            return document

        except etree.ParseError as e:
            raise HTMLParsingError(f"Streaming parse failed: {str(e)}") from e
        except Exception as e:
            if isinstance(e, (DocumentTooLargeError, HTMLParsingError)):
                raise
            raise HTMLParsingError(f"Unexpected error during streaming parse: {str(e)}") from e

    def _process_event(self, event: str, elem: HtmlElement):
        """Process a parse event."""
        if event == 'start':
            self._handle_start_tag(elem)
        elif event == 'end':
            self._handle_end_tag(elem)

    def _handle_start_tag(self, elem: HtmlElement):
        """Handle opening tag."""
        tag = elem.tag.lower()

        # Track tag stack
        self.tag_stack.append(tag)

        # Extract metadata from early elements
        if tag == 'title' and elem.text:
            self._extract_title_metadata(elem.text)
        elif tag == 'meta':
            self._extract_meta_metadata(elem)

        # Handle specific tags
        if tag == 'body':
            # Create a container for body content
            body_container = ContainerNode(tag_name='body')
            self.root.add_child(body_container)
            self.current_parent = body_container
        elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self._start_heading(elem)
        elif tag == 'p':
            self._start_paragraph(elem)
        elif tag == 'table':
            self._start_table(elem)
        elif tag == 'section':
            self._start_section(elem)

    def _handle_end_tag(self, elem: HtmlElement):
        """Handle closing tag."""
        tag = elem.tag.lower()

        # Remove from tag stack
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

        # Handle specific tags
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self._end_heading(elem)
        elif tag == 'p':
            self._end_paragraph(elem)
        elif tag == 'table':
            self._end_table(elem)
        elif tag == 'section':
            self._end_section(elem)
        elif tag == 'body':
            # When body ends, flush any remaining nodes
            self._flush_buffer()

        # Handle text content
        if elem.text:
            self.text_buffer.append(elem.text.strip())
        if elem.tail:
            self.text_buffer.append(elem.tail.strip())

    def _start_heading(self, elem: HtmlElement):
        """Start processing a heading."""
        level = int(elem.tag[1])
        text = self._get_text_content(elem)

        # Create heading node
        heading = HeadingNode(
            level=level,
            content=text
        )

        # Check if this is a section header
        if self.strategies.get('header_detection'):
            detector = self.strategies['header_detection']
            if detector.is_section_header(text, elem):
                heading.semantic_type = SemanticType.SECTION_HEADER

        self.node_buffer.append(heading)

    def _end_heading(self, elem: HtmlElement):
        """End processing a heading."""
        # Get text content from element
        text = self._get_text_content(elem)
        if text and self.node_buffer and isinstance(self.node_buffer[-1], HeadingNode):
            self.node_buffer[-1].content = text

        # Clear any accumulated text buffer
        self.text_buffer.clear()

    def _start_paragraph(self, elem: HtmlElement):
        """Start processing a paragraph."""
        para = ParagraphNode()

        # Get style if present
        style_attr = elem.get('style')
        if style_attr and self.strategies.get('style_parser'):
            style_parser = self.strategies['style_parser']
            para.style = style_parser.parse(style_attr)

        self.node_buffer.append(para)

    def _end_paragraph(self, elem: HtmlElement):
        """End processing a paragraph."""
        # Get text content from element
        text = self._get_text_content(elem)
        if text and self.node_buffer and isinstance(self.node_buffer[-1], ParagraphNode):
            text_node = TextNode(content=text)
            self.node_buffer[-1].add_child(text_node)

        # Clear any accumulated text buffer
        self.text_buffer.clear()

    def _start_table(self, elem: HtmlElement):
        """Start processing a table."""
        self.in_table = True
        self.table_buffer = []

        # Store table element for later processing
        self.table_elem = elem

    def _end_table(self, elem: HtmlElement):
        """End processing a table."""
        self.in_table = False

        # Process table with table processor if available
        if self.strategies.get('table_processing'):
            processor = self.strategies['table_processing']
            table_node = processor.process(elem)
            if table_node:
                self.node_buffer.append(table_node)
        else:
            # Basic table node
            table = TableNode()
            self.node_buffer.append(table)

        self.table_buffer.clear()

    def _start_section(self, elem: HtmlElement):
        """Start processing a section."""
        section = SectionNode()

        # Get section attributes
        section_id = elem.get('id')
        if section_id:
            section.metadata['id'] = section_id

        section_class = elem.get('class')
        if section_class:
            section.metadata['class'] = section_class

        self.current_section = section
        self.node_buffer.append(section)

    def _end_section(self, elem: HtmlElement):
        """End processing a section."""
        self.current_section = None

    def _flush_buffer(self):
        """Flush node buffer to document tree."""
        for node in self.node_buffer:
            # Add to current parent
            if self.current_section:
                self.current_section.add_child(node)
            else:
                self.current_parent.add_child(node)

        self.node_buffer.clear()

    def _get_text_content(self, elem: HtmlElement) -> str:
        """Extract text content from element."""
        text_parts = []

        if elem.text:
            text_parts.append(elem.text.strip())

        for child in elem:
            child_text = self._get_text_content(child)
            if child_text:
                text_parts.append(child_text)
            if child.tail:
                text_parts.append(child.tail.strip())

        return ' '.join(text_parts)

    def _extract_title_metadata(self, title: str):
        """Extract metadata from title."""
        # Example: "APPLE INC - 10-K - 2023-09-30"
        parts = title.split(' - ')
        if len(parts) >= 2:
            self.metadata.company = parts[0].strip()
            self.metadata.filing_type = parts[1].strip()
            if len(parts) >= 3:
                self.metadata.filing_date = parts[2].strip()

    def _extract_meta_metadata(self, elem: HtmlElement):
        """Extract metadata from meta tags."""
        name = elem.get('name', '').lower()
        content = elem.get('content', '')

        if name and content:
            if name == 'company':
                self.metadata.company = content
            elif name == 'filing-type':
                self.metadata.filing_type = content
            elif name == 'cik':
                self.metadata.cik = content
            elif name == 'filing-date':
                self.metadata.filing_date = content
            elif name == 'accession-number':
                self.metadata.accession_number = content


class ChunkedStreamingParser(StreamingParser):
    """
    Alternative streaming parser that processes HTML in chunks.

    Better for extremely large documents where even streaming
    parse might use too much memory.
    """

    def parse(self, html: str) -> Document:
        """
        Parse HTML in chunks.

        Args:
            html: HTML content to parse

        Returns:
            Parsed Document
        """
        self._reset_state()

        # Process in chunks
        for i in range(0, len(html), self.CHUNK_SIZE):
            chunk = html[i:i + self.CHUNK_SIZE]
            self._process_chunk(chunk, is_last=(i + self.CHUNK_SIZE >= len(html)))

        # Create document
        return Document(root=self.root, metadata=self.metadata)

    def _process_chunk(self, chunk: str, is_last: bool):
        """Process a single chunk of HTML."""
        # This is a simplified implementation
        # In practice, would need to handle tags that span chunks

        # Extract text and basic structure
        text = self._extract_text_from_chunk(chunk)
        if text:
            text_node = TextNode(content=text)
            self.node_buffer.append(text_node)

        # Flush if needed
        if len(self.node_buffer) >= self.MAX_NODE_BUFFER or is_last:
            self._flush_buffer()

    def _extract_text_from_chunk(self, chunk: str) -> str:
        """Extract text from HTML chunk."""
        # Simple text extraction
        import re

        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', chunk)

        # Clean whitespace
        text = ' '.join(text.split())

        return text
