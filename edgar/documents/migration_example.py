"""
Example showing how to migrate from old parser to new.
"""

def old_parser_example():
    """Example using old parser API."""
    print("=== OLD PARSER EXAMPLE ===")
    
    # This is how code might look with the old parser
    from edgar.documents.migration import SECHTMLParser  # Using compatibility layer
    
    # Create parser
    parser = SECHTMLParser({
        'extract_tables': True,
        'clean_text': True,
        'preserve_layout': False
    })
    
    # Parse HTML
    html = """
    <html>
        <body>
            <h1>Item 1. Business</h1>
            <p>We are a technology company.</p>
            
            <table>
                <tr><th>Year</th><th>Revenue</th></tr>
                <tr><td>2023</td><td>$100M</td></tr>
            </table>
        </body>
    </html>
    """
    
    document = parser.parse(html)
    
    # Old API usage (will show deprecation warnings)
    print(f"Text: {document.text[:50]}...")
    print(f"Tables: {len(document.tables)}")
    print(f"Sections: {list(document.sections.keys())}")
    
    # Search
    results = document.search("revenue")
    print(f"Search results: {results}")
    
    # Convert to markdown
    markdown = document.to_markdown()
    print(f"Markdown: {markdown[:100]}...")


def new_parser_example():
    """Example using new parser API."""
    print("\n=== NEW PARSER EXAMPLE ===")
    
    # New imports
    from edgar.documents import HTMLParser, Document, ParserConfig, DocumentSearch
    from edgar.documents.renderers import MarkdownRenderer
    
    # Create parser with new config
    config = ParserConfig(
        table_extraction=True,
        clean_text=True,
        preserve_whitespace=False,
        detect_sections=True
    )
    
    parser = HTMLParser(config)
    
    # Parse HTML
    html = """
    <html>
        <body>
            <h1>Item 1. Business</h1>
            <p>We are a technology company.</p>
            
            <table>
                <tr><th>Year</th><th>Revenue</th></tr>
                <tr><td>2023</td><td>$100M</td></tr>
            </table>
        </body>
    </html>
    """
    
    document = parser.parse(html)
    
    # New API usage
    print(f"Text: {document.text()[:50]}...")
    print(f"Tables: {len(document.tables)}")
    print(f"Sections: {list(document.sections.keys())}")
    
    # Search with new API
    search = DocumentSearch(document)
    results = search.search("revenue")
    print(f"Search results: {[r.text for r in results]}")
    
    # Convert to markdown with new API
    renderer = MarkdownRenderer()
    markdown = renderer.render(document)
    print(f"Markdown: {markdown[:100]}...")
    
    # New features not available in old parser
    print("\n--- New Features ---")
    
    # Advanced search
    table_results = search.find_tables(caption_pattern="Revenue")
    print(f"Tables with 'Revenue': {len(table_results)}")
    
    # Performance-optimized parser
    fast_parser = HTMLParser.create_for_performance()
    print(f"Performance parser created: {fast_parser}")
    
    # Cache statistics
    from edgar.documents.utils import get_cache_manager
    cache_stats = get_cache_manager().get_stats()
    print(f"Cache stats: {list(cache_stats.keys())}")


def migration_comparison():
    """Show side-by-side comparison."""
    print("\n=== MIGRATION COMPARISON ===")
    
    comparison = """
    | Feature           | Old API                        | New API                          |
    |-------------------|--------------------------------|----------------------------------|
    | Import            | from edgar.files.html import   | from edgar.documents import          |
    | Parser            | SECHTMLParser()                | HTMLParser()                     |
    | Parse             | parser.parse(html)             | parser.parse(html)               |
    | Get text          | document.text                  | document.text()                  |
    | Get tables        | document.tables                | document.tables                  |
    | Search            | document.search(pattern)       | DocumentSearch(doc).search(...)  |
    | Find elements     | document.find_all('h1')        | doc.root.find(lambda n: ...)     |
    | To markdown       | document.to_markdown()         | MarkdownRenderer().render(doc)   |
    | Sections          | document.sections              | document.sections                |
    | Config            | {'extract_tables': True}       | ParserConfig(table_extraction=True) |
    """
    
    print(comparison)


def automatic_migration_example():
    """Show automatic code migration."""
    print("\n=== AUTOMATIC CODE MIGRATION ===")
    
    from edgar.documents.migration import migrate_parser_usage
    
    old_code = '''
from edgar.files.html import SECHTMLParser, Document

def analyze_filing(html):
    parser = SECHTMLParser({'extract_tables': True})
    document = parser.parse(html)
    
    # Get text
    text = document.text
    
    # Search for revenue
    revenue_mentions = document.search("revenue")
    
    # Convert to markdown
    markdown = document.to_markdown()
    
    return {
        'text': text,
        'revenue_mentions': revenue_mentions,
        'markdown': markdown
    }
'''
    
    new_code = migrate_parser_usage(old_code)
    
    print("OLD CODE:")
    print(old_code)
    print("\nMIGRATED CODE:")
    print(new_code)


if __name__ == "__main__":
    # Run examples
    import warnings
    
    # Show deprecation warnings
    warnings.filterwarnings('always', category=DeprecationWarning)
    
    # Run old parser example (will show warnings)
    old_parser_example()
    
    # Run new parser example
    new_parser_example()
    
    # Show comparison
    migration_comparison()
    
    # Show automatic migration
    automatic_migration_example()
    
    # Print full migration guide
    print("\n" + "="*50)
    from edgar.documents.migration import MigrationGuide
    MigrationGuide.print_migration_guide()