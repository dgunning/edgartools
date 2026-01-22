# Advanced Ranking Search

EdgarTools provides advanced search capabilities with BM25-based ranking and semantic structure awareness. This is designed specifically for financial documents to help you find the most relevant information quickly.

## Overview

The ranking search system offers:

- **Three ranking algorithms**: BM25 (text-focused), Hybrid (text + structure), and Semantic (structure-focused)
- **Intelligent caching**: 10x+ faster repeated searches with automatic index caching
- **Structure-aware boosting**: Prioritizes headings, cross-references, and gateway content
- **Agent-friendly results**: Full section context for investigation and navigation
- **Performance optimized**: Instant results from cache, minimal memory overhead

## Quick Start

```python
from edgar import Company
from edgar.documents.search import DocumentSearch

# Get a filing
company = Company("AAPL")
filing = company.get_filings(form="10-K").latest(1)

# Parse HTML into structured Document
document = filing.parse()

# Create search interface
searcher = DocumentSearch(document)

# Search with ranking
results = searcher.ranked_search(
    query="revenue growth",
    algorithm="hybrid",
    top_k=5
)

# Access results
for result in results:
    print(f"Score: {result.score:.3f}")
    print(f"Section: {result.section}")
    print(f"Snippet: {result.snippet}")
```

!!! note "About `filing.parse()`"
    The `parse()` method parses the filing's HTML into a structured `Document` object
    with a node tree that `DocumentSearch` can index. This is different from
    `filing.document` which returns an `Attachment` (file metadata).

    Other useful Filing methods:

    - `filing.html()` - Returns raw HTML string
    - `filing.text()` - Returns plain text extraction
    - `filing.xbrl()` - Returns parsed XBRL data
    - `filing.parse()` - Returns structured Document for advanced operations

## Ranking Algorithms

### BM25 (Best for Exact Term Matching)

BM25 is a probabilistic retrieval function that ranks documents based on term frequency and inverse document frequency. It's excellent for finding exact matches of financial terms and concepts.

```python
results = searcher.ranked_search(
    query="operating expenses depreciation",
    algorithm="bm25",
    top_k=10
)
```

**Best for:**
- Finding specific financial terms
- Exact phrase matching
- Traditional keyword search

**Parameters:**
- `k1` (default: 1.5): Controls term frequency saturation
- `b` (default: 0.75): Controls document length normalization

### Hybrid (Recommended for Most Use Cases)

Hybrid combines BM25 text matching with semantic structure boosting. It understands document structure and boosts:

- **Headings and section markers** (e.g., "Item 1A - Risk Factors")
- **Cross-references** (e.g., "See Item 7 for discussion")
- **Gateway content** (summaries, overviews, introductions)
- **Tables and XBRL data** (structured financial information)

```python
results = searcher.ranked_search(
    query="cybersecurity risks",
    algorithm="hybrid",
    top_k=5
)
```

**Best for:**
- General-purpose search
- Finding gateway content for investigation
- Balancing exact matches with structural importance
- Agent/LLM workflows

**Weights (customizable):**
- `bm25_weight` (default: 0.8): Weight for text matching
- `semantic_weight` (default: 0.2): Weight for structure boosting

### Semantic (Best for Structure Navigation)

Semantic ranking prioritizes document structure without text matching. It finds structurally important sections regardless of query terms.

```python
results = searcher.ranked_search(
    query="business overview",
    algorithm="semantic",
    top_k=5
)
```

**Best for:**
- Understanding document organization
- Finding section boundaries
- Structural navigation
- Overview and summary content

## Advanced Search Options

### Section-Specific Search

Limit search to specific sections:

```python
results = searcher.ranked_search(
    query="supply chain risks",
    in_section="Risk Factors",
    top_k=5
)
```

### Section Boosting

Give higher weight to matches in certain sections:

```python
results = searcher.ranked_search(
    query="revenue recognition",
    algorithm="hybrid",
    boost_sections=["MD&A", "Critical Accounting Policies"],
    top_k=5
)
```

### Node Type Filtering

Search only specific node types:

```python
from edgar.documents.types import NodeType

results = searcher.ranked_search(
    query="financial data",
    node_types=[NodeType.TABLE, NodeType.XBRL],
    top_k=5
)
```

## Working with Results

Each result contains:

```python
result.score           # Relevance score (higher = more relevant)
result.snippet         # Short text snippet (first 200 chars)
result.section         # Section name (e.g., "Risk Factors")
result.node            # Original document node
result.context         # Full text context (up to 500 chars)
```

### Accessing Full Context

For agent workflows, results include full section access:

```python
results = searcher.ranked_search("AI strategy", algorithm="hybrid")

for result in results:
    # Access full section for investigation
    if hasattr(result, '_section_obj') and result._section_obj:
        section = result._section_obj
        full_text = section.text()

        # Navigate section structure
        for child in section.children:
            # Process subsections
            pass
```

## Performance and Caching

### How Caching Works

EdgarTools automatically caches search indices for fast repeated searches:

1. **Instance cache**: Stores engines for same DocumentSearch session
2. **Global cache**: Stores indices across documents (memory + disk)
3. **LRU eviction**: Automatically manages memory (default: 10 cached indices)
4. **TTL expiration**: Automatic cleanup after 24 hours

### Cache Performance

Typical speedup:

```python
import time

# First search (cold cache) - builds index
start = time.perf_counter()
results1 = searcher.ranked_search("revenue", algorithm="bm25")
cold_time = time.perf_counter() - start  # ~0.5s

# Second search (warm cache) - uses cached index
start = time.perf_counter()
results2 = searcher.ranked_search("revenue", algorithm="bm25")
warm_time = time.perf_counter() - start  # ~0.05s

# 10x faster!
```

### Cache Statistics

Monitor cache performance:

```python
stats = searcher.get_cache_stats()

print(f"Cache hits: {stats['global_cache_stats']['cache_hits']}")
print(f"Cache misses: {stats['global_cache_stats']['cache_misses']}")
print(f"Hit rate: {stats['global_cache_stats']['hit_rate']:.1%}")
print(f"Memory usage: {stats['global_cache_stats']['memory_size_mb']:.2f} MB")
```

### Cache Management

```python
# Clear instance cache only
searcher.clear_cache(memory_only=True)

# Clear all caches (memory + disk)
searcher.clear_cache(memory_only=False)

# Disable caching (for testing)
searcher = DocumentSearch(document, use_cache=False)
```

### Custom Cache Configuration

```python
from edgar.documents.ranking.cache import SearchIndexCache, set_search_cache

# Create custom cache
cache = SearchIndexCache(
    memory_cache_size=20,      # Store 20 indices in memory
    disk_cache_enabled=True,   # Enable disk persistence
    ttl_hours=48              # Keep cached for 48 hours
)

# Set as global cache
set_search_cache(cache)
```

## Best Practices

### Choosing the Right Algorithm

| Use Case | Algorithm | Why |
|----------|-----------|-----|
| Finding specific terms | BM25 | Exact text matching |
| General document search | Hybrid | Balance text + structure |
| Understanding document structure | Semantic | Pure structure focus |
| Agent/LLM workflows | Hybrid | Finds gateway content |
| Financial term lookup | BM25 | Best for exact matches |

### Performance Tips

1. **Use caching** (enabled by default) for repeated searches
2. **Use Hybrid algorithm** for most use cases (best results)
3. **Filter by section** to reduce search space
4. **Limit top_k** to needed results (default: 10)
5. **Monitor cache stats** to optimize cache size

### Agent Workflows

For AI agents investigating documents:

```python
# Step 1: Find relevant sections
results = searcher.ranked_search(
    query="climate risk disclosures",
    algorithm="hybrid",
    top_k=3
)

# Step 2: Investigate full sections
for result in results:
    if result._section_obj:
        section = result._section_obj

        # Read full section
        full_content = section.text()

        # Navigate subsections
        for subsection in section.children:
            # Process hierarchically
            pass
```

## API Reference

### DocumentSearch

```python
DocumentSearch(document, use_cache=True)
```

Creates a search interface for a document.

**Parameters:**
- `document`: Parsed SEC document
- `use_cache` (bool): Enable index caching (default: True)

### ranked_search()

```python
searcher.ranked_search(
    query: str,
    algorithm: str = "hybrid",
    top_k: int = 10,
    node_types: Optional[List[NodeType]] = None,
    in_section: Optional[str] = None,
    boost_sections: Optional[List[str]] = None
) -> List[SearchResult]
```

Perform ranked search with BM25-based ranking.

**Parameters:**
- `query`: Search query string
- `algorithm`: Ranking algorithm ("bm25", "hybrid", "semantic")
- `top_k`: Maximum results to return (default: 10)
- `node_types`: Limit to specific node types (optional)
- `in_section`: Limit to specific section (optional)
- `boost_sections`: Sections to boost in ranking (optional)

**Returns:**
- List of `SearchResult` objects with scores and context

### get_cache_stats()

```python
searcher.get_cache_stats() -> Dict[str, Any]
```

Get cache performance statistics.

**Returns:**
- Dictionary with cache metrics:
  - `memory_entries`: Indices in memory
  - `disk_entries`: Indices on disk
  - `cache_hits`: Total cache hits
  - `cache_misses`: Total cache misses
  - `hit_rate`: Cache hit rate (0-1)
  - `memory_size_mb`: Memory usage in MB

### clear_cache()

```python
searcher.clear_cache(memory_only: bool = False)
```

Clear search caches.

**Parameters:**
- `memory_only`: If True, only clear memory cache (default: False)

## Examples

See [ranking_search_examples.py](../examples/ranking_search_examples.py) for comprehensive examples including:

1. Basic BM25 ranked search
2. Hybrid search with structure boosting
3. Semantic structure search
4. Section-specific search
5. Section boosting
6. Cache performance demonstration
7. Agent-friendly workflows
8. Comparing algorithms
9. Disabling cache
10. Cache management

## Migration from Old Search

If you're currently using the basic `search()` method:

### Old Way (Basic Text Search)

```python
results = searcher.search(
    query="revenue",
    mode=SearchMode.TEXT,
    limit=10
)
```

### New Way (Ranked Search)

```python
results = searcher.ranked_search(
    query="revenue growth trends",
    algorithm="hybrid",
    top_k=10
)
```

**Benefits:**
- Relevance scores (not just presence/absence)
- Structure-aware boosting
- Better results for financial documents
- 10x faster with caching
- Full section context

**Note:** The old `search()` method is still available for backwards compatibility.

## Troubleshooting

### Cache Not Working

Check if caching is enabled:

```python
searcher = DocumentSearch(document, use_cache=True)  # Make sure use_cache=True
```

### Memory Issues

Reduce cache size:

```python
from edgar.documents.ranking.cache import SearchIndexCache, set_search_cache

cache = SearchIndexCache(memory_cache_size=5)  # Reduce from default 10
set_search_cache(cache)
```

Or disable disk cache:

```python
cache = SearchIndexCache(disk_cache_enabled=False)
set_search_cache(cache)
```

### Slow First Search

First search builds the index (0.2-1.0s depending on document size). Subsequent searches are instant (~0.05s).

This is normal and expected - the index is cached for future searches.

## Technical Details

### BM25 Algorithm

EdgarTools uses the Okapi BM25 variant with default parameters:
- k1 = 1.5 (term frequency saturation)
- b = 0.75 (length normalization)

These parameters are optimized for financial documents.

### Caching Strategy

- **Memory cache**: LRU eviction, configurable size (default: 10)
- **Disk cache**: Pickle serialization in `~/.edgar_cache/search/`
- **TTL**: 24 hours default (configurable)
- **Index data**: Tokenized corpus + parameters (~5MB per index)

### Semantic Boosting

Structure-aware boosting uses:
- Node type scoring (headings > text > etc.)
- Semantic type detection (item headers, section headers)
- Cross-reference detection (regex patterns for "See Item X")
- Position importance (earlier sections ranked higher)

## See Also

- [Document Parsing](parsing-filing-data.md)
- [XBRL Querying](xbrl-querying.md)
- [Examples](../examples/ranking_search_examples.py)
