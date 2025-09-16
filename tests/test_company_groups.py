"""
Company Group Testing Framework

A simple and elegant way to test features across curated groups of companies
using the company-subsets API as the foundation.

Example usage:
    @test_on_company_group(nasdaq_top20)
    def test_standardized_concepts(company):
        facts = company.get_facts()
        assert facts.get_revenue() is not None

    @test_on_company_group("tech_giants", max_failures=2)
    def test_financial_ratios(company):
        # Test logic here
        pass
"""

import pytest
from functools import wraps
from typing import Union, Callable, Optional, List
import pandas as pd
from dataclasses import dataclass

from edgar import Company
from edgar.core import set_identity
from edgar.reference.company_subsets import (
    CompanySubset,
    get_popular_companies,
    get_tech_giants,
    get_faang_companies,
    get_dow_jones_sample,
    PopularityTier
)


# Set identity for SEC API requests
set_identity("EdgarTools Test Suite test@edgartools.dev")


@dataclass
class TestResult:
    """Result of testing a single company."""
    ticker: str
    cik: int
    name: str
    success: bool
    error: Optional[str] = None
    duration: Optional[float] = None


@dataclass
class GroupTestResult:
    """Aggregated results from testing a company group."""
    group_name: str
    total_companies: int
    successful: int
    failed: int
    skipped: int
    results: List[TestResult]

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_companies == 0:
            return 0.0
        return (self.successful / self.total_companies) * 100

    @property
    def failed_tickers(self) -> List[str]:
        """Get list of tickers that failed."""
        return [r.ticker for r in self.results if not r.success and r.error]

    def __str__(self) -> str:
        return (f"GroupTestResult({self.group_name}: "
                f"{self.successful}/{self.total_companies} passed, "
                f"{self.success_rate:.1f}% success rate)")


# Pre-defined company groups for common testing scenarios
COMPANY_GROUPS = {
    "nasdaq_top20": lambda: (CompanySubset()
                            .from_exchange("Nasdaq")
                            .from_popular(PopularityTier.POPULAR)
                            .top(20, by="ticker")
                            .get()),

    "nyse_top20": lambda: (CompanySubset()
                          .from_exchange("NYSE")
                          .from_popular(PopularityTier.POPULAR)
                          .top(20, by="ticker")
                          .get()),

    "tech_giants": lambda: get_tech_giants(),

    "faang": lambda: get_faang_companies(),

    "dow_sample": lambda: get_dow_jones_sample().head(15),  # Smaller sample for faster tests

    "mega_cap": lambda: get_popular_companies(PopularityTier.MEGA_CAP),

    "diverse_sample": lambda: (CompanySubset()
                              .from_popular(PopularityTier.POPULAR)
                              .sample(25, random_state=42)
                              .get()),

    "financial_mixed": lambda: (CompanySubset()
                               .from_exchange(["NYSE", "Nasdaq"])
                               .sample(30, random_state=123)
                               .get())
}


def get_company_group(group: Union[str, pd.DataFrame, Callable]) -> pd.DataFrame:
    """
    Get a company group from various sources.

    Args:
        group: Company group identifier - can be:
               - String key from COMPANY_GROUPS
               - DataFrame with company data
               - Callable that returns DataFrame

    Returns:
        DataFrame with company information
    """
    if isinstance(group, str):
        if group not in COMPANY_GROUPS:
            raise ValueError(f"Unknown company group: {group}. "
                           f"Available groups: {list(COMPANY_GROUPS.keys())}")
        return COMPANY_GROUPS[group]()
    elif isinstance(group, pd.DataFrame):
        return group
    elif callable(group):
        return group()
    else:
        raise ValueError(f"Invalid group type: {type(group)}")


def test_on_company_group(
    group: Union[str, pd.DataFrame, Callable],
    max_failures: int = 5,
    skip_on_error: bool = True,
    timeout_per_company: int = 30
):
    """
    Decorator to test a function across a group of companies.

    Args:
        group: Company group to test on
        max_failures: Maximum failures before stopping test
        skip_on_error: If True, continue testing other companies on error
        timeout_per_company: Max seconds per company (future enhancement)

    Example:
        @test_on_company_group("tech_giants", max_failures=2)
        def test_revenue_available(company):
            facts = company.get_facts()
            revenue = facts.get_revenue()
            assert revenue is not None, "Revenue should be available"
            assert revenue > 0, "Revenue should be positive"
    """
    def decorator(test_func: Callable):
        @wraps(test_func)
        def wrapper(*args, **kwargs):
            import time

            # Get the company group
            companies_df = get_company_group(group)
            group_name = group if isinstance(group, str) else "custom_group"

            results = []
            failures = 0

            print(f"\n🧪 Testing {test_func.__name__} on {group_name} group")
            print(f"📊 Testing {len(companies_df)} companies...")

            for idx, (_, company_info) in enumerate(companies_df.iterrows()):
                ticker = company_info['ticker']
                cik = company_info['cik']
                name = company_info['name']

                start_time = time.time()

                try:
                    # Create company object and run test
                    company = Company(ticker)
                    test_func(company, *args, **kwargs)

                    duration = time.time() - start_time
                    result = TestResult(
                        ticker=ticker,
                        cik=cik,
                        name=name,
                        success=True,
                        duration=duration
                    )
                    print(f"  ✅ {ticker}: PASSED ({duration:.1f}s)")

                except Exception as e:
                    duration = time.time() - start_time
                    failures += 1

                    result = TestResult(
                        ticker=ticker,
                        cik=cik,
                        name=name,
                        success=False,
                        error=str(e),
                        duration=duration
                    )
                    print(f"  ❌ {ticker}: FAILED - {str(e)[:100]}")

                    # Stop if we hit max failures
                    if failures >= max_failures:
                        print(f"  🛑 Stopping after {max_failures} failures")
                        # Add remaining companies as skipped
                        for _, remaining_info in companies_df.iloc[idx+1:].iterrows():
                            results.append(TestResult(
                                ticker=remaining_info['ticker'],
                                cik=remaining_info['cik'],
                                name=remaining_info['name'],
                                success=False
                            ))
                        break

                    if not skip_on_error:
                        raise

                results.append(result)

            # Calculate summary
            successful = sum(1 for r in results if r.success)
            failed = sum(1 for r in results if not r.success and r.error)
            skipped = sum(1 for r in results if not r.success and not r.error)

            group_result = GroupTestResult(
                group_name=group_name,
                total_companies=len(companies_df),
                successful=successful,
                failed=failed,
                skipped=skipped,
                results=results
            )

            # Print summary
            print(f"\n📈 {group_result}")
            if group_result.failed_tickers:
                print(f"❌ Failed: {', '.join(group_result.failed_tickers[:10])}")
                if len(group_result.failed_tickers) > 10:
                    print(f"   ... and {len(group_result.failed_tickers) - 10} more")

            # Assert overall success based on success rate
            min_success_rate = 80.0  # Require 80% success rate
            if group_result.success_rate < min_success_rate:
                pytest.fail(f"Group test failed: {group_result.success_rate:.1f}% success rate "
                          f"(minimum required: {min_success_rate}%)")

            return group_result

        return wrapper
    return decorator


# Convenience decorators for common groups
def test_on_tech_giants(max_failures: int = 3):
    """Test on major technology companies."""
    return test_on_company_group("tech_giants", max_failures=max_failures)


def test_on_nasdaq_top20(max_failures: int = 4):
    """Test on top 20 NASDAQ companies."""
    return test_on_company_group("nasdaq_top20", max_failures=max_failures)


def test_on_diverse_sample(max_failures: int = 5):
    """Test on diverse sample of popular companies."""
    return test_on_company_group("diverse_sample", max_failures=max_failures)


# Example test classes using the framework
class TestStandardizedConceptsOnGroups:
    """Test standardized financial concepts across company groups."""

    @test_on_tech_giants(max_failures=2)
    def test_revenue_standardization(self, company):
        """Test that revenue standardization works across tech companies."""
        facts = company.get_facts()
        revenue = facts.get_revenue()

        assert revenue is not None, f"{company.ticker} should have revenue data"
        assert revenue > 1_000_000_000, f"{company.ticker} revenue should be > $1B"

    @test_on_company_group("mega_cap", max_failures=1)
    def test_complete_financial_metrics(self, company):
        """Test that mega-cap companies have complete financial metrics."""
        facts = company.get_facts()

        # All these methods should return values for mega-cap companies
        revenue = facts.get_revenue()
        net_income = facts.get_net_income()
        assets = facts.get_total_assets()

        assert revenue is not None, f"{company.ticker} missing revenue"
        assert net_income is not None, f"{company.ticker} missing net income"
        assert assets is not None, f"{company.ticker} missing assets"

        # Basic financial relationships
        assert assets > revenue, f"{company.ticker} assets should be > revenue"

    @test_on_diverse_sample(max_failures=5)
    def test_concept_mapping_robustness(self, company):
        """Test that concept mapping works across diverse companies."""
        facts = company.get_facts()

        # At least one of these should be available
        metrics = [
            facts.get_revenue(),
            facts.get_net_income(),
            facts.get_total_assets()
        ]

        available_metrics = [m for m in metrics if m is not None]
        assert len(available_metrics) > 0, f"{company.ticker} has no standardized metrics available"


# Custom group examples
def create_custom_healthcare_group():
    """Example of creating a custom company group."""
    return (CompanySubset()
            .from_exchange(["NYSE", "Nasdaq"])
            .filter_by(lambda df: df['name'].str.contains('health|medical|pharma|bio', case=False))
            .sample(15, random_state=42)
            .get())


def create_custom_size_stratified_group():
    """Example of size-stratified group using multiple tiers."""
    mega_cap = get_popular_companies(PopularityTier.MEGA_CAP).head(5)
    popular = (CompanySubset()
              .from_popular(PopularityTier.POPULAR)
              .exclude_tickers(mega_cap['ticker'].tolist())
              .sample(10, random_state=42)
              .get())

    from edgar.reference.company_subsets import combine_company_sets
    return combine_company_sets([mega_cap, popular])


class TestCustomGroups:
    """Examples of testing with custom company groups."""

    @test_on_company_group(create_custom_healthcare_group, max_failures=3)
    def test_healthcare_companies(self, company):
        """Test standardized concepts on healthcare companies."""
        facts = company.get_facts()

        # Healthcare companies should have basic financial data
        revenue = facts.get_revenue()
        if revenue is not None:
            assert revenue > 0, f"{company.ticker} revenue should be positive"

    @test_on_company_group(create_custom_size_stratified_group, max_failures=2)
    def test_size_stratified_consistency(self, company):
        """Test that standardized methods work across company sizes."""
        facts = company.get_facts()

        # Should be able to get concept mapping info
        revenue_concepts = ['Revenue', 'Revenues', 'NetSales']
        info = facts.get_concept_mapping_info(revenue_concepts)

        # Should have at least some concept information
        assert len(info['available']) + len(info['missing']) == len(revenue_concepts)


if __name__ == "__main__":
    # Demo usage
    print("🚀 Company Group Testing Framework Demo")
    print("=" * 50)

    # Show available groups
    print(f"📋 Available company groups: {list(COMPANY_GROUPS.keys())}")

    # Demo a simple test
    @test_on_company_group("faang", max_failures=1)
    def demo_test(company):
        facts = company.get_facts()
        revenue = facts.get_revenue()
        assert revenue is not None
        return revenue

    try:
        result = demo_test()
        print(f"✅ Demo completed: {result}")
    except Exception as e:
        print(f"❌ Demo failed: {e}")