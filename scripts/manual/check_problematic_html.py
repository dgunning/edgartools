"""
Focused tests for problematic HTML files.

Tests specific edge cases and known issues.
Run with: python scripts/manual/test_problematic_html.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from edgar.documents import HTMLParser, ParserConfig, parse_html, DocumentSearch
from edgar.documents.renderers import MarkdownRenderer, TextRenderer


def test_html_with_no_body():
    """Test HTML file missing body tag."""
    print("\n" + "="*60)
    print("Testing: HtmlWithNoBody.html")
    print("="*60)
    
    file_path = Path("data/html/HtmlWithNoBody.html")
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    print(f"File size: {len(html):,} bytes")
    
    try:
        # Parse with different configurations
        configs = {
            'default': ParserConfig(),
            'lenient': ParserConfig(strict_mode=False),
            'preserve': ParserConfig(preserve_whitespace=True)
        }
        
        for config_name, config in configs.items():
            print(f"\nTesting with {config_name} config...")
            doc = parse_html(html, config)
            
            # Check if content was extracted
            text = doc.text()
            print(f"  Text length: {len(text):,} chars")
            print(f"  First 100 chars: {text[:100]}...")
            
            # Check structure
            print(f"  Tables: {len(doc.tables)}")
            print(f"  Headings: {len(doc.headings)}")
            print(f"  Root children: {len(doc.root.children)}")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()


def test_line_breaks():
    """Test line break handling."""
    print("\n" + "="*60)
    print("Testing: LineBreaks.html")
    print("="*60)
    
    file_path = Path("data/html/LineBreaks.html")
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    print(f"HTML content:\n{html}\n")
    
    try:
        # Test with different whitespace settings
        configs = {
            'default': ParserConfig(),
            'preserve_ws': ParserConfig(preserve_whitespace=True),
            'normalize': ParserConfig(normalize_text=True, preserve_whitespace=False)
        }
        
        for config_name, config in configs.items():
            print(f"\n{config_name} config:")
            doc = parse_html(html, config)
            text = doc.text()
            
            # Show exact representation
            print(f"  Text repr: {repr(text)}")
            newline_repr = repr('\n')
            print(f"  Contains \\n: {newline_repr in repr(text)}")
            print(f"  Contains <br>: {'<br>' in text}")
            
            # Test different renderers
            print("\n  Markdown render:")
            md_renderer = MarkdownRenderer()
            markdown = md_renderer.render(doc)
            print(f"    {repr(markdown)}")
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()


def test_spans_inside_div():
    """Test nested span elements inside divs."""
    print("\n" + "="*60)
    print("Testing: SpansInsideDiv.html")
    print("="*60)
    
    file_path = Path("data/html/SpansInsideDiv.html")
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    print(f"HTML content:\n{html}\n")
    
    try:
        doc = parse_html(html)
        
        # Check text extraction
        text = doc.text()
        print(f"Extracted text: {repr(text)}")
        
        # Check node structure
        print("\nNode structure:")
        for node in doc.root.walk():
            indent = "  " * node.depth if hasattr(node, 'depth') else ""
            node_info = f"{node.type}"
            if hasattr(node, 'text') and node.text():
                node_info += f": {repr(node.text()[:50])}"
            print(f"{indent}{node_info}")
        
        # Test that all text is preserved
        expected_texts = ["First span", "Second span", "Third span"]  # Adjust based on actual content
        for expected in expected_texts:
            if expected in text:
                print(f"✅ Found: {expected}")
            else:
                print(f"❌ Missing: {expected}")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()


def test_table_inside_ix_element():
    """Test table extraction from inside XBRL ix elements."""
    print("\n" + "="*60)
    print("Testing: TableInsideIxElement.html")
    print("="*60)
    
    file_path = Path("data/html/TableInsideIxElement.html")
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    try:
        # Parse with XBRL extraction enabled
        config = ParserConfig(
            table_extraction=True,
            extract_xbrl=True
        )
        doc = parse_html(html, config)
        
        print(f"Tables found: {len(doc.tables)}")
        
        # Examine each table
        for i, table in enumerate(doc.tables):
            print(f"\nTable {i + 1}:")
            print(f"  Caption: {table.caption}")
            print(f"  Dimensions: {table.row_count} x {table.col_count}")
            
            # Check if XBRL data was preserved
            if hasattr(table, 'metadata') and table.metadata:
                xbrl_data = table.metadata.get('xbrl_context')
                if xbrl_data:
                    print(f"  XBRL context: {xbrl_data}")
            
            # Try to extract dataframe
            try:
                df = table.to_dataframe()
                print(f"  DataFrame shape: {df.shape}")
                print(f"  Columns: {list(df.columns)}")
            except Exception as e:
                print(f"  DataFrame extraction failed: {e}")
        
        # Check XBRL metadata
        if hasattr(doc.metadata, 'xbrl_data') and doc.metadata.xbrl_data:
            print(f"\nXBRL data extracted: {len(doc.metadata.xbrl_data)} items")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()


def test_order_of_table_in_div():
    """Test correct ordering of tables inside divs."""
    print("\n" + "="*60)
    print("Testing: OrderOfTableInDiv.html")
    print("="*60)
    
    file_path = Path("data/html/OrderOfTableInDiv.html")
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    try:
        doc = parse_html(html)
        
        # Check table order
        print(f"Tables found: {len(doc.tables)}")
        
        # Track order of content
        print("\nContent order:")
        content_order = []
        
        for node in doc.root.walk():
            if hasattr(node, 'type'):
                if node.type.name == 'TABLE':
                    content_order.append(f"TABLE: {getattr(node, 'caption', 'No caption')}")
                elif node.type.name == 'HEADING':
                    content_order.append(f"HEADING: {node.text()[:50] if hasattr(node, 'text') else 'No text'}")
                elif node.type.name == 'PARAGRAPH':
                    text = node.text() if hasattr(node, 'text') else ''
                    if text and len(text.strip()) > 0:
                        content_order.append(f"PARAGRAPH: {text[:50]}...")
        
        for item in content_order:
            print(f"  {item}")
        
        # Verify tables appear in correct positions
        table_positions = [i for i, item in enumerate(content_order) if item.startswith("TABLE:")]
        print(f"\nTable positions in content: {table_positions}")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()


def test_large_problematic_file():
    """Test large problematic file with streaming."""
    print("\n" + "="*60)
    print("Testing: problem-6K.html (Large file)")
    print("="*60)
    
    file_path = Path("data/html/problem-6K.html")
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    file_size = file_path.stat().st_size
    print(f"File size: {file_size / 1024 / 1024:.1f}MB")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Test regular parsing
    print("\nRegular parsing:")
    try:
        import time
        start = time.time()
        doc = parse_html(html)
        regular_time = time.time() - start
        
        print(f"  ✅ Success in {regular_time:.2f}s")
        print(f"  Text length: {len(doc.text()):,} chars")
        print(f"  Tables: {len(doc.tables)}")
        
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        regular_time = None
    
    # Test streaming parsing
    print("\nStreaming parsing:")
    try:
        config = ParserConfig(
            streaming_threshold=1_000_000,  # 1MB - force streaming
            max_document_size=10_000_000    # 10MB limit
        )
        
        start = time.time()
        doc = parse_html(html, config)
        streaming_time = time.time() - start
        
        print(f"  ✅ Success in {streaming_time:.2f}s")
        print(f"  Text length: {len(doc.text()):,} chars")
        
        if regular_time:
            speedup = regular_time / streaming_time
            print(f"  Speedup: {speedup:.1f}x")
        
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    # Test memory usage
    print("\nCache statistics:")
    from edgar.documents.utils import get_cache_manager
    cache_manager = get_cache_manager()
    stats = cache_manager.get_stats()
    
    for cache_name, cache_stats in stats.items():
        if cache_stats.hits + cache_stats.misses > 0:
            print(f"  {cache_name}: {cache_stats.hit_rate:.1%} hit rate")


def test_424_div_containing_spans():
    """Test complex div/span nesting in 424 filings."""
    print("\n" + "="*60)
    print("Testing: 424-DivContainingSpans.html")
    print("="*60)
    
    file_path = Path("data/html/424-DivContainingSpans.html")
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    try:
        doc = parse_html(html)
        
        # Test text extraction preserves all content
        text = doc.text()
        print(f"Total text length: {len(text):,} chars")
        
        # Search for specific patterns common in 424 filings
        search = DocumentSearch(doc)
        
        # Search for prices
        from edgar.documents.search import SearchMode
        price_results = search.search(r'\$\d+\.?\d*', mode=SearchMode.REGEX)
        print(f"\nPrice mentions found: {len(price_results)}")
        for i, result in enumerate(price_results[:5]):
            print(f"  {i+1}. {result.text} - Context: {result.snippet}")
        
        # Test markdown rendering
        renderer = MarkdownRenderer(include_metadata=True)
        markdown = renderer.render(doc)
        
        # Check markdown preserves structure
        print(f"\nMarkdown length: {len(markdown):,} chars")
        print("First 500 chars of markdown:")
        print(markdown[:500])
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all problematic file tests."""
    print("PROBLEMATIC HTML FILES TEST SUITE")
    print("Testing edge cases and known issues")
    
    # Run individual tests
    test_html_with_no_body()
    test_line_breaks()
    test_spans_inside_div()
    test_table_inside_ix_element()
    test_order_of_table_in_div()
    test_424_div_containing_spans()
    test_large_problematic_file()
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)


if __name__ == "__main__":
    main()