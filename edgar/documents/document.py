"""
Document model for parsed HTML.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Iterator

from rich.table import Table as RichTable
from rich.console import Group
from rich.text import Text
from edgar.richtools import repr_rich

from edgar.documents.nodes import Node, SectionNode
from edgar.documents.table_nodes import TableNode
from edgar.documents.types import XBRLFact, SearchResult


@dataclass
class DocumentMetadata:
    """
    Document metadata.

    Contains information about the source document and parsing process.
    """
    source: Optional[str] = None
    form: Optional[str] = None
    company: Optional[str] = None
    cik: Optional[str] = None
    accession_number: Optional[str] = None
    filing_date: Optional[str] = None
    report_date: Optional[str] = None
    url: Optional[str] = None
    size: int = 0
    parse_time: float = 0.0
    parser_version: str = "2.0.0"
    xbrl_data: Optional[List[XBRLFact]] = None
    preserve_whitespace: bool = False
    original_html: Optional[str] = None  # Store original HTML for anchor analysis

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            'source': self.source,
            'form': self.form,
            'company': self.company,
            'cik': self.cik,
            'accession_number': self.accession_number,
            'filing_date': self.filing_date,
            'report_date': self.report_date,
            'url': self.url,
            'size': self.size,
            'parse_time': self.parse_time,
            'parser_version': self.parser_version,
            'xbrl_data': [fact.to_dict() for fact in self.xbrl_data] if self.xbrl_data else None
        }


@dataclass
class Section:
    """
    Document section representation.

    Represents a logical section of the document (e.g., Risk Factors, MD&A).

    Attributes:
        name: Section identifier (e.g., "item_1", "part_i_item_1", "risk_factors")
        title: Display title (e.g., "Item 1 - Business")
        node: Node containing section content
        start_offset: Character position where section starts
        end_offset: Character position where section ends
        confidence: Detection confidence score (0.0-1.0)
        detection_method: How section was detected ('toc', 'heading', 'pattern')
        validated: Whether section has been cross-validated
        part: Optional part identifier for 10-Q filings ("I", "II", or None for 10-K)
        item: Optional item identifier (e.g., "1", "1A", "2")
        _text_extractor: Optional callback for lazy text extraction (for TOC-based sections)
    """
    name: str
    title: str
    node: SectionNode
    start_offset: int = 0
    end_offset: int = 0
    confidence: float = 1.0  # Detection confidence (0.0-1.0)
    detection_method: str = 'unknown'  # 'toc', 'heading', 'pattern', or 'unknown'
    validated: bool = False  # Cross-validated flag
    part: Optional[str] = None  # Part identifier for 10-Q: "I", "II", or None for 10-K
    item: Optional[str] = None  # Item identifier: "1", "1A", "2", etc.
    _text_extractor: Optional[Any] = field(default=None, repr=False)  # Callback for lazy text extraction

    def text(self, **kwargs) -> str:
        """Extract text from section."""
        # If we have a text extractor callback (TOC-based sections), use it
        if self._text_extractor is not None:
            return self._text_extractor(self.name, **kwargs)

        # Otherwise extract from node (heading/pattern-based sections)
        from edgar.documents.extractors.text_extractor import TextExtractor
        extractor = TextExtractor(**kwargs)
        return extractor.extract_from_node(self.node)
    
    def tables(self) -> List[TableNode]:
        """Get all tables in section."""
        return self.node.find(lambda n: isinstance(n, TableNode))
    
    def search(self, query: str) -> List[SearchResult]:
        """Search within section."""
        # Implementation would use semantic search
        results = []
        # Simple text search for now
        text = self.text().lower()
        query_lower = query.lower()
        
        if query_lower in text:
            # Find snippet around match
            index = text.find(query_lower)
            start = max(0, index - 50)
            end = min(len(text), index + len(query) + 50)
            snippet = text[start:end]
            
            results.append(SearchResult(
                node=self.node,
                score=1.0,
                snippet=snippet,
                section=self.name
            ))

        return results

    @staticmethod
    def parse_section_name(section_name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse section name to extract part and item identifiers.

        Handles both 10-Q part-aware names and 10-K simple names.

        Args:
            section_name: Section identifier (e.g., "part_i_item_1", "item_1a", "risk_factors")

        Returns:
            Tuple of (part, item) where:
            - part: "I", "II", or None for 10-K sections
            - item: "1", "1A", "2", etc. or None if not an item section

        Examples:
            >>> Section.parse_section_name("part_i_item_1")
            ("I", "1")
            >>> Section.parse_section_name("part_ii_item_1a")
            ("II", "1A")
            >>> Section.parse_section_name("item_7")
            (None, "7")
            >>> Section.parse_section_name("risk_factors")
            (None, None)
        """
        import re

        section_lower = section_name.lower()

        # Match 10-Q format: "part_i_item_1", "part_ii_item_1a"
        part_item_match = re.match(r'part_([ivx]+)_item_(\d+[a-z]?)', section_lower)
        if part_item_match:
            part_roman = part_item_match.group(1).upper()
            item_num = part_item_match.group(2).upper()
            return (part_roman, item_num)

        # Match 10-K format: "item_1", "item_1a", "item_7"
        item_match = re.match(r'item_(\d+[a-z]?)', section_lower)
        if item_match:
            item_num = item_match.group(1).upper()
            return (None, item_num)

        # Not a structured item section
        return (None, None)


class Sections(Dict[str, Section]):
    """
    Dictionary wrapper for sections with rich display support.

    Behaves like a normal dict but provides beautiful terminal display
    via __rich__() method when printed in rich-enabled environments.
    """

    def __rich__(self):
        """Return rich representation for display."""
        if not self:
            return Text("No sections detected", style="dim")

        # Create summary table
        table = RichTable(title="Document Sections", show_header=True, header_style="bold magenta")
        table.add_column("Section", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("Confidence", justify="right", style="green")
        table.add_column("Method", style="yellow")
        table.add_column("Part/Item", style="blue")

        # Sort sections by part (roman numeral) and item number
        def sort_key(item):
            name, section = item
            # Convert roman numerals to integers for sorting
            roman_to_int = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5}

            part = section.part.lower() if section.part else ''
            item_str = section.item if section.item else ''

            # Extract part number
            part_num = roman_to_int.get(part, 0)

            # Extract item number and letter
            import re
            if item_str:
                match = re.match(r'(\d+)([a-z]?)', item_str.lower())
                if match:
                    item_num = int(match.group(1))
                    item_letter = match.group(2) or ''
                    return (part_num, item_num, item_letter)

            # Fallback to name sorting
            return (part_num, 999, name)

        sorted_sections = sorted(self.items(), key=sort_key)

        # Add rows for each section
        for name, section in sorted_sections:
            # Format confidence as percentage
            confidence = f"{section.confidence:.1%}"

            # Format part/item info
            part_item = ""
            if section.part and section.item:
                part_item = f"Part {section.part}, Item {section.item}"
            elif section.item:
                part_item = f"Item {section.item}"
            elif section.part:
                part_item = f"Part {section.part}"

            # Truncate title if too long
            title = section.title
            if len(title) > 50:
                title = title[:47] + "..."

            table.add_row(
                name,
                title,
                confidence,
                section.detection_method,
                part_item
            )

        # Create summary stats
        total = len(self)
        high_conf = sum(1 for s in self.values() if s.confidence >= 0.8)
        methods = {}
        for section in self.values():
            methods[section.detection_method] = methods.get(section.detection_method, 0) + 1

        summary = Text()
        summary.append(f"\nTotal: {total} sections | ", style="dim")
        summary.append(f"High confidence (≥80%): {high_conf} | ", style="dim")
        summary.append(f"Methods: {', '.join(f'{m}={c}' for m, c in methods.items())}", style="dim")

        return Group(table, summary)

    def __repr__(self):
        return repr_rich(self.__rich__())

    def get_item(self, item: str, part: str = None) -> Optional[Section]:
        """
        Get section by item number with optional part specification.

        Args:
            item: Item identifier (e.g., "1", "1A", "7", "Item 1", "Item 7A")
            part: Optional part specification (e.g., "I", "II", "Part I", "Part II")
                  If not specified and multiple parts contain the item, returns first match.

        Returns:
            Section object if found, None otherwise

        Examples:
            >>> sections.get_item("1")           # Returns first Item 1 (any part)
            >>> sections.get_item("1", "I")      # Returns Part I, Item 1
            >>> sections.get_item("Item 1A")     # Returns first Item 1A
            >>> sections.get_item("7A", "II")    # Returns Part II, Item 7A
        """
        # Normalize item string - remove "Item " prefix if present
        item_clean = item.replace("Item ", "").replace("item ", "").strip().upper()

        # Normalize part string if provided
        part_clean = None
        if part:
            part_clean = part.replace("Part ", "").replace("part ", "").replace("PART ", "").strip().upper()

        # Search through sections
        for name, section in self.items():
            if section.item and section.item.upper() == item_clean:
                if part_clean is None:
                    # No part specified - return first match
                    return section
                elif section.part and section.part.upper() == part_clean:
                    # Part matches
                    return section

        return None

    def get_part(self, part: str) -> Dict[str, Section]:
        """
        Get all sections in a specific part.

        Args:
            part: Part identifier (e.g., "I", "II", "Part I", "Part II")

        Returns:
            Dictionary of sections in that part

        Examples:
            >>> sections.get_part("I")        # All Part I sections
            >>> sections.get_part("Part II")  # All Part II sections
        """
        # Normalize part string
        part_clean = part.replace("Part ", "").replace("part ", "").replace("PART ", "").strip().upper()

        result = {}
        for name, section in self.items():
            if section.part and section.part.upper() == part_clean:
                result[name] = section

        return result

    def get(self, key, default=None):
        """
        Enhanced get method that supports flexible key formats.

        Supports:
        - Standard dict key: "part_i_item_1"
        - Item number: "Item 1", "1", "1A"
        - Part+Item: ("I", "1"), ("Part II", "7A")

        Args:
            key: Section key (string or tuple)
            default: Default value if not found

        Returns:
            Section object or default value
        """
        # Try standard dict lookup first
        if isinstance(key, str):
            result = super().get(key, None)
            if result is not None:
                return result

            # Try as item number
            result = self.get_item(key)
            if result is not None:
                return result

        # Try as (part, item) tuple
        elif isinstance(key, tuple) and len(key) == 2:
            part, item = key
            result = self.get_item(item, part)
            if result is not None:
                return result

        return default

    def __getitem__(self, key):
        """
        Enhanced __getitem__ that supports flexible key formats.

        Supports:
        - Standard dict key: sections["part_i_item_1"]
        - Item number: sections["Item 1"], sections["1A"]
        - Part+Item tuple: sections[("I", "1")], sections[("II", "7A")]

        Raises KeyError if not found (standard dict behavior).
        """
        # Try standard dict lookup first
        if isinstance(key, str):
            try:
                return super().__getitem__(key)
            except KeyError:
                # Try as item number
                result = self.get_item(key)
                if result is not None:
                    return result

        # Try as (part, item) tuple
        elif isinstance(key, tuple) and len(key) == 2:
            part, item = key
            result = self.get_item(item, part)
            if result is not None:
                return result

        # Not found - raise KeyError
        raise KeyError(key)


@dataclass
class Document:
    """
    Main document class.
    
    Represents a parsed HTML document with methods for content extraction,
    search, and transformation.
    """
    
    # Core properties
    root: Node
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)

    # Cached extractions
    _sections: Optional[Sections] = field(default=None, init=False, repr=False)
    _tables: Optional[List[TableNode]] = field(default=None, init=False, repr=False)
    _headings: Optional[List[Node]] = field(default=None, init=False, repr=False)
    _xbrl_facts: Optional[List[XBRLFact]] = field(default=None, init=False, repr=False)
    _text_cache: Optional[str] = field(default=None, init=False, repr=False)
    _config: Optional[Any] = field(default=None, init=False, repr=False)  # ParserConfig reference
    
    @property
    def sections(self) -> Sections:
        """
        Get document sections using hybrid multi-strategy detection.

        Tries detection methods in order of reliability:
        1. TOC-based (0.95 confidence)
        2. Heading-based (0.7-0.9 confidence)
        3. Pattern-based (0.6 confidence)

        Returns a Sections dictionary wrapper that provides rich terminal display
        via __rich__() method. Each section includes confidence score and detection method.
        """
        if self._sections is None:
            # Get form type from config or metadata
            form = None
            if self._config and hasattr(self._config, 'form'):
                form = self._config.form
            elif self.metadata and self.metadata.form:
                form = self.metadata.form

            # Only detect sections for supported form types (including amendments)
            # Normalize form type by removing /A suffix for amendments
            base_form = form.replace('/A', '') if form else None

            if base_form and base_form in ['10-K', '10-Q', '8-K']:
                from edgar.documents.extractors.hybrid_section_detector import HybridSectionDetector
                # Pass thresholds from config if available
                thresholds = self._config.detection_thresholds if self._config else None
                # Use base form type for detection (10-K/A → 10-K)
                detector = HybridSectionDetector(self, base_form, thresholds)
                detected_sections = detector.detect_sections()
            else:
                # Fallback to pattern-based for other types or unknown
                from edgar.documents.extractors.pattern_section_extractor import SectionExtractor
                extractor = SectionExtractor(form) if form else SectionExtractor()
                detected_sections = extractor.extract(self)

            # Wrap detected sections in Sections class for rich display
            self._sections = Sections(detected_sections)

        return self._sections
    
    @property
    def tables(self) -> List[TableNode]:
        """Get all tables in document."""
        if self._tables is None:
            self._tables = self.root.find(lambda n: isinstance(n, TableNode))
        return self._tables
    
    @property
    def headings(self) -> List[Node]:
        """Get all headings in document."""
        if self._headings is None:
            from edgar.documents.nodes import HeadingNode
            self._headings = self.root.find(lambda n: isinstance(n, HeadingNode))
        return self._headings
    
    @property
    def xbrl_facts(self) -> List[XBRLFact]:
        """Get all XBRL facts in document."""
        if self._xbrl_facts is None:
            self._xbrl_facts = self._extract_xbrl_facts()
        return self._xbrl_facts
    
    def text(self, 
             clean: bool = True,
             include_tables: bool = True,
             include_metadata: bool = False,
             max_length: Optional[int] = None) -> str:
        """
        Extract text from document.
        
        Args:
            clean: Clean and normalize text
            include_tables: Include table content in text
            include_metadata: Include metadata annotations
            max_length: Maximum text length
            
        Returns:
            Extracted text
        """
        # Use cache if available and parameters match
        if (self._text_cache is not None and 
            clean and not include_tables and not include_metadata and max_length is None):
            return self._text_cache
        
        # If whitespace was preserved during parsing and clean is default (True),
        # respect the preserve_whitespace setting
        if self.metadata.preserve_whitespace and clean:
            clean = False
        
        from edgar.documents.extractors.text_extractor import TextExtractor
        extractor = TextExtractor(
            clean=clean,
            include_tables=include_tables,
            include_metadata=include_metadata,
            max_length=max_length
        )
        text = extractor.extract(self)
        
        # Apply navigation link filtering when cleaning 
        if clean:
            # Use cached/integrated navigation filtering (optimized approach)
            try:
                from edgar.documents.utils.anchor_cache import filter_with_cached_patterns
                # Use minimal cached approach (no memory overhead)
                original_html = getattr(self.metadata, 'original_html', None)
                text = filter_with_cached_patterns(text, html_content=original_html)
            except:
                # Fallback to pattern-based filtering
                from edgar.documents.utils.toc_filter import filter_toc_links
                text = filter_toc_links(text)
        
        # Cache if using default parameters
        if clean and not include_tables and not include_metadata and max_length is None:
            self._text_cache = text
        
        return text
    
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        Search document for query.
        
        Args:
            query: Search query
            top_k: Maximum results to return
            
        Returns:
            List of search results
        """
        from edgar.documents.search import DocumentSearch
        searcher = DocumentSearch(self)
        return searcher.search(query, top_k=top_k)
    
    def get_section(self, section_name: str, part: Optional[str] = None) -> Optional[Section]:
        """
        Get section by name with optional part specification for 10-Q filings.

        Args:
            section_name: Section identifier (e.g., "item_1", "part_i_item_1")
            part: Optional part specification for 10-Q ("I", "II", "i", "ii")
                  If provided, searches for "part_{part}_{section_name}"

        Returns:
            Section object if found, None otherwise

        Examples:
            # 10-K usage (unchanged)
            >>> doc.get_section("item_1")  # Returns Item 1

            # 10-Q usage with explicit part
            >>> doc.get_section("item_1", part="I")  # Returns Part I Item 1
            >>> doc.get_section("item_1", part="II")  # Returns Part II Item 1

            # 10-Q usage with full name
            >>> doc.get_section("part_i_item_1")  # Returns Part I Item 1
        """
        # If part is specified, construct part-aware name
        if part:
            part_normalized = part.upper()
            # Remove "item_" prefix if present in section_name
            item_name = section_name.replace("item_", "") if section_name.startswith("item_") else section_name
            full_name = f"part_{part_normalized.lower()}_item_{item_name.lower()}"
            return self.sections.get(full_name)

        # Direct lookup (works for both 10-K "item_1" and 10-Q "part_i_item_1")
        section = self.sections.get(section_name)
        if section:
            return section

        # If not found and looks like an item without part, check if we have multiple parts
        # In that case, raise a helpful error
        if section_name.startswith("item_") or section_name.replace("_", "").startswith("item"):
            # Check if we have part-aware sections (10-Q)
            matching_sections = [name for name in self.sections.keys()
                               if section_name in name and "part_" in name]
            if matching_sections:
                # Multiple parts available - user needs to specify which one
                parts = sorted(set(s.split("_")[1] for s in matching_sections if s.startswith("part_")))
                raise ValueError(
                    f"Ambiguous section '{section_name}' in 10-Q filing. "
                    f"Found in parts: {parts}. "
                    f"Please specify part: get_section('{section_name}', part='I') or part='II'"
                )

        return None
    
    def extract_section_text(self, section_name: str) -> Optional[str]:
        """Extract text from specific section."""
        section = self.get_section(section_name)
        if section:
            return section.text()
        return None
    
    def get_sec_section(self, section_name: str, clean: bool = True, 
                       include_subsections: bool = True) -> Optional[str]:
        """
        Extract content from a specific SEC filing section using anchor analysis.
        
        Args:
            section_name: Section name (e.g., "Item 1", "Item 1A", "Part I")
            clean: Whether to apply text cleaning and navigation filtering
            include_subsections: Whether to include subsections
            
        Returns:
            Section text content or None if section not found
            
        Examples:
            >>> doc.get_sec_section("Item 1")  # Business description
            >>> doc.get_sec_section("Item 1A") # Risk factors  
            >>> doc.get_sec_section("Item 7")  # MD&A
        """
        # Lazy-load section extractor
        if not hasattr(self, '_section_extractor'):
            from edgar.documents.extractors.toc_section_extractor import SECSectionExtractor
            self._section_extractor = SECSectionExtractor(self)
        
        return self._section_extractor.get_section_text(
            section_name, include_subsections, clean
        )
    
    def get_available_sec_sections(self) -> List[str]:
        """
        Get list of SEC sections available for extraction.
        
        Returns:
            List of section names that can be passed to get_sec_section()
            
        Example:
            >>> sections = doc.get_available_sec_sections()
            >>> print(sections)
            ['Part I', 'Item 1', 'Item 1A', 'Item 1B', 'Item 2', ...]
        """
        if not hasattr(self, '_section_extractor'):
            from edgar.documents.extractors.toc_section_extractor import SECSectionExtractor
            self._section_extractor = SECSectionExtractor(self)
        
        return self._section_extractor.get_available_sections()
    
    def get_sec_section_info(self, section_name: str) -> Optional[Dict]:
        """
        Get detailed information about an SEC section.
        
        Args:
            section_name: Section name to look up
            
        Returns:
            Dict with section metadata including anchor info
        """
        if not hasattr(self, '_section_extractor'):
            from edgar.documents.extractors.toc_section_extractor import SECSectionExtractor
            self._section_extractor = SECSectionExtractor(self)
        
        return self._section_extractor.get_section_info(section_name)
    
    def to_markdown(self) -> str:
        """Convert document to Markdown."""
        from edgar.documents.renderers.markdown_renderer import MarkdownRenderer
        renderer = MarkdownRenderer()
        return renderer.render(self)
    
    def to_json(self, include_content: bool = True) -> Dict[str, Any]:
        """
        Convert document to JSON.
        
        Args:
            include_content: Include full content or just structure
            
        Returns:
            JSON-serializable dictionary
        """
        result = {
            'metadata': self.metadata.to_dict(),
            'sections': list(self.sections.keys()),
            'table_count': len(self.tables),
            'xbrl_fact_count': len(self.xbrl_facts)
        }
        
        if include_content:
            result['sections_detail'] = {
                name: {
                    'title': section.title,
                    'text_length': len(section.text()),
                    'table_count': len(section.tables())
                }
                for name, section in self.sections.items()
            }
            
            result['tables'] = [
                {
                    'type': table.table_type.name,
                    'rows': len(table.rows),
                    'columns': len(table.headers[0]) if table.headers else 0,
                    'caption': table.caption
                }
                for table in self.tables
            ]
        
        return result
    
    def to_dataframe(self) -> 'pd.DataFrame':
        """
        Convert document tables to pandas DataFrame.
        
        Returns a DataFrame with all tables concatenated.
        """
        import pandas as pd
        
        if not self.tables:
            return pd.DataFrame()
        
        # Convert each table to DataFrame
        dfs = []
        for i, table in enumerate(self.tables):
            df = table.to_dataframe()
            # Add table index
            df['_table_index'] = i
            df['_table_type'] = table.table_type.name
            if table.caption:
                df['_table_caption'] = table.caption
            dfs.append(df)
        
        # Concatenate all tables
        return pd.concat(dfs, ignore_index=True)
    
    def chunks(self, chunk_size: int = 512, overlap: int = 128) -> Iterator['DocumentChunk']:
        """
        Generate document chunks for processing.
        
        Args:
            chunk_size: Target chunk size in tokens
            overlap: Overlap between chunks
            
        Yields:
            Document chunks
        """
        from edgar.documents.extractors.chunk_extractor import ChunkExtractor
        extractor = ChunkExtractor(chunk_size=chunk_size, overlap=overlap)
        return extractor.extract(self)
    
    def prepare_for_llm(self, 
                       max_tokens: int = 4000,
                       preserve_structure: bool = True,
                       focus_sections: Optional[List[str]] = None) -> 'LLMDocument':
        """
        Prepare document for LLM processing.
        
        Args:
            max_tokens: Maximum tokens
            preserve_structure: Preserve document structure
            focus_sections: Sections to focus on
            
        Returns:
            LLM-optimized document
        """
        from edgar.documents.ai.llm_optimizer import LLMOptimizer
        optimizer = LLMOptimizer()
        return optimizer.optimize(
            self, 
            max_tokens=max_tokens,
            preserve_structure=preserve_structure,
            focus_sections=focus_sections
        )
    
    def extract_key_information(self) -> Dict[str, Any]:
        """Extract key information from document."""
        return {
            'company': self.metadata.company,
            'form': self.metadata.form,
            'filing_date': self.metadata.filing_date,
            'sections': list(self.sections.keys()),
            'financial_tables': sum(1 for t in self.tables if t.is_financial_table),
            'total_tables': len(self.tables),
            'xbrl_facts': len(self.xbrl_facts),
            'document_length': len(self.text())
        }
    
    def _extract_xbrl_facts(self) -> List[XBRLFact]:
        """Extract XBRL facts from document."""
        facts = []
        
        # Find all nodes with XBRL metadata
        xbrl_nodes = self.root.find(
            lambda n: n.get_metadata('ix_tag') is not None
        )
        
        for node in xbrl_nodes:
            fact = XBRLFact(
                concept=node.get_metadata('ix_tag'),
                value=node.text(),
                context_ref=node.get_metadata('ix_context'),
                unit_ref=node.get_metadata('ix_unit'),
                decimals=node.get_metadata('ix_decimals'),
                scale=node.get_metadata('ix_scale')
            )
            facts.append(fact)
        
        return facts
    
    def __len__(self) -> int:
        """Get number of top-level nodes."""
        return len(self.root.children)
    
    def __iter__(self) -> Iterator[Node]:
        """Iterate over top-level nodes."""
        return iter(self.root.children)

    def __repr__(self) -> str:
        return self.text()
    
    def walk(self) -> Iterator[Node]:
        """Walk entire document tree."""
        return self.root.walk()
    
    def find_nodes(self, predicate) -> List[Node]:
        """Find all nodes matching predicate."""
        return self.root.find(predicate)
    
    def find_first_node(self, predicate) -> Optional[Node]:
        """Find first node matching predicate."""
        return self.root.find_first(predicate)
    
    @property
    def is_empty(self) -> bool:
        """Check if document is empty."""
        return len(self.root.children) == 0
    
    @property
    def has_tables(self) -> bool:
        """Check if document has tables."""
        return len(self.tables) > 0
    
    @property
    def has_xbrl(self) -> bool:
        """Check if document has XBRL data."""
        return len(self.xbrl_facts) > 0
    
    def validate(self) -> List[str]:
        """
        Validate document structure.
        
        Returns list of validation issues.
        """
        issues = []
        
        # Check for empty document
        if self.is_empty:
            issues.append("Document is empty")
        
        # Check for sections
        if not self.sections:
            issues.append("No sections detected")
        
        # Check for common sections in filings
        if self.metadata.form in ['10-K', '10-Q']:
            expected_sections = ['business', 'risk_factors', 'mda']
            missing = [s for s in expected_sections if s not in self.sections]
            if missing:
                issues.append(f"Missing expected sections: {', '.join(missing)}")
        
        # Check for orphaned nodes
        orphaned = self.root.find(lambda n: n.parent is None and n != self.root)
        if orphaned:
            issues.append(f"Found {len(orphaned)} orphaned nodes")
        
        return issues


@dataclass
class DocumentChunk:
    """Represents a chunk of document for processing."""
    content: str
    start_node: Node
    end_node: Node
    section: Optional[str] = None
    token_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary."""
        return {
            'content': self.content,
            'section': self.section,
            'token_count': self.token_count,
            'start_path': self.start_node.path,
            'end_path': self.end_node.path
        }


@dataclass 
class LLMDocument:
    """Document optimized for LLM processing."""
    content: str
    metadata: Dict[str, Any]
    token_count: int
    sections: List[str]
    truncated: bool = False
    
    def to_prompt(self) -> str:
        """Convert to LLM prompt."""
        parts = []
        
        # Add metadata context
        parts.append(f"Document: {self.metadata.get('form', 'Unknown')}")
        parts.append(f"Company: {self.metadata.get('company', 'Unknown')}")
        parts.append(f"Date: {self.metadata.get('filing_date', 'Unknown')}")
        parts.append("")
        
        # Add content
        parts.append(self.content)
        
        if self.truncated:
            parts.append("\n[Content truncated due to length]")
        
        return '\n'.join(parts)