"""
Search functionality for parsed documents.

Provides both traditional search modes (TEXT, REGEX, SEMANTIC, XPATH) and
advanced BM25-based ranking with semantic structure awareness.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from edgar.documents.document import Document
from edgar.documents.nodes import Node, HeadingNode
from edgar.documents.table_nodes import TableNode
from edgar.documents.types import NodeType, SemanticType

if TYPE_CHECKING:
    from edgar.documents.types import SearchResult as TypesSearchResult


class SearchMode(Enum):
    """Search modes."""
    TEXT = "text"           # Plain text search
    REGEX = "regex"         # Regular expression search
    SEMANTIC = "semantic"   # Semantic/structural search
    XPATH = "xpath"         # XPath-like search


@dataclass
class SearchResult:
    """Result from a search operation."""
    node: Node                      # Node containing match
    text: str                       # Matched text
    start_offset: int              # Start position in text
    end_offset: int                # End position in text
    context: Optional[str] = None  # Surrounding context
    score: float = 1.0             # Relevance score
    
    @property
    def snippet(self) -> str:
        """Get text snippet with match highlighted."""
        if self.context:
            # Highlight match in context
            before = self.context[:self.start_offset]
            match = self.context[self.start_offset:self.end_offset]
            after = self.context[self.end_offset:]
            return f"{before}**{match}**{after}"
        return f"**{self.text}**"


class DocumentSearch:
    """
    Search functionality for parsed documents.
    
    Supports various search modes and options.
    """
    
    def __init__(self, document: Document, use_cache: bool = True):
        """
        Initialize search with document.

        Args:
            document: Document to search
            use_cache: Enable index caching for faster repeated searches (default: True)
        """
        self.document = document
        self.use_cache = use_cache
        self._ranking_engines: Dict[str, Any] = {}  # Cached ranking engines
        self._build_index()
    
    def _build_index(self):
        """Build search index for performance."""
        # Text index: map text to nodes
        self.text_index: Dict[str, List[Node]] = {}
        
        # Type index: map node types to nodes
        self.type_index: Dict[NodeType, List[Node]] = {}
        
        # Semantic index: map semantic types to nodes  
        self.semantic_index: Dict[SemanticType, List[Node]] = {}
        
        # Build indices
        for node in self.document.root.walk():
            # Text index
            if hasattr(node, 'text'):
                text = node.text()
                if text:
                    text_lower = text.lower()
                    if text_lower not in self.text_index:
                        self.text_index[text_lower] = []
                    self.text_index[text_lower].append(node)
            
            # Type index
            if node.type not in self.type_index:
                self.type_index[node.type] = []
            self.type_index[node.type].append(node)
            
            # Semantic index
            if hasattr(node, 'semantic_type') and node.semantic_type:
                if node.semantic_type not in self.semantic_index:
                    self.semantic_index[node.semantic_type] = []
                self.semantic_index[node.semantic_type].append(node)
    
    def search(self, 
              query: str,
              mode: SearchMode = SearchMode.TEXT,
              case_sensitive: bool = False,
              whole_word: bool = False,
              limit: Optional[int] = None,
              node_types: Optional[List[NodeType]] = None,
              in_section: Optional[str] = None) -> List[SearchResult]:
        """
        Search document.
        
        Args:
            query: Search query
            mode: Search mode
            case_sensitive: Case sensitive search
            whole_word: Match whole words only
            limit: Maximum results to return
            node_types: Limit search to specific node types
            in_section: Limit search to specific section
            
        Returns:
            List of search results
        """
        if mode == SearchMode.TEXT:
            results = self._text_search(query, case_sensitive, whole_word)
        elif mode == SearchMode.REGEX:
            results = self._regex_search(query, case_sensitive)
        elif mode == SearchMode.SEMANTIC:
            results = self._semantic_search(query)
        elif mode == SearchMode.XPATH:
            results = self._xpath_search(query)
        else:
            raise ValueError(f"Unsupported search mode: {mode}")
        
        # Filter by node types
        if node_types:
            results = [r for r in results if r.node.type in node_types]
        
        # Filter by section
        if in_section:
            section_nodes = self._get_section_nodes(in_section)
            results = [r for r in results if r.node in section_nodes]
        
        # Apply limit
        if limit and len(results) > limit:
            results = results[:limit]
        
        return results
    
    def _text_search(self, query: str, case_sensitive: bool, whole_word: bool) -> List[SearchResult]:
        """Perform text search."""
        results = []
        
        # Prepare query
        if not case_sensitive:
            query = query.lower()
        
        # Search only leaf nodes to avoid duplicates
        for node in self.document.root.walk():
            # Skip nodes with children (they aggregate child text)
            if hasattr(node, 'children') and node.children:
                continue
            
            if not hasattr(node, 'text'):
                continue
            
            text = node.text()
            if not text:
                continue
            
            search_text = text if case_sensitive else text.lower()
            
            # Find all occurrences
            if whole_word:
                # Use word boundary regex
                pattern = r'\b' + re.escape(query) + r'\b'
                flags = 0 if case_sensitive else re.IGNORECASE
                
                for match in re.finditer(pattern, text, flags):
                    results.append(SearchResult(
                        node=node,
                        text=match.group(),
                        start_offset=match.start(),
                        end_offset=match.end(),
                        context=self._get_context(text, match.start(), match.end())
                    ))
            else:
                # Simple substring search
                start = 0
                while True:
                    pos = search_text.find(query, start)
                    if pos == -1:
                        break
                    
                    results.append(SearchResult(
                        node=node,
                        text=text[pos:pos + len(query)],
                        start_offset=pos,
                        end_offset=pos + len(query),
                        context=self._get_context(text, pos, pos + len(query))
                    ))
                    
                    start = pos + 1
        
        return results
    
    def _regex_search(self, pattern: str, case_sensitive: bool) -> List[SearchResult]:
        """Perform regex search."""
        results = []
        
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        
        # Search only leaf nodes to avoid duplicates
        for node in self.document.root.walk():
            # Skip nodes with children (they aggregate child text)
            if hasattr(node, 'children') and node.children:
                continue
                
            if not hasattr(node, 'text'):
                continue
            
            text = node.text()
            if not text:
                continue
            
            # Find all matches
            for match in regex.finditer(text):
                results.append(SearchResult(
                    node=node,
                    text=match.group(),
                    start_offset=match.start(),
                    end_offset=match.end(),
                    context=self._get_context(text, match.start(), match.end())
                ))
        
        return results
    
    def _semantic_search(self, query: str) -> List[SearchResult]:
        """Perform semantic/structural search."""
        results = []
        
        # Parse semantic query
        # Examples: "heading:Item 1", "table:revenue", "section:risk factors"
        if ':' in query:
            search_type, search_text = query.split(':', 1)
            search_type = search_type.lower().strip()
            search_text = search_text.strip()
        else:
            # Default to text search in headings
            search_type = 'heading'
            search_text = query
        
        if search_type == 'heading':
            # Search headings
            for node in self.type_index.get(NodeType.HEADING, []):
                if isinstance(node, HeadingNode):
                    heading_text = node.text()
                    if heading_text and search_text.lower() in heading_text.lower():
                        results.append(SearchResult(
                            node=node,
                            text=heading_text,
                            start_offset=0,
                            end_offset=len(heading_text),
                            score=self._calculate_heading_score(node)
                        ))
        
        elif search_type == 'table':
            # Search tables
            for node in self.type_index.get(NodeType.TABLE, []):
                if isinstance(node, TableNode):
                    # Search in table content
                    table_text = node.text()
                    if table_text and search_text.lower() in table_text.lower():
                        results.append(SearchResult(
                            node=node,
                            text=f"Table: {node.caption or 'Untitled'}",
                            start_offset=0,
                            end_offset=len(table_text),
                            context=table_text[:200] + "..." if len(table_text) > 200 else table_text
                        ))
        
        elif search_type == 'section':
            # Search sections
            sections = self.document.sections
            for section_name, section in sections.items():
                if search_text.lower() in section_name.lower():
                    results.append(SearchResult(
                        node=section.node,
                        text=section.title,
                        start_offset=section.start_offset,
                        end_offset=section.end_offset,
                        score=2.0  # Boost section matches
                    ))
        
        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)
        
        return results
    
    def _xpath_search(self, xpath: str) -> List[SearchResult]:
        """Perform XPath-like search."""
        results = []
        
        # Simple XPath parser
        # Examples: "//h1", "//table[@class='financial']", "//p[contains(text(),'revenue')]"
        
        # Extract tag name
        tag_match = re.match(r'//(\w+)', xpath)
        if not tag_match:
            raise ValueError(f"Invalid XPath: {xpath}")
        
        tag_name = tag_match.group(1).lower()
        
        # Map tag to node type
        tag_to_type = {
            'h1': NodeType.HEADING,
            'h2': NodeType.HEADING,
            'h3': NodeType.HEADING,
            'h4': NodeType.HEADING,
            'h5': NodeType.HEADING,
            'h6': NodeType.HEADING,
            'p': NodeType.PARAGRAPH,
            'table': NodeType.TABLE,
            'section': NodeType.SECTION
        }
        
        node_type = tag_to_type.get(tag_name)
        if not node_type:
            return results
        
        # Get nodes of type
        nodes = self.type_index.get(node_type, [])
        
        # Apply filters
        if '[' in xpath:
            # Extract condition
            condition_match = re.search(r'\[(.*?)\]', xpath)
            if condition_match:
                condition = condition_match.group(1)
                nodes = self._apply_xpath_condition(nodes, condition)
        
        # Create results
        for node in nodes:
            text = node.text() if hasattr(node, 'text') else str(node)
            results.append(SearchResult(
                node=node,
                text=text[:100] + "..." if len(text) > 100 else text,
                start_offset=0,
                end_offset=len(text)
            ))
        
        return results
    
    def _apply_xpath_condition(self, nodes: List[Node], condition: str) -> List[Node]:
        """Apply XPath condition to filter nodes."""
        filtered = []
        
        # Parse condition
        if condition.startswith('@'):
            # Attribute condition
            attr_match = re.match(r'@(\w+)=["\']([^"\']+)["\']', condition)
            if attr_match:
                attr_name, attr_value = attr_match.groups()
                for node in nodes:
                    if node.metadata.get(attr_name) == attr_value:
                        filtered.append(node)
        
        elif 'contains(text()' in condition:
            # Text contains condition
            text_match = re.search(r'contains\(text\(\),\s*["\']([^"\']+)["\']\)', condition)
            if text_match:
                search_text = text_match.group(1).lower()
                for node in nodes:
                    if hasattr(node, 'text'):
                        node_text = node.text()
                        if node_text and search_text in node_text.lower():
                            filtered.append(node)
        
        else:
            # Level condition for headings
            try:
                level = int(condition)
                for node in nodes:
                    if isinstance(node, HeadingNode) and node.level == level:
                        filtered.append(node)
            except ValueError:
                pass
        
        return filtered
    
    def _get_context(self, text: str, start: int, end: int, context_size: int = 50) -> str:
        """Get context around match."""
        # Calculate context boundaries
        context_start = max(0, start - context_size)
        context_end = min(len(text), end + context_size)
        
        # Get context
        context = text[context_start:context_end]
        
        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(text):
            context = context + "..."
        
        # Adjust offsets for context
        if context_start > 0:
            start = start - context_start + 3  # Account for "..."
            end = end - context_start + 3
        else:
            start = start - context_start
            end = end - context_start
        
        return context
    
    def _calculate_heading_score(self, heading: HeadingNode) -> float:
        """Calculate relevance score for heading."""
        # Higher level headings get higher scores
        base_score = 7 - heading.level  # H1=6, H2=5, etc.
        
        # Boost section headers
        if heading.semantic_type == SemanticType.SECTION_HEADER:
            base_score *= 1.5
        
        return base_score
    
    def _get_section_nodes(self, section_name: str) -> List[Node]:
        """Get all nodes in a section."""
        nodes = []
        
        sections = self.document.sections
        if section_name in sections:
            section = sections[section_name]
            # Get all nodes in section
            for node in section.node.walk():
                nodes.append(node)
        
        return nodes
    
    def find_tables(self, 
                   caption_pattern: Optional[str] = None,
                   min_rows: Optional[int] = None,
                   min_cols: Optional[int] = None) -> List[TableNode]:
        """
        Find tables matching criteria.
        
        Args:
            caption_pattern: Regex pattern for caption
            min_rows: Minimum number of rows
            min_cols: Minimum number of columns
            
        Returns:
            List of matching tables
        """
        tables = []
        
        for node in self.type_index.get(NodeType.TABLE, []):
            if not isinstance(node, TableNode):
                continue
            
            # Check caption
            if caption_pattern and node.caption:
                if not re.search(caption_pattern, node.caption, re.IGNORECASE):
                    continue
            
            # Check dimensions
            if min_rows and node.row_count < min_rows:
                continue
            if min_cols and node.col_count < min_cols:
                continue
            
            tables.append(node)
        
        return tables
    
    def find_headings(self,
                     level: Optional[int] = None,
                     pattern: Optional[str] = None) -> List[HeadingNode]:
        """
        Find headings matching criteria.

        Args:
            level: Heading level (1-6)
            pattern: Regex pattern for heading text

        Returns:
            List of matching headings
        """
        headings = []

        for node in self.type_index.get(NodeType.HEADING, []):
            if not isinstance(node, HeadingNode):
                continue

            # Check level
            if level and node.level != level:
                continue

            # Check pattern
            if pattern:
                heading_text = node.text()
                if not heading_text or not re.search(pattern, heading_text, re.IGNORECASE):
                    continue

            headings.append(node)

        return headings

    def ranked_search(self,
                     query: str,
                     algorithm: str = "hybrid",
                     top_k: int = 10,
                     node_types: Optional[List[NodeType]] = None,
                     in_section: Optional[str] = None,
                     boost_sections: Optional[List[str]] = None) -> List['TypesSearchResult']:
        """
        Advanced search with BM25-based ranking and semantic structure awareness.

        This provides relevance-ranked results better suited for financial documents
        than simple substring matching. Uses BM25 for exact term matching combined
        with semantic structure boosting for gateway content detection.

        Args:
            query: Search query
            algorithm: Ranking algorithm ("bm25", "hybrid", "semantic")
            top_k: Maximum results to return
            node_types: Limit search to specific node types
            in_section: Limit search to specific section
            boost_sections: Section names to boost (e.g., ["Risk Factors"])

        Returns:
            List of SearchResult objects with relevance scores (from types.py)

        Examples:
            >>> searcher = DocumentSearch(document)
            >>> results = searcher.ranked_search("revenue growth", algorithm="hybrid", top_k=5)
            >>> for result in results:
            >>>     print(f"Score: {result.score:.3f}")
            >>>     print(f"Text: {result.snippet}")
            >>>     print(f"Full context: {result.full_context[:200]}...")
        """
        from edgar.documents.ranking.ranking import (
            BM25Engine,
            HybridEngine,
            SemanticEngine
        )
        from edgar.documents.types import SearchResult as TypesSearchResult

        # Get all leaf nodes for ranking (avoid duplicates from parent nodes)
        nodes = []
        for node in self.document.root.walk():
            # Only include leaf nodes with text
            if hasattr(node, 'children') and node.children:
                continue  # Skip parent nodes
            if hasattr(node, 'text'):
                text = node.text()
                if text and len(text.strip()) > 0:
                    nodes.append(node)

        # Filter by node types if specified
        if node_types:
            nodes = [n for n in nodes if n.type in node_types]

        # Filter by section if specified
        if in_section:
            section_nodes = self._get_section_nodes(in_section)
            nodes = [n for n in nodes if n in section_nodes]

        if not nodes:
            return []

        # Select ranking engine (with caching)
        engine = self._get_ranking_engine(algorithm.lower(), nodes, boost_sections)

        # Rank nodes
        ranked_results = engine.rank(query, nodes)

        # Convert to types.SearchResult format and add section context
        search_results = []
        for ranked in ranked_results[:top_k]:
            # Try to find which section this node belongs to
            section_obj = self._find_node_section(ranked.node)

            search_results.append(TypesSearchResult(
                node=ranked.node,
                score=ranked.score,
                snippet=ranked.snippet,
                section=section_obj.name if section_obj else None,
                context=ranked.text if len(ranked.text) <= 500 else ranked.text[:497] + "...",
                _section_obj=section_obj  # Agent navigation support
            ))

        return search_results

    def _get_ranking_engine(self, algorithm: str, nodes: List[Node],
                            boost_sections: Optional[List[str]] = None):
        """
        Get or create ranking engine with caching support.

        Args:
            algorithm: Ranking algorithm ("bm25", "hybrid", "semantic")
            nodes: Nodes to index
            boost_sections: Section names to boost (for hybrid/semantic)

        Returns:
            Ready-to-use ranking engine
        """
        from edgar.documents.ranking.ranking import (
            BM25Engine,
            HybridEngine,
            SemanticEngine
        )
        from edgar.documents.ranking.cache import get_search_cache, CacheEntry
        from datetime import datetime

        # Create cache key
        # Use document ID, algorithm, and sample of first node for stability
        content_sample = nodes[0].text()[:200] if nodes and hasattr(nodes[0], 'text') else ""
        cache_key = f"{self.document.accession_number if hasattr(self.document, 'accession_number') else id(self.document)}_{algorithm}"

        # Check instance cache first (for same search session)
        if cache_key in self._ranking_engines:
            engine, cached_nodes = self._ranking_engines[cache_key]
            # Verify nodes haven't changed
            if cached_nodes == nodes:
                return engine

        # Create engine based on algorithm
        if algorithm == "bm25":
            engine = BM25Engine()
        elif algorithm == "hybrid":
            engine = HybridEngine(boost_sections=boost_sections)
        elif algorithm == "semantic":
            engine = SemanticEngine(boost_sections=boost_sections)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Try to load from global cache if enabled
        if self.use_cache and algorithm == "bm25":  # Only cache BM25 for now
            search_cache = get_search_cache()
            document_hash = search_cache.compute_document_hash(
                document_id=cache_key,
                content_sample=content_sample
            )

            cached_entry = search_cache.get(document_hash)
            if cached_entry:
                # Load index from cache
                try:
                    engine.load_index_data(cached_entry.index_data, nodes)
                    # Cache in instance
                    self._ranking_engines[cache_key] = (engine, nodes)
                    return engine
                except Exception as e:
                    # Cache load failed, rebuild
                    pass

        # Build fresh index
        # For BM25/Hybrid, index is built lazily on first rank() call
        # But we can force it here and cache the result
        if self.use_cache and algorithm == "bm25":
            # Force index build by doing a dummy rank
            engine._build_index(nodes)

            # Save to global cache
            try:
                search_cache = get_search_cache()
                document_hash = search_cache.compute_document_hash(
                    document_id=cache_key,
                    content_sample=content_sample
                )

                index_data = engine.get_index_data()
                cache_entry = CacheEntry(
                    document_hash=document_hash,
                    index_data=index_data,
                    created_at=datetime.now()
                )
                search_cache.put(document_hash, cache_entry)
            except Exception as e:
                # Cache save failed, not critical
                pass

        # Cache in instance
        self._ranking_engines[cache_key] = (engine, nodes)

        return engine

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get search cache statistics.

        Returns:
            Dictionary with cache performance metrics including:
            - memory_entries: Number of indices in memory
            - disk_entries: Number of indices on disk
            - cache_hits: Total cache hits
            - cache_misses: Total cache misses
            - hit_rate: Cache hit rate (0-1)
            - memory_size_mb: Estimated memory usage in MB

        Examples:
            >>> searcher = DocumentSearch(document)
            >>> searcher.ranked_search("revenue", algorithm="bm25")
            >>> stats = searcher.get_cache_stats()
            >>> print(f"Hit rate: {stats['hit_rate']:.1%}")
        """
        from edgar.documents.ranking.cache import get_search_cache

        stats = {
            'instance_cache_entries': len(self._ranking_engines),
            'global_cache_stats': {}
        }

        if self.use_cache:
            cache = get_search_cache()
            stats['global_cache_stats'] = cache.get_stats()

        return stats

    def clear_cache(self, memory_only: bool = False) -> None:
        """
        Clear search caches.

        Args:
            memory_only: If True, only clear in-memory caches (default: False)

        Examples:
            >>> searcher = DocumentSearch(document)
            >>> searcher.clear_cache()  # Clear all caches
            >>> searcher.clear_cache(memory_only=True)  # Only clear memory
        """
        # Clear instance cache
        self._ranking_engines.clear()

        # Clear global cache if enabled
        if self.use_cache:
            from edgar.documents.ranking.cache import get_search_cache
            cache = get_search_cache()
            cache.clear(memory_only=memory_only)

    def _find_node_section(self, node: Node):
        """
        Find which section a node belongs to.

        Returns:
            Section object or None
        """
        # Walk up the tree to find section markers
        current = node
        while current:
            # Check if any section contains this node
            for section_name, section in self.document.sections.items():
                # Check if node is in section's subtree
                for section_node in section.node.walk():
                    if section_node is current or section_node is node:
                        return section

            current = current.parent if hasattr(current, 'parent') else None

        return None