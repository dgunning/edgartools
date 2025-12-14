"""
Example: Using the .docs property for interactive documentation.

This example demonstrates how to use EdgarTools' built-in documentation
system to learn the API interactively without leaving your Python environment.
"""

from edgar import Company, set_identity

# Set your SEC identity (required)
set_identity("Your Name your.email@example.com")

def example_1_display_docs():
    """Display rich documentation for a Company object."""
    print("=" * 60)
    print("Example 1: Displaying Documentation")
    print("=" * 60)

    company = Company("AAPL")

    # Display rich, formatted documentation
    # This shows the complete API reference in your terminal
    print("\nDisplaying Company documentation...")
    print("(In a real terminal, this would show beautifully formatted rich output)")

    # In an actual Python REPL or Jupyter notebook, just type:
    # company.docs
    # This displays the full documentation with syntax highlighting

    print("\nDocumentation includes:")
    print("- Complete method reference")
    print("- Parameter descriptions")
    print("- Return types")
    print("- Usage examples")
    print("- Best practices")


def example_2_search_docs():
    """Search documentation for specific functionality."""
    print("\n" + "=" * 60)
    print("Example 2: Searching Documentation")
    print("=" * 60)

    company = Company("AAPL")

    # Search for specific functionality using BM25 semantic search
    query = "get financials"
    print(f"\nSearching docs for: '{query}'")

    results = company.docs.search(query)

    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results[:3], 1):
        print(f"\n{i}. Relevance Score: {result.score:.2f}")
        print(f"   Excerpt: {result.text[:200]}...")


def example_3_docs_on_different_objects():
    """Access documentation on different EdgarTools objects."""
    print("\n" + "=" * 60)
    print("Example 3: Documentation on Different Objects")
    print("=" * 60)

    company = Company("AAPL")

    # Every major object has documentation
    print("\n1. Company documentation:")
    print("   Available via: company.docs")
    print("   Size: ~1,070 lines")

    # Get a filing
    filings = company.get_filings(form="10-K")
    filing = filings.latest()

    print("\n2. Filing documentation:")
    print("   Available via: filing.docs")
    print("   Size: ~557 lines")

    # Get XBRL data
    xbrl = filing.xbrl()

    print("\n3. XBRL documentation:")
    print("   Available via: xbrl.docs")
    print("   Size: ~587 lines")

    # Get a statement
    income = xbrl.statements.income_statement()

    print("\n4. Statement documentation:")
    print("   Available via: income.docs")
    print("   Size: ~567 lines")

    print("\n📚 Total documentation: 3,450+ lines!")


def example_4_learning_workflow():
    """Demonstrate a typical learning workflow."""
    print("\n" + "=" * 60)
    print("Example 4: Learning Workflow")
    print("=" * 60)

    company = Company("MSFT")

    # Step 1: Browse general documentation
    print("\nStep 1: Explore the Company object")
    print(">>> company.docs")
    print("(Displays full API reference)")

    # Step 2: Search for specific functionality
    print("\nStep 2: Search for what you need")
    print(">>> company.docs.search('get filings')")

    results = company.docs.search("get filings")
    if results:
        print(f"Found {len(results)} relevant sections")
        print(f"Top result: {results[0].text[:150]}...")

    # Step 3: Try the code
    print("\nStep 3: Try the code from examples")
    print(">>> filings = company.get_filings(form='10-K')")

    filings = company.get_filings(form="10-K")
    print(f"✅ Retrieved {len(filings)} 10-K filings")

    # Step 4: Learn about the result object
    print("\nStep 4: Learn about the result")
    print(">>> filings.docs")
    print("(Shows EntityFilings documentation)")

    print("\n💡 Documentation is always just a .docs away!")


def example_5_quick_reference():
    """Quick reference for common searches."""
    print("\n" + "=" * 60)
    print("Example 5: Quick Reference Searches")
    print("=" * 60)

    company = Company("GOOGL")

    # Common search queries
    searches = [
        "get financials",
        "filing dates",
        "XBRL statements",
        "filter filings",
        "pandas dataframe"
    ]

    print("\nCommon documentation searches:\n")
    for query in searches:
        results = company.docs.search(query)
        print(f"'{query}' → {len(results)} results")


if __name__ == "__main__":
    print("\n🤖 EdgarTools Interactive Documentation Examples\n")

    # Run all examples
    example_1_display_docs()
    example_2_search_docs()
    example_3_docs_on_different_objects()
    example_4_learning_workflow()
    example_5_quick_reference()

    print("\n" + "=" * 60)
    print("✅ Examples Complete!")
    print("=" * 60)
    print("\n💡 Try these in an interactive Python session:")
    print("   - company.docs            # Display documentation")
    print("   - company.docs.search(...)  # Search documentation")
    print("   - filing.docs             # Docs on any object")
    print("\n📚 3,450+ lines of documentation always at your fingertips!")
