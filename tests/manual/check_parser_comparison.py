"""
Comparison test between old and new HTML parsers.

Shows improvements and differences in parsing results.
Run with: python tests/manual/test_parser_comparison.py
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import both parsers
try:
    # Old parser (if available)
    from edgar.files.html import SECHTMLParser as OldParser
    OLD_PARSER_AVAILABLE = True
except ImportError:
    OLD_PARSER_AVAILABLE = False
    print("Note: Old parser not available for comparison")

# New parser
from edgar.documents import HTMLParser, ParserConfig, parse_html
from edgar.documents.search import DocumentSearch
from edgar.documents.renderers import MarkdownRenderer


class ParserComparison:
    """Compare old and new parser results."""
    
    def __init__(self):
        self.test_files = [
            ("data/html/Apple.10-K.html", "Large 10-K filing"),
            ("data/html/BuckleInc.8-K.html", "8-K with exhibits"),
            ("data/html/TableInsideDiv.html", "Table structure test"),
            ("data/html/LineBreaks.html", "Line break handling"),
            ("data/html/HtmlWithNoBody.html", "Missing body tag"),
            ("data/html/Oracle.10-Q.html", "Complex 10-Q filing"),
        ]
    
    def compare_all(self):
        """Run comparison on all test files."""
        print("=" * 80)
        print("HTML PARSER COMPARISON TEST")
        print("=" * 80)
        
        if not OLD_PARSER_AVAILABLE:
            print("\n⚠️  Old parser not available - showing new parser results only\n")
        
        for file_path, description in self.test_files:
            path = Path(file_path)
            if path.exists():
                print(f"\nTesting: {path.name}")
                print(f"Description: {description}")
                print("-" * 60)
                
                self.compare_file(path)
            else:
                print(f"\n❌ File not found: {file_path}")
    
    def compare_file(self, file_path: Path):
        """Compare parsing results for a single file."""
        # Read file
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            html = f.read()
        
        file_size = len(html)
        print(f"File size: {file_size:,} bytes ({file_size/1024/1024:.1f}MB)")
        
        # Parse with new parser
        new_results = self.parse_with_new(html)
        self.print_results("New Parser", new_results)
        
        # Parse with old parser if available
        if OLD_PARSER_AVAILABLE:
            old_results = self.parse_with_old(html)
            self.print_results("Old Parser", old_results)
            
            # Compare results
            self.compare_results(old_results, new_results)
        
        print()
    
    def parse_with_new(self, html: str) -> Dict[str, Any]:
        """Parse with new parser and collect metrics."""
        results = {
            'success': False,
            'parse_time': 0,
            'error': None
        }
        
        try:
            # Time the parsing
            start = time.time()
            doc = parse_html(html)
            parse_time = time.time() - start
            
            results['success'] = True
            results['parse_time'] = parse_time
            
            # Collect metrics
            text = doc.text()
            results['text_length'] = len(text)
            results['text_preview'] = text[:100].replace('\n', ' ')
            
            # Tables
            results['table_count'] = len(doc.tables)
            if doc.tables:
                results['first_table_size'] = (doc.tables[0].row_count, doc.tables[0].col_count)
                results['table_captions'] = [t.caption for t in doc.tables if t.caption][:3]
            
            # Sections
            results['section_count'] = len(doc.sections)
            results['section_names'] = list(doc.sections.keys())
            
            # Headings
            results['heading_count'] = len(doc.headings)
            results['heading_samples'] = [h.text()[:50] for h in doc.headings[:3]]
            
            # Search capabilities
            search = DocumentSearch(doc)
            revenue_results = search.search("revenue")
            results['revenue_mentions'] = len(revenue_results)
            
            # Node statistics
            node_counts = {}
            for node in doc.root.walk():
                node_type = str(node.type)
                node_counts[node_type] = node_counts.get(node_type, 0) + 1
            results['node_counts'] = node_counts
            
            # Memory efficiency (cache usage)
            from edgar.documents.utils import get_cache_manager
            cache_stats = get_cache_manager().get_stats()
            results['cache_hits'] = sum(s.hits for s in cache_stats.values())
            
        except Exception as e:
            results['error'] = str(e)
            results['error_type'] = type(e).__name__
        
        return results
    
    def parse_with_old(self, html: str) -> Dict[str, Any]:
        """Parse with old parser and collect metrics."""
        results = {
            'success': False,
            'parse_time': 0,
            'error': None
        }
        
        try:
            # Time the parsing
            parser = OldParser()
            start = time.time()
            doc = parser.parse(html)
            parse_time = time.time() - start
            
            results['success'] = True
            results['parse_time'] = parse_time
            
            # Collect metrics (using old API)
            text = doc.text if hasattr(doc, 'text') else doc.get_text()
            results['text_length'] = len(text)
            results['text_preview'] = text[:100].replace('\n', ' ')
            
            # Tables
            if hasattr(doc, 'tables'):
                results['table_count'] = len(doc.tables)
            
            # Sections (if available)
            if hasattr(doc, 'sections'):
                results['section_count'] = len(doc.sections)
                results['section_names'] = list(doc.sections.keys())
            
            # Search (old API)
            if hasattr(doc, 'search'):
                revenue_results = doc.search("revenue")
                results['revenue_mentions'] = len(revenue_results)
            
        except Exception as e:
            results['error'] = str(e)
            results['error_type'] = type(e).__name__
        
        return results
    
    def print_results(self, parser_name: str, results: Dict[str, Any]):
        """Print parser results."""
        print(f"\n{parser_name} Results:")
        
        if results['success']:
            print(f"  ✅ Success in {results['parse_time']:.3f}s")
            print(f"  Text length: {results['text_length']:,} chars")
            print(f"  Tables: {results['table_count']}")
            
            if 'first_table_size' in results:
                rows, cols = results['first_table_size']
                print(f"    First table: {rows}x{cols}")
            
            if 'section_count' in results:
                print(f"  Sections: {results['section_count']}")
                if results.get('section_names'):
                    print(f"    Names: {', '.join(results['section_names'][:5])}")
            
            if 'heading_count' in results:
                print(f"  Headings: {results['heading_count']}")
            
            if 'revenue_mentions' in results:
                print(f"  'Revenue' mentions: {results['revenue_mentions']}")
            
            if 'cache_hits' in results:
                print(f"  Cache hits: {results['cache_hits']}")
            
        else:
            print(f"  ❌ Failed: {results['error_type']} - {results['error']}")
    
    def compare_results(self, old_results: Dict[str, Any], new_results: Dict[str, Any]):
        """Compare and highlight differences."""
        print("\nComparison:")
        
        # Both successful?
        if old_results['success'] and new_results['success']:
            # Performance
            speedup = old_results['parse_time'] / new_results['parse_time']
            print(f"  Performance: {speedup:.1f}x faster")
            
            # Text extraction
            text_diff = abs(old_results['text_length'] - new_results['text_length'])
            if text_diff > 100:
                print(f"  ⚠️  Text length difference: {text_diff:,} chars")
            
            # Tables
            if old_results.get('table_count', 0) != new_results.get('table_count', 0):
                print(f"  📊 Table count: Old={old_results.get('table_count', 0)}, "
                      f"New={new_results.get('table_count', 0)}")
            
            # Sections
            old_sections = old_results.get('section_count', 0)
            new_sections = new_results.get('section_count', 0)
            if new_sections > old_sections:
                print(f"  📑 Better section detection: {old_sections} → {new_sections}")
            
            # Features only in new parser
            if 'node_counts' in new_results:
                total_nodes = sum(new_results['node_counts'].values())
                print(f"  🌳 Rich node tree: {total_nodes} nodes")
            
        elif not old_results['success'] and new_results['success']:
            print(f"  ✨ New parser handles previously failing case!")
        elif old_results['success'] and not new_results['success']:
            print(f"  ⚠️  Regression: Old parser succeeded but new failed")


def test_specific_improvements():
    """Test specific improvements in the new parser."""
    print("\n" + "=" * 80)
    print("SPECIFIC IMPROVEMENTS TEST")
    print("=" * 80)
    
    # Test 1: Header detection improvement
    print("\nTest 1: Header Detection")
    print("-" * 40)
    
    html = """
    <div style="font-size: 18pt; font-weight: bold">Item 1. Business</div>
    <p>Our business description...</p>
    
    <div style="font-size: 16pt; font-weight: bold">Risk Factors</div>
    <p>Various risks...</p>
    """
    
    doc = parse_html(html)
    print(f"Sections detected: {list(doc.sections.keys())}")
    print(f"Headings found: {len(doc.headings)}")
    
    # Test 2: Table structure preservation
    print("\nTest 2: Table Structure")
    print("-" * 40)
    
    html = """
    <table>
        <caption>Financial Results</caption>
        <thead>
            <tr><th>Year</th><th>Revenue</th><th>Profit</th></tr>
        </thead>
        <tbody>
            <tr><td>2023</td><td>$100M</td><td>$20M</td></tr>
            <tr><td>2022</td><td>$80M</td><td>$15M</td></tr>
        </tbody>
    </table>
    """
    
    config = ParserConfig(table_extraction=True)
    doc = parse_html(html, config)
    
    if doc.tables:
        table = doc.tables[0]
        print(f"Table caption: {table.caption}")
        print(f"Has header: {table.has_header}")
        df = table.to_dataframe()
        print(f"DataFrame shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
    
    # Test 3: Performance with caching
    print("\nTest 3: Performance with Caching")
    print("-" * 40)
    
    # Create HTML with repeated styles
    html_parts = []
    for i in range(100):
        html_parts.append(f'<p style="font-size: 14px; color: #333">Paragraph {i}</p>')
    
    html = "<html><body>" + "".join(html_parts) + "</body></html>"
    
    # First parse
    start = time.time()
    doc1 = parse_html(html)
    first_time = time.time() - start
    
    # Second parse (should use cache)
    start = time.time()
    doc2 = parse_html(html)
    second_time = time.time() - start
    
    print(f"First parse: {first_time:.3f}s")
    print(f"Second parse: {second_time:.3f}s")
    print(f"Cache speedup: {first_time/second_time:.1f}x")
    
    # Show cache stats
    from edgar.documents.utils import get_cache_manager
    cache_manager = get_cache_manager()
    stats = cache_manager.get_stats()
    
    print("\nCache statistics:")
    for name, stat in stats.items():
        if stat.hits > 0:
            print(f"  {name}: {stat.hits} hits, {stat.hit_rate:.1%} hit rate")


def main():
    """Run all comparison tests."""
    # Run file comparisons
    comparison = ParserComparison()
    comparison.compare_all()
    
    # Run specific improvement tests
    test_specific_improvements()
    
    print("\n" + "=" * 80)
    print("Comparison tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()