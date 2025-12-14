"""
Example demonstrating EntityFacts.to_dataframe() functionality.

This example shows how to export financial facts to pandas DataFrame
for custom analysis and exploration.
"""

from edgar import Company, set_identity
from edgar.enums import PeriodType

# Set identity as required by SEC
set_identity("Example User example@example.com")

def main():
    print("=" * 80)
    print("EntityFacts DataFrame Export Example")
    print("=" * 80)

    # Get company and facts
    company = Company("AAPL")
    print(f"\n📊 Company: {company.name}")

    # Example 1: Basic DataFrame export
    print("\n" + "=" * 80)
    print("Example 1: Basic DataFrame Export")
    print("=" * 80)

    annual_facts = company.get_facts(period_type=PeriodType.ANNUAL)
    df = annual_facts.to_dataframe()

    print(f"\n✅ Exported {len(df):,} facts to DataFrame")
    print(f"Columns: {list(df.columns)}")
    print("\nFirst 5 rows:")
    print(df.head())

    # Example 2: Filter for revenue data
    print("\n" + "=" * 80)
    print("Example 2: Filter Revenue Facts")
    print("=" * 80)

    revenue_df = df[df['concept'].str.contains('Revenue', case=False, na=False)]
    print(f"\n✅ Found {len(revenue_df)} revenue-related facts")
    print("\nRevenue data by year:")
    print(revenue_df[['concept', 'label', 'fiscal_year', 'numeric_value', 'unit']].head(10))

    # Example 3: Export with metadata
    print("\n" + "=" * 80)
    print("Example 3: DataFrame with Metadata")
    print("=" * 80)

    df_full = annual_facts.to_dataframe(include_metadata=True)
    print(f"\n✅ DataFrame with metadata has {len(df_full.columns)} columns:")
    print(f"Additional metadata columns: {[c for c in df_full.columns if c not in df.columns]}")

    # Example 4: Custom columns for specific analysis
    print("\n" + "=" * 80)
    print("Example 4: Custom Column Selection")
    print("=" * 80)

    df_slim = annual_facts.to_dataframe(
        columns=['concept', 'fiscal_year', 'numeric_value', 'unit']
    )
    print("\n✅ Slim DataFrame with selected columns:")
    print(df_slim.head())

    # Example 5: Group and analyze
    print("\n" + "=" * 80)
    print("Example 5: Aggregate Analysis")
    print("=" * 80)

    # Count facts by fiscal year
    facts_by_year = df.groupby('fiscal_year').size().sort_index(ascending=False)
    print("\n✅ Facts count by fiscal year:")
    print(facts_by_year.head(10))

    # Count unique concepts by year
    concepts_by_year = df.groupby('fiscal_year')['concept'].nunique().sort_index(ascending=False)
    print("\n✅ Unique concepts by fiscal year:")
    print(concepts_by_year.head(10))

    print("\n" + "=" * 80)
    print("✨ All examples completed successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()
