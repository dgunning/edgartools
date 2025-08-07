"""
Test HTML parser on real files using simple parser.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from edgar.documents.simple_parser import parse_html_simple
from edgar.documents import DocumentSearch, MarkdownRenderer


def test_html_files():
    """Test parser on various HTML files."""
    data_dir = Path("data/html")
    
    test_files = [
        "Apple.10-K.html",
        "Oracle.10-Q.html", 
        "BuckleInc.8-K.html",
        "TableInsideDiv.html",
        "LineBreaks.html",
        "SpansInsideDiv.html",
        "HtmlWithNoBody.html",
        "problem-6K.html"
    ]
    
    print("HTML PARSER TEST - REAL FILES")
    print("=" * 60)
    
    successful = 0
    failed = 0
    
    for filename in test_files:
        file_path = data_dir / filename
        
        if not file_path.exists():
            print(f"\n❌ {filename} - Not found")
            continue
        
        print(f"\nTesting: {filename}")
        print(f"Size: {file_path.stat().st_size / 1024:.1f}KB")
        
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                html = f.read()
            
            # Parse
            start = time.time()
            doc = parse_html_simple(html)
            parse_time = time.time() - start
            
            # Extract metrics
            text = doc.text()
            tables = doc.tables
            headings = doc.headings
            
            print(f"✅ Success in {parse_time:.3f}s")
            print(f"   Text length: {len(text):,} chars")
            print(f"   Tables: {len(tables)}")
            print(f"   Headings: {len(headings)}")
            
            # Test search
            search = DocumentSearch(doc)
            results = search.search("the")
            print(f"   Search 'the': {len(results)} results")
            
            # Test markdown
            renderer = MarkdownRenderer()
            markdown = renderer.render(doc)
            print(f"   Markdown: {len(markdown):,} chars")
            
            successful += 1
            
        except Exception as e:
            print(f"❌ Failed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"SUMMARY: {successful} passed, {failed} failed")
    print("=" * 60)


def test_specific_issues():
    """Test specific problematic cases."""
    print("\n\nSPECIFIC ISSUE TESTS")
    print("=" * 60)
    
    # Test 1: Empty document
    print("\nTest 1: Empty document")
    try:
        doc = parse_html_simple("")
        print("❌ Should have failed on empty document")
    except Exception as e:
        print(f"✅ Correctly rejected: {e}")
    
    # Test 2: Malformed HTML
    print("\nTest 2: Malformed HTML")
    try:
        html = "<p>Unclosed <div>nested</p></div>"
        doc = parse_html_simple(html)
        print(f"✅ Handled malformed HTML: {doc.text()}")
    except Exception as e:
        print(f"❌ Failed on malformed HTML: {e}")
    
    # Test 3: Large document simulation
    print("\nTest 3: Large document")
    try:
        # Create large HTML
        html = "<html><body>"
        for i in range(1000):
            html += f"<p>Paragraph {i} with some content that makes it larger.</p>"
        html += "</body></html>"
        
        start = time.time()
        doc = parse_html_simple(html)
        parse_time = time.time() - start
        
        print(f"✅ Parsed {len(html):,} bytes in {parse_time:.3f}s")
        print(f"   Text length: {len(doc.text()):,} chars")
        
    except Exception as e:
        print(f"❌ Failed on large document: {e}")


if __name__ == "__main__":
    test_html_files()
    test_specific_issues()