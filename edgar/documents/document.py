"""
Document model for parsed HTML.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any, Iterator
from datetime import datetime
import json

from edgar.documents.nodes import Node, DocumentNode, SectionNode
from edgar.documents.table_nodes import TableNode
from edgar.documents.types import NodeType, XBRLFact, SearchResult


@dataclass
class DocumentMetadata:
    """
    Document metadata.
    
    Contains information about the source document and parsing process.
    """
    source: Optional[str] = None
    filing_type: Optional[str] = None
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            'source': self.source,
            'filing_type': self.filing_type,
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
    """
    name: str
    title: str
    node: SectionNode
    start_offset: int = 0
    end_offset: int = 0
    
    def text(self, **kwargs) -> str:
        """Extract text from section."""
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
    _sections: Optional[Dict[str, Section]] = field(default=None, init=False, repr=False)
    _tables: Optional[List[TableNode]] = field(default=None, init=False, repr=False)
    _headings: Optional[List[Node]] = field(default=None, init=False, repr=False)
    _xbrl_facts: Optional[List[XBRLFact]] = field(default=None, init=False, repr=False)
    _text_cache: Optional[str] = field(default=None, init=False, repr=False)
    
    @property
    def sections(self) -> Dict[str, Section]:
        """
        Get document sections.
        
        Returns a dictionary mapping section names to Section objects.
        Sections are detected based on headers and structure.
        """
        if self._sections is None:
            from edgar.documents.extractors.section_extractor import SectionExtractor
            self._sections = SectionExtractor().extract(self)
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
             include_tables: bool = False,
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
    
    def get_section(self, section_name: str) -> Optional[Section]:
        """Get section by name."""
        return self.sections.get(section_name)
    
    def extract_section_text(self, section_name: str) -> Optional[str]:
        """Extract text from specific section."""
        section = self.get_section(section_name)
        if section:
            return section.text()
        return None
    
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
            'filing_type': self.metadata.filing_type,
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
        if self.metadata.filing_type in ['10-K', '10-Q']:
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
        parts.append(f"Document: {self.metadata.get('filing_type', 'Unknown')}")
        parts.append(f"Company: {self.metadata.get('company', 'Unknown')}")
        parts.append(f"Date: {self.metadata.get('filing_date', 'Unknown')}")
        parts.append("")
        
        # Add content
        parts.append(self.content)
        
        if self.truncated:
            parts.append("\n[Content truncated due to length]")
        
        return '\n'.join(parts)