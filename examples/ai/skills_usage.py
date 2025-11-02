"""
Example: Using AI Skills for SEC analysis workflows.

This example demonstrates how to use EdgarTools' AI Skills system
for specialized SEC analysis tasks and helper functions.
"""

from edgar import set_identity

# Set your SEC identity (required)
set_identity("Your Name your.email@example.com")


def example_1_list_skills():
    """List all available skills."""
    print("=" * 60)
    print("Example 1: Listing Available Skills")
    print("=" * 60)

    from edgar.ai import list_skills

    # Get all available skills
    skills = list_skills()

    print(f"\nFound {len(skills)} skill(s):\n")
    for skill in skills:
        print(f"📦 {skill.name}")
        print(f"   {skill.description}")
        print(f"   Documents: {len(skill.get_documents())}")
        print(f"   Helpers: {len(skill.get_helpers())}")
        print()


def example_2_get_skill():
    """Get a specific skill by name."""
    print("\n" + "=" * 60)
    print("Example 2: Getting a Specific Skill")
    print("=" * 60)

    from edgar.ai import get_skill

    # Get the SEC Filing Analysis skill
    skill = get_skill("SEC Filing Analysis")

    print(f"\n{skill}")

    # List available documents
    print("\nAvailable documents:")
    for doc in skill.get_documents():
        print(f"  - {doc}.md")

    # List helper functions
    print("\nAvailable helper functions:")
    for name, func in skill.get_helpers().items():
        print(f"  - {name}()")


def example_3_use_helper_functions():
    """Use helper functions from a skill."""
    print("\n" + "=" * 60)
    print("Example 3: Using Helper Functions")
    print("=" * 60)

    from edgar.ai.helpers import (
        get_revenue_trend,
        get_filing_statement,
        compare_companies_revenue
    )

    # 1. Get revenue trend
    print("\n1. Get Revenue Trend (3 years):")
    income = get_revenue_trend("AAPL", periods=3)
    print(income)

    # 2. Get specific statement from filing
    print("\n2. Get Balance Sheet from 2023 10-K:")
    balance = get_filing_statement("MSFT", 2023, "10-K", "balance")
    if balance:
        print(f"   ✅ Retrieved balance sheet with {len(balance.concept)} items")
    else:
        print("   ℹ️  Balance sheet not available")

    # 3. Compare companies
    print("\n3. Compare Revenue Across Companies:")
    comparison = compare_companies_revenue(["AAPL", "MSFT", "GOOGL"], periods=3)

    for ticker, stmt in comparison.items():
        if stmt:
            print(f"\n   {ticker}:")
            print(f"   {stmt}")


def example_4_filing_helpers():
    """Use filing access helper functions."""
    print("\n" + "=" * 60)
    print("Example 4: Filing Access Helpers")
    print("=" * 60)

    from edgar.ai.helpers import get_filings_by_period, get_today_filings

    # 1. Get published filings for specific period
    print("\n1. Get 10-K filings from Q1 2023:")
    filings = get_filings_by_period(2023, 1, form="10-K")
    print(f"   Found {len(filings)} filings")
    if len(filings) > 0:
        print(f"   Example: {filings[0].company} - {filings[0].filing_date}")

    # 2. Get today's filings
    print("\n2. Get today's filings:")
    current = get_today_filings()
    print(f"   Found {len(current)} recent filings")
    if len(current) > 0:
        print(f"   Latest: {current[0].company} - {current[0].form}")


def example_5_access_documentation():
    """Access skill documentation."""
    print("\n" + "=" * 60)
    print("Example 5: Accessing Skill Documentation")
    print("=" * 60)

    from edgar.ai import get_skill

    skill = get_skill("SEC Filing Analysis")

    # Get list of documents
    docs = skill.get_documents()
    print(f"\nAvailable documents: {', '.join(docs)}")

    # Get content of a specific document
    print("\n📄 README content (first 500 chars):")
    readme = skill.get_document_content("readme")
    print(readme[:500] + "...")


def example_6_export_skill():
    """Export a skill to Claude Desktop format."""
    print("\n" + "=" * 60)
    print("Example 6: Exporting Skills")
    print("=" * 60)

    from edgar.ai import get_skill
    import tempfile

    skill = get_skill("SEC Filing Analysis")

    # Export to temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Export as directory
        output_dir = skill.export(
            format="claude-desktop",
            output_dir=tmpdir
        )

        print(f"\n✅ Skill exported to: {output_dir}")
        print(f"   Format: Claude Desktop Skills")

        # List exported files
        import os
        print("\n   Exported files:")
        for root, dirs, files in os.walk(output_dir):
            level = root.replace(str(output_dir), '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")


def example_7_skill_workflow():
    """Complete workflow using skills."""
    print("\n" + "=" * 60)
    print("Example 7: Complete Analysis Workflow")
    print("=" * 60)

    from edgar.ai.helpers import (
        get_revenue_trend,
        compare_companies_revenue
    )

    # Scenario: Compare tech giants' revenue trends

    print("\n🎯 Goal: Analyze and compare FAANG revenue trends\n")

    # Step 1: Define companies
    companies = ["META", "AAPL", "AMZN", "NFLX", "GOOGL"]
    print(f"1. Companies: {', '.join(companies)}")

    # Step 2: Get revenue trends
    print("\n2. Fetching 3-year revenue trends...")
    comparison = compare_companies_revenue(companies, periods=3)

    # Step 3: Analyze results
    print("\n3. Analysis Results:\n")
    for ticker, income in comparison.items():
        if income:
            print(f"   ✅ {ticker}: Revenue data retrieved")
            # Could do more analysis here
        else:
            print(f"   ⚠️  {ticker}: Data not available")

    print("\n4. ✅ Workflow complete!")
    print("   💡 Results ready for further analysis or AI processing")


def example_8_custom_workflow():
    """Build a custom workflow with helpers."""
    print("\n" + "=" * 60)
    print("Example 8: Custom Analysis Workflow")
    print("=" * 60)

    from edgar.ai.helpers import get_revenue_trend, get_filing_statement

    ticker = "TSLA"

    print(f"\n🚗 Custom Analysis: {ticker}\n")

    # 1. Get revenue trend
    print("1. Revenue Trend Analysis:")
    income = get_revenue_trend(ticker, periods=3)
    if income:
        print(f"   ✅ Retrieved 3-year income statement")

    # 2. Get balance sheet
    print("\n2. Balance Sheet Analysis:")
    balance = get_filing_statement(ticker, 2023, "10-K", "balance")
    if balance:
        print(f"   ✅ Retrieved balance sheet")

    # 3. Get cash flow
    print("\n3. Cash Flow Analysis:")
    cash_flow = get_filing_statement(ticker, 2023, "10-K", "cash_flow")
    if cash_flow:
        print(f"   ✅ Retrieved cash flow statement")

    print("\n4. ✅ Custom analysis complete!")
    print("   📊 All financial statements retrieved and ready for analysis")


if __name__ == "__main__":
    print("\n🤖 EdgarTools AI Skills Examples\n")

    # Run all examples
    example_1_list_skills()
    example_2_get_skill()
    example_3_use_helper_functions()
    example_4_filing_helpers()
    example_5_access_documentation()
    example_6_export_skill()
    example_7_skill_workflow()
    example_8_custom_workflow()

    print("\n" + "=" * 60)
    print("✅ Examples Complete!")
    print("=" * 60)
    print("\n💡 Key Takeaways:")
    print("   - list_skills() to see available skills")
    print("   - get_skill() to access a specific skill")
    print("   - Use helper functions for common workflows")
    print("   - Export skills for AI tool integration")
    print("   - Skills combine docs + helpers + examples")
    print("\n🎯 Perfect for building specialized analysis tools!")
