"""
Example: Using .text() methods for AI-optimized context.

This example demonstrates how to generate token-efficient context
for Large Language Models (LLMs) using EdgarTools' .text() methods.
"""

from edgar import Company, set_identity

# Set your SEC identity (required)
set_identity("Your Name your.email@example.com")


def example_1_basic_text_output():
    """Generate basic AI-optimized text output."""
    print("=" * 60)
    print("Example 1: Basic Text Output")
    print("=" * 60)

    company = Company("AAPL")

    # Generate AI-optimized text
    text = company.text()

    print("\nCompany text output (markdown-kv format):")
    print(text)

    # Estimate tokens
    estimated_tokens = len(text.split()) * 1.3
    print(f"\nEstimated tokens: ~{estimated_tokens:.0f}")


def example_2_detail_levels():
    """Demonstrate progressive disclosure with detail levels."""
    print("\n" + "=" * 60)
    print("Example 2: Detail Levels (Progressive Disclosure)")
    print("=" * 60)

    company = Company("MSFT")

    # Minimal - Just the essentials
    minimal = company.text(detail='minimal')
    print("\n1. MINIMAL (~100-200 tokens):")
    print(minimal)
    print(f"   Estimated tokens: ~{len(minimal.split()) * 1.3:.0f}")

    # Standard - Balanced overview
    standard = company.text(detail='standard')
    print("\n2. STANDARD (~300-500 tokens):")
    print(standard[:300] + "...")  # Show first 300 chars
    print(f"   Estimated tokens: ~{len(standard.split()) * 1.3:.0f}")

    # Detailed - Comprehensive information
    detailed = company.text(detail='detailed')
    print("\n3. DETAILED (~800-1200 tokens):")
    print(detailed[:300] + "...")  # Show first 300 chars
    print(f"   Estimated tokens: ~{len(detailed.split()) * 1.3:.0f}")


def example_3_token_limiting():
    """Control output size with token limits."""
    print("\n" + "=" * 60)
    print("Example 3: Token Limiting")
    print("=" * 60)

    company = Company("GOOGL")

    # Limit to specific token count
    text_500 = company.text(max_tokens=500)
    print("\nLimited to 500 tokens:")
    print(text_500)
    print(f"Actual tokens: ~{len(text_500.split()) * 1.3:.0f}")

    # Smaller limit
    text_250 = company.text(max_tokens=250)
    print("\nLimited to 250 tokens:")
    print(text_250)
    print(f"Actual tokens: ~{len(text_250.split()) * 1.3:.0f}")


def example_4_building_llm_context():
    """Build comprehensive context for an LLM."""
    print("\n" + "=" * 60)
    print("Example 4: Building LLM Context")
    print("=" * 60)

    company = Company("TSLA")

    # Build multi-part context
    context_parts = []
    token_budget = 1500
    tokens_used = 0

    # 1. Company overview
    company_text = company.text(detail='minimal', max_tokens=200)
    context_parts.append("# Company Overview")
    context_parts.append(company_text)
    tokens_used += len(company_text.split()) * 1.3
    print(f"\n1. Company overview: ~{len(company_text.split()) * 1.3:.0f} tokens")

    # 2. Latest filing
    filing = company.get_filings(form="10-K").latest()
    filing_text = filing.text(detail='standard', max_tokens=300)
    context_parts.append("\n# Latest 10-K Filing")
    context_parts.append(filing_text)
    tokens_used += len(filing_text.split()) * 1.3
    print(f"2. Latest filing: ~{len(filing_text.split()) * 1.3:.0f} tokens")

    # 3. Financial statement
    xbrl = filing.xbrl()
    income = xbrl.statements.income_statement()
    statement_text = income.text(max_tokens=500)
    context_parts.append("\n# Income Statement")
    context_parts.append(statement_text)
    tokens_used += len(statement_text.split()) * 1.3
    print(f"3. Income statement: ~{len(statement_text.split()) * 1.3:.0f} tokens")

    # Combine
    full_context = "\n".join(context_parts)
    print(f"\n📊 Total context: ~{tokens_used:.0f} tokens (budget: {token_budget})")

    # Preview
    print("\n--- Context Preview ---")
    print(full_context[:500] + "...")


def example_5_format_comparison():
    """Compare markdown-kv format with other formats."""
    print("\n" + "=" * 60)
    print("Example 5: Format Comparison")
    print("=" * 60)

    company = Company("NVDA")

    # Markdown-KV (default)
    markdown_kv = company.text(format='markdown-kv', detail='minimal')
    print("\n1. Markdown-KV (Default - Optimal for LLMs):")
    print(markdown_kv)
    print(f"   Tokens: ~{len(markdown_kv.split()) * 1.3:.0f}")

    # TSV format (alternative)
    tsv = company.text(format='tsv', detail='minimal')
    print("\n2. TSV (Tab-separated):")
    print(tsv)
    print(f"   Tokens: ~{len(tsv.split()) * 1.3:.0f}")

    print("\n💡 markdown-kv is research-backed as optimal for LLM comprehension")


def example_6_batch_processing():
    """Process multiple companies with token budget."""
    print("\n" + "=" * 60)
    print("Example 6: Batch Processing with Token Budget")
    print("=" * 60)

    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    token_budget = 2000
    tokens_used = 0

    results = []

    print(f"\nProcessing {len(tickers)} companies with {token_budget} token budget:\n")

    for ticker in tickers:
        company = Company(ticker)

        # Generate text with remaining budget
        remaining = token_budget - tokens_used
        if remaining < 100:
            print(f"❌ {ticker}: Insufficient token budget")
            break

        text = company.text(detail='minimal', max_tokens=min(remaining, 300))
        estimated_tokens = len(text.split()) * 1.3

        results.append({
            'ticker': ticker,
            'text': text,
            'tokens': estimated_tokens
        })

        tokens_used += estimated_tokens
        print(f"✅ {ticker}: ~{estimated_tokens:.0f} tokens")

    print(f"\n📊 Processed {len(results)}/{len(tickers)} companies")
    print(f"   Total tokens used: ~{tokens_used:.0f}/{token_budget}")


def example_7_different_objects():
    """Generate context from different object types."""
    print("\n" + "=" * 60)
    print("Example 7: Text from Different Objects")
    print("=" * 60)

    company = Company("AMD")

    print("\n1. Company text:")
    print(company.text(detail='minimal', max_tokens=150))

    print("\n2. Filing text:")
    filing = company.get_filings(form="10-K").latest()
    print(filing.text(detail='minimal', max_tokens=150))

    print("\n3. XBRL text:")
    xbrl = filing.xbrl()
    print(xbrl.text(detail='minimal', max_tokens=150))

    print("\n4. Statement text:")
    income = xbrl.statements.income_statement()
    print(income.text(max_tokens=150))

    print("\n💡 All major objects support .text() for AI context")


if __name__ == "__main__":
    print("\n🤖 EdgarTools AI Context Generation Examples\n")

    # Run all examples
    example_1_basic_text_output()
    example_2_detail_levels()
    example_3_token_limiting()
    example_4_building_llm_context()
    example_5_format_comparison()
    example_6_batch_processing()
    example_7_different_objects()

    print("\n" + "=" * 60)
    print("✅ Examples Complete!")
    print("=" * 60)
    print("\n💡 Key Takeaways:")
    print("   - Use .text() for AI-optimized output")
    print("   - Choose detail level: minimal/standard/detailed")
    print("   - Set max_tokens to fit your context window")
    print("   - markdown-kv format is optimal for LLMs")
    print("   - All major objects support .text()")
    print("\n🎯 Perfect for LangChain, LlamaIndex, or custom AI pipelines!")
