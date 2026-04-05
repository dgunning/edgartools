"""
Manual test for HTML parser using real SEC filing HTML files.

Tests the new parser against various HTML files including problematic ones.
Run with: python scripts/manual/test_html_parser_real_files.py
"""

import os
import time
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from edgar.documents import (
    HTMLParser, Document, ParserConfig, parse_html,
    DocumentSearch, SearchMode, MarkdownRenderer
)
from edgar.documents.exceptions import HTMLParsingError, DocumentTooLargeError
from edgar.documents.utils import get_cache_manager


class HTMLTestRunner:
    """Runner for testing HTML parser with real files."""
    
    def __init__(self, data_dir: str = "data/html"):
        """Initialize test runner."""
        self.data_dir = Path(data_dir)
        self.results: List[Dict[str, Any]] = []
        self.problematic_files = [
            "HtmlWithNoBody.html",  # Missing body tag
            "problem-6K.html",  # Large problematic file
            "LineBreaks.html",  # Line break handling
            "SpansInsideDiv.html",  # Nested inline elements
            "TableInsideIxElement.html",  # Tables in XBRL elements
            "424-DivContainingSpans.html",  # Complex div/span nesting
            "OrderOfTableInDiv.html",  # Table ordering issues
        ]
    
    def run_all_tests(self):
        """Run tests on all HTML files."""
        print("=" * 80)
        print("HTML PARSER MANUAL TEST SUITE")
        print("=" * 80)
        print(f"Testing files in: {self.data_dir}\n")
        
        # Get all HTML files
        html_files = list(self.data_dir.glob("*.html"))
        print(f"Found {len(html_files)} HTML files to test\n")
        
        # Test each file
        for i, file_path in enumerate(html_files, 1):
            print(f"[{i}/{len(html_files)}] Testing: {file_path.name}")
            
            # Mark problematic files
            is_problematic = file_path.name in self.problematic_files
            if is_problematic:
                print("  ⚠️  Known problematic file")
            
            result = self.test_file(file_path)
            self.results.append(result)
            
            # Print summary
            if result['success']:
                print(f"  ✅ Success - {result['parse_time']:.2f}s")
                print(f"     Text length: {result.get('text_length', 0):,} chars")
                print(f"     Tables: {result.get('table_count', 0)}")
                print(f"     Sections: {result.get('section_count', 0)}")
            else:
                print(f"  ❌ Failed: {result['error']}")
            
            print()
        
        # Print summary
        self.print_summary()
    
    def test_file(self, file_path: Path) -> Dict[str, Any]:
        """Test a single HTML file."""
        result = {
            'file': file_path.name,
            'size': file_path.stat().st_size,
            'success': False,
            'error': None,
            'parse_time': 0,
            'is_problematic': file_path.name in self.problematic_files
        }
        
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                html = f.read()
            
            # Test different parser configurations
            configs = {
                'default': ParserConfig(),
                'performance': ParserConfig.for_performance(),
                'accuracy': ParserConfig.for_accuracy(),
                'ai': ParserConfig.for_ai()
            }
            
            # Test with default config first
            start_time = time.time()
            document = parse_html(html, configs['default'])
            parse_time = time.time() - start_time
            
            result['parse_time'] = parse_time
            result['success'] = True
            
            # Extract metrics
            result.update(self.extract_metrics(document))
            
            # Test specific features based on file
            if 'Table' in file_path.name:
                self.test_table_features(document, result)
            
            if any(x in file_path.name for x in ['10-K', '10-Q', '8-K']):
                self.test_filing_features(document, result)
            
            if file_path.name in self.problematic_files:
                self.test_problematic_features(document, result, html)
            
            # Test other configurations
            for config_name, config in configs.items():
                if config_name != 'default':
                    try:
                        _ = parse_html(html, config)
                        result[f'{config_name}_success'] = True
                    except Exception as e:
                        result[f'{config_name}_success'] = False
                        result[f'{config_name}_error'] = str(e)
            
        except Exception as e:
            result['error'] = str(e)
            result['traceback'] = traceback.format_exc()
        
        return result
    
    def extract_metrics(self, document: Document) -> Dict[str, Any]:
        """Extract metrics from parsed document."""
        metrics = {}
        
        try:
            # Basic metrics
            text = document.text()
            metrics['text_length'] = len(text)
            metrics['table_count'] = len(document.tables)
            metrics['heading_count'] = len(document.headings)
            metrics['section_count'] = len(document.sections)
            
            # Node statistics
            node_types = {}
            for node in document.root.walk():
                node_type = str(node.type)
                node_types[node_type] = node_types.get(node_type, 0) + 1
            metrics['node_types'] = node_types
            
            # Table details
            if document.tables:
                table_info = []
                for table in document.tables[:5]:  # First 5 tables
                    info = {
                        'caption': table.caption,
                        'rows': table.row_count,
                        'cols': table.col_count,
                        'type': str(table.semantic_type) if hasattr(table, 'semantic_type') else None
                    }
                    table_info.append(info)
                metrics['table_info'] = table_info
            
            # Section details
            if document.sections:
                metrics['section_names'] = list(document.sections.keys())
            
        except Exception as e:
            metrics['metric_error'] = str(e)
        
        return metrics
    
    def test_table_features(self, document: Document, result: Dict[str, Any]):
        """Test table-specific features."""
        try:
            search = DocumentSearch(document)
            
            # Find tables by various methods
            tables = search.find_tables()
            result['tables_found'] = len(tables)
            
            # Test table data extraction
            for i, table in enumerate(tables[:3]):  # Test first 3 tables
                try:
                    df = table.to_dataframe()
                    result[f'table_{i}_df_shape'] = df.shape
                    result[f'table_{i}_has_data'] = not df.empty
                except Exception as e:
                    result[f'table_{i}_df_error'] = str(e)
            
        except Exception as e:
            result['table_test_error'] = str(e)
    
    def test_filing_features(self, document: Document, result: Dict[str, Any]):
        """Test SEC filing-specific features."""
        try:
            # Test section detection
            expected_sections = {
                '10-K': ['business', 'risk_factors', 'mda', 'financial_statements'],
                '10-Q': ['financial_statements', 'mda'],
                '8-K': []  # Various item sections
            }
            
            filing_type = None
            for ft in ['10-K', '10-Q', '8-K']:
                if ft in result['file']:
                    filing_type = ft
                    break
            
            if filing_type and filing_type in expected_sections:
                found_sections = set(document.sections.keys())
                expected = set(expected_sections[filing_type])
                result['expected_sections'] = list(expected)
                result['found_sections'] = list(found_sections)
                result['missing_sections'] = list(expected - found_sections)
            
            # Test search functionality
            search = DocumentSearch(document)
            
            # Search for common terms
            revenue_results = search.search("revenue", mode=SearchMode.TEXT)
            result['revenue_mentions'] = len(revenue_results)
            
            # Search for dollar amounts
            dollar_results = search.search(r'\$[\d,]+', mode=SearchMode.REGEX)
            result['dollar_amounts'] = len(dollar_results)
            
            # Test markdown rendering
            renderer = MarkdownRenderer()
            markdown = renderer.render(document)
            result['markdown_length'] = len(markdown)
            
        except Exception as e:
            result['filing_test_error'] = str(e)
    
    def test_problematic_features(self, document: Document, result: Dict[str, Any], html: str):
        """Test features specific to problematic files."""
        try:
            # Test specific issues
            if "HtmlWithNoBody" in result['file']:
                # Should still parse without body tag
                result['parsed_without_body'] = document.text() != ""
            
            elif "LineBreaks" in result['file']:
                # Test line break handling
                text = document.text()
                result['preserves_line_breaks'] = '\n' in text or '<br' not in text
            
            elif "SpansInsideDiv" in result['file']:
                # Test nested element handling
                result['handles_nested_spans'] = True  # If we got here, it parsed
            
            elif "TableInsideIxElement" in result['file']:
                # Test XBRL element handling
                tables = document.tables
                result['extracted_tables_from_ix'] = len(tables) > 0
            
            elif "problem-6K" in result['file']:
                # Large file - test streaming
                config = ParserConfig(streaming_threshold=1_000_000)  # 1MB
                start = time.time()
                doc_streaming = parse_html(html, config)
                result['streaming_time'] = time.time() - start
                result['streaming_success'] = True
            
        except Exception as e:
            result['problematic_test_error'] = str(e)
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        # Overall stats
        total = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        failed = total - successful
        
        print(f"\nTotal files tested: {total}")
        print(f"✅ Successful: {successful} ({successful/total*100:.1f}%)")
        print(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")
        
        # Problematic files
        print("\nProblematic Files:")
        problematic_results = [r for r in self.results if r['is_problematic']]
        for result in problematic_results:
            status = "✅" if result['success'] else "❌"
            print(f"  {status} {result['file']}")
            if result['success']:
                print(f"     - Parse time: {result['parse_time']:.3f}s")
                if 'streaming_time' in result:
                    print(f"     - Streaming time: {result['streaming_time']:.3f}s")
        
        # Performance stats
        print("\nPerformance Statistics:")
        parse_times = [r['parse_time'] for r in self.results if r['success']]
        if parse_times:
            print(f"  Average parse time: {sum(parse_times)/len(parse_times):.3f}s")
            print(f"  Min parse time: {min(parse_times):.3f}s")
            print(f"  Max parse time: {max(parse_times):.3f}s")
        
        # File size analysis
        print("\nFile Size Analysis:")
        sizes = [(r['file'], r['size'], r['parse_time']) 
                for r in self.results if r['success']]
        sizes.sort(key=lambda x: x[1], reverse=True)
        
        print("  Largest files:")
        for name, size, parse_time in sizes[:5]:
            print(f"    {name}: {size/1024/1024:.1f}MB - {parse_time:.3f}s")
        
        # Table extraction stats
        print("\nTable Extraction:")
        table_counts = [r.get('table_count', 0) for r in self.results if r['success']]
        if table_counts:
            print(f"  Total tables found: {sum(table_counts)}")
            print(f"  Average tables per doc: {sum(table_counts)/len(table_counts):.1f}")
            print(f"  Max tables in doc: {max(table_counts)}")
        
        # Section detection stats
        print("\nSection Detection (for filings):")
        filing_results = [r for r in self.results 
                         if r['success'] and any(ft in r['file'] for ft in ['10-K', '10-Q', '8-K'])]
        
        for result in filing_results:
            if 'found_sections' in result:
                print(f"  {result['file']}: {len(result['found_sections'])} sections")
                if result.get('missing_sections'):
                    print(f"    Missing: {', '.join(result['missing_sections'])}")
        
        # Cache statistics
        print("\nCache Performance:")
        cache_manager = get_cache_manager()
        stats = cache_manager.get_stats()
        
        for cache_name, cache_stats in stats.items():
            if cache_stats.hits + cache_stats.misses > 0:
                print(f"  {cache_name}:")
                print(f"    Hit rate: {cache_stats.hit_rate:.1%}")
                print(f"    Hits: {cache_stats.hits}, Misses: {cache_stats.misses}")
        
        # Failed files details
        if failed > 0:
            print("\nFailed Files:")
            for result in self.results:
                if not result['success']:
                    print(f"  {result['file']}: {result['error']}")
                    if 'traceback' in result and '--verbose' in sys.argv:
                        print(f"    Traceback:\n{result['traceback']}")
        
        # Memory usage estimate
        cache_usage = cache_manager.get_memory_usage()
        total_cache_mb = sum(cache_usage.values()) / 1024 / 1024
        print(f"\nEstimated cache memory usage: {total_cache_mb:.1f}MB")


def main():
    """Run manual tests."""
    # Check if data directory exists
    data_dir = Path("data/html")
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        print("Please run from project root directory")
        return
    
    # Create and run tests
    runner = HTMLTestRunner(str(data_dir))
    
    try:
        runner.run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        runner.print_summary()
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()