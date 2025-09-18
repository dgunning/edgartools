"""
Example showing how to migrate from old parser to new.
"""

def old_parser_example():
    """Example using old parser API."""

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

    # Search
    document.search("revenue")

    # Convert to markdown
    document.to_markdown()


def new_parser_example():
    """Example using new parser API."""

    # New imports
    from edgar.documents import DocumentSearch, HTMLParser, ParserConfig
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

    # Search with new API
    search = DocumentSearch(document)
    search.search("revenue")

    # Convert to markdown with new API
    renderer = MarkdownRenderer()
    renderer.render(document)

    # New features not available in old parser

    # Advanced search
    search.find_tables(caption_pattern="Revenue")

    # Performance-optimized parser
    HTMLParser.create_for_performance()

    # Cache statistics
    from edgar.documents.utils import get_cache_manager
    get_cache_manager().get_stats()


def migration_comparison():
    """Show side-by-side comparison."""




def automatic_migration_example():
    """Show automatic code migration."""

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

    migrate_parser_usage(old_code)



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
    from edgar.documents.migration import MigrationGuide
    MigrationGuide.print_migration_guide()
