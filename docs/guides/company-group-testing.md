# Company Group Testing Framework

A simple and elegant approach to test EdgarTools features across curated groups of companies using the `edgar.reference.company_subsets` API as the foundation.

## Overview

Traditional testing often focuses on individual companies or small hardcoded sets. The Company Group Testing framework enables systematic testing across diverse, curated company groups to ensure features work robustly across different:

- **Company sizes** (mega-cap, mid-cap, small-cap)
- **Industries** (tech, finance, healthcare, retail)
- **Exchanges** (NYSE, NASDAQ, OTC)
- **Data quality levels** (comprehensive vs. sparse filings)

## Key Benefits

✅ **Representative Testing**: Test across statistically meaningful company samples
✅ **Edge Case Discovery**: Identify compatibility issues with different company types
✅ **Success Rate Metrics**: Measure feature robustness with quantified success rates
✅ **Maintainable**: Leverage existing company-subsets infrastructure
✅ **Flexible**: Easy to create custom groups for specific testing needs

## Basic Usage

### Quick Example

```python
from edgar.reference.company_subsets import get_tech_giants

def test_standardized_concepts_on_tech_giants():
    """Test new standardized API on major tech companies."""
    tech_companies = get_tech_giants().head(10)

    passed = 0
    for _, company_info in tech_companies.iterrows():
        try:
            company = Company(company_info['ticker'])
            facts = company.get_facts()

            # Test the feature
            revenue = facts.get_revenue()
            assert revenue is not None
            assert revenue > 1_000_000_000  # Tech giants should have >$1B revenue

            passed += 1
            print(f"✅ {company_info['ticker']}: ${revenue/1e9:.1f}B")

        except Exception as e:
            print(f"❌ {company_info['ticker']}: {str(e)[:50]}")

    success_rate = (passed / len(tech_companies)) * 100
    print(f"Success Rate: {passed}/{len(tech_companies)} ({success_rate:.1f}%)")

    assert success_rate >= 80, "Feature should work on 80%+ of tech giants"
```

### Available Company Groups

The framework provides pre-defined groups via `company_subsets`:

```python
from edgar.reference.company_subsets import (
    get_faang_companies,      # Meta, Apple, Amazon, Netflix, Google
    get_tech_giants,          # Major technology companies
    get_dow_jones_sample,     # Dow Jones Industrial Average sample
    get_popular_companies,    # Popular stocks by tier
    CompanySubset             # Fluent interface for custom groups
)

# Pre-defined groups
faang = get_faang_companies()                    # 5 companies
tech_giants = get_tech_giants()                  # ~13 companies
mega_cap = get_popular_companies(PopularityTier.MEGA_CAP)  # Top 10

# Custom groups using fluent interface
nasdaq_sample = (CompanySubset()
                .from_exchange("Nasdaq")
                .from_popular(PopularityTier.POPULAR)
                .sample(20, random_state=42)
                .get())
```

## Testing Patterns

### Pattern 1: Systematic Feature Validation

Test a new feature across multiple company groups:

```python
def validate_standardized_concepts():
    """Validate FEAT-411 standardized concepts across company groups."""

    groups_to_test = [
        ("FAANG", get_faang_companies()),
        ("Tech Giants", get_tech_giants().head(10)),
        ("Mega Cap", get_popular_companies(PopularityTier.MEGA_CAP)),
        ("NYSE Sample", CompanySubset().from_exchange("NYSE").sample(15).get())
    ]

    overall_results = []

    for group_name, companies in groups_to_test:
        print(f"\n🧪 Testing {group_name} ({len(companies)} companies)")

        group_passed = 0
        for _, company_info in companies.iterrows():
            try:
                company = Company(company_info['ticker'])
                facts = company.get_facts()

                # Test core standardized methods
                revenue = facts.get_revenue()
                net_income = facts.get_net_income()
                assets = facts.get_total_assets()

                # Validation logic
                assert revenue is not None, "Revenue should be available"
                if net_income: assert isinstance(net_income, (int, float))
                if assets: assert assets > 0

                group_passed += 1
                print(f"  ✅ {company_info['ticker']}")

            except Exception as e:
                print(f"  ❌ {company_info['ticker']}: {str(e)[:60]}")

        success_rate = (group_passed / len(companies)) * 100
        overall_results.append((group_name, group_passed, len(companies), success_rate))
        print(f"  📊 {group_name}: {group_passed}/{len(companies)} ({success_rate:.1f}%)")

    # Overall assessment
    total_passed = sum(r[1] for r in overall_results)
    total_tested = sum(r[2] for r in overall_results)
    overall_rate = (total_passed / total_tested) * 100

    print(f"\n🏆 Overall: {total_passed}/{total_tested} ({overall_rate:.1f}%)")
    return overall_rate >= 75  # Require 75% overall success
```

### Pattern 2: Method-Specific Testing

Test individual methods across company diversity:

```python
def test_revenue_method_robustness():
    """Test get_revenue() method across diverse company types."""

    # Create diverse test set
    diverse_companies = (CompanySubset()
                        .from_exchange(["NYSE", "Nasdaq"])
                        .sample(50, random_state=42)
                        .get())

    results = {
        'has_revenue': 0,
        'positive_revenue': 0,
        'reasonable_values': 0,
        'concept_mapping_works': 0
    }

    for _, company_info in diverse_companies.iterrows():
        ticker = company_info['ticker']

        try:
            company = Company(ticker)
            facts = company.get_facts()

            # Test revenue method
            revenue = facts.get_revenue()

            if revenue is not None:
                results['has_revenue'] += 1

                if revenue > 0:
                    results['positive_revenue'] += 1

                    # Test reasonable value ranges (avoid unit issues)
                    if 1_000_000 < revenue < 1_000_000_000_000:  # $1M to $1T
                        results['reasonable_values'] += 1

            # Test concept mapping functionality
            revenue_concepts = ['Revenue', 'Revenues', 'NetSales']
            mapping_info = facts.get_concept_mapping_info(revenue_concepts)
            if isinstance(mapping_info, dict) and 'available' in mapping_info:
                results['concept_mapping_works'] += 1

        except Exception as e:
            print(f"Error with {ticker}: {str(e)[:50]}")

    total = len(diverse_companies)

    print("Revenue Method Robustness Results:")
    print(f"  📊 Has revenue data: {results['has_revenue']}/{total} ({results['has_revenue']/total*100:.1f}%)")
    print(f"  ✅ Positive values: {results['positive_revenue']}/{total} ({results['positive_revenue']/total*100:.1f}%)")
    print(f"  🎯 Reasonable ranges: {results['reasonable_values']}/{total} ({results['reasonable_values']/total*100:.1f}%)")
    print(f"  🔍 Mapping info works: {results['concept_mapping_works']}/{total} ({results['concept_mapping_works']/total*100:.1f}%)")

    return results
```

### Pattern 3: Performance Testing

Measure performance across company groups:

```python
import time

def performance_test_across_groups():
    """Measure standardized concept performance across company groups."""

    groups = [
        ("Small Set", get_faang_companies()),
        ("Medium Set", get_tech_giants()),
        ("Large Set", CompanySubset().from_popular().sample(30).get())
    ]

    for group_name, companies in groups:
        print(f"\n⏱️ Performance Test: {group_name}")

        start_time = time.time()
        successful_calls = 0

        for _, company_info in companies.iterrows():
            try:
                company = Company(company_info['ticker'])
                facts = company.get_facts()

                # Time the standardized method calls
                method_start = time.time()
                revenue = facts.get_revenue()
                net_income = facts.get_net_income()
                assets = facts.get_total_assets()
                method_time = time.time() - method_start

                if revenue is not None:
                    successful_calls += 1

                print(f"  {company_info['ticker']}: {method_time:.2f}s")

            except Exception as e:
                print(f"  {company_info['ticker']}: ERROR")

        total_time = time.time() - start_time
        avg_time = total_time / len(companies)

        print(f"  📈 Total: {total_time:.1f}s, Avg: {avg_time:.2f}s/company")
        print(f"  ✅ Success: {successful_calls}/{len(companies)}")
```

## Custom Company Groups

Create custom groups for specific testing scenarios:

### Industry-Specific Groups

```python
# Healthcare companies
healthcare_companies = (CompanySubset()
                       .from_exchange(["NYSE", "Nasdaq"])
                       .filter_by(lambda df: df['name'].str.contains(
                           'health|medical|pharma|bio', case=False))
                       .sample(20, random_state=42)
                       .get())

# Financial services
financial_companies = (CompanySubset()
                      .from_exchange("NYSE")
                      .filter_by(lambda df: df['name'].str.contains(
                          'bank|financial|insurance', case=False))
                      .top(15, by='ticker')
                      .get())
```

### Size-Stratified Groups

```python
# Multi-tier sample
def create_size_stratified_group():
    mega_cap = get_popular_companies(PopularityTier.MEGA_CAP).head(5)
    mid_cap = (CompanySubset()
              .from_popular(PopularityTier.POPULAR)
              .exclude_tickers(mega_cap['ticker'].tolist())
              .sample(10, random_state=42)
              .get())
    small_cap = (CompanySubset()
                .from_exchange(["NYSE", "Nasdaq"])
                .exclude_tickers(mega_cap['ticker'].tolist() + mid_cap['ticker'].tolist())
                .sample(15, random_state=42)
                .get())

    from edgar.reference.company_subsets import combine_company_sets
    return combine_company_sets([mega_cap, mid_cap, small_cap])
```

### Geographic/Exchange Groups

```python
# Exchange comparison
exchange_groups = {
    'NYSE': CompanySubset().from_exchange("NYSE").sample(25).get(),
    'NASDAQ': CompanySubset().from_exchange("Nasdaq").sample(25).get(),
    'Mixed': CompanySubset().from_exchange(["NYSE", "Nasdaq"]).sample(25).get()
}
```

## Integration with CI/CD

### Pytest Integration

```python
import pytest
from edgar.reference.company_subsets import get_tech_giants

@pytest.mark.parametrize("company_info", get_tech_giants().head(5).to_dict('records'))
def test_standardized_concepts_parametrized(company_info):
    """Pytest parametrized test using company groups."""
    company = Company(company_info['ticker'])
    facts = company.get_facts()

    revenue = facts.get_revenue()
    assert revenue is not None, f"{company_info['ticker']} should have revenue"
    assert revenue > 0, "Revenue should be positive"

def test_feature_success_rate():
    """Test that feature works on majority of companies."""
    tech_companies = get_tech_giants()

    passed = 0
    for _, company_info in tech_companies.iterrows():
        try:
            company = Company(company_info['ticker'])
            facts = company.get_facts()

            if facts.get_revenue() is not None:
                passed += 1
        except:
            continue

    success_rate = (passed / len(tech_companies)) * 100
    assert success_rate >= 70, f"Success rate {success_rate:.1f}% below 70% threshold"
```

### Performance Benchmarks

```python
def benchmark_standardized_methods():
    """Benchmark standardized methods for performance regression."""
    import time

    companies = get_popular_companies(PopularityTier.POPULAR).head(20)

    times = []
    for _, company_info in companies.iterrows():
        try:
            start = time.time()

            company = Company(company_info['ticker'])
            facts = company.get_facts()

            # Test all standardized methods
            facts.get_revenue()
            facts.get_net_income()
            facts.get_total_assets()

            elapsed = time.time() - start
            times.append(elapsed)

        except:
            continue

    if times:
        avg_time = sum(times) / len(times)
        max_time = max(times)

        print(f"Avg time: {avg_time:.2f}s, Max time: {max_time:.2f}s")

        # Performance regression checks
        assert avg_time < 3.0, f"Average time {avg_time:.2f}s too slow"
        assert max_time < 10.0, f"Max time {max_time:.2f}s too slow"
```

## Best Practices

### 1. Choose Representative Groups

```python
# Good: Diverse, representative sample
test_companies = (CompanySubset()
                 .from_exchange(["NYSE", "Nasdaq"])
                 .from_popular(PopularityTier.POPULAR)
                 .sample(30, random_state=42)  # Reproducible
                 .get())

# Avoid: Overly narrow or biased samples
# tech_only = get_tech_giants()  # Too narrow for general feature testing
```

### 2. Set Appropriate Success Thresholds

```python
# Adjust thresholds based on feature maturity and company diversity
thresholds = {
    'mega_cap': 95,      # Should work on almost all mega-cap companies
    'tech_giants': 90,   # Tech companies usually have good data
    'popular': 80,       # Popular companies generally reliable
    'diverse_sample': 70,# Diverse samples include edge cases
    'random_sample': 60  # Random samples include low-quality data
}
```

### 3. Handle Errors Gracefully

```python
def robust_group_testing(companies, test_func, max_failures=5):
    """Test with graceful error handling."""
    results = {'passed': 0, 'failed': 0, 'errors': []}

    for _, company_info in companies.iterrows():
        try:
            test_func(company_info)
            results['passed'] += 1
        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f"{company_info['ticker']}: {str(e)[:50]}")

            # Stop if too many failures
            if results['failed'] >= max_failures:
                break

    return results
```

### 4. Document Group Characteristics

```python
def analyze_group_characteristics(companies):
    """Analyze the characteristics of a company group."""
    print(f"Group Analysis ({len(companies)} companies):")
    print(f"  Exchanges: {companies['exchange'].value_counts().to_dict()}")
    print(f"  Name lengths: {companies['name'].str.len().describe()}")

    # Can help understand why certain tests pass/fail
    return companies.describe()
```

## Real-World Examples

### Example 1: FEAT-411 Validation

The standardized financial concepts feature was validated using this framework:

```python
def validate_feat_411():
    """Complete validation of FEAT-411 standardized concepts."""

    test_groups = [
        ("FAANG", get_faang_companies(), 0),        # Should be 100%
        ("Tech Giants", get_tech_giants().head(10), 1),  # Allow 1 failure
        ("Mega Cap", get_popular_companies(PopularityTier.MEGA_CAP), 1),
        ("Diverse", CompanySubset().from_popular().sample(25).get(), 5)
    ]

    overall_success = True

    for group_name, companies, max_failures in test_groups:
        passed = test_standardized_concepts_on_group(companies, max_failures)
        success_rate = (passed / len(companies)) * 100

        min_rate = 100 if max_failures == 0 else 80
        if success_rate < min_rate:
            print(f"❌ {group_name} failed: {success_rate:.1f}% < {min_rate}%")
            overall_success = False
        else:
            print(f"✅ {group_name} passed: {success_rate:.1f}%")

    return overall_success
```

### Example 2: Cross-Exchange Compatibility

```python
def test_cross_exchange_compatibility():
    """Test feature compatibility across different exchanges."""

    exchanges = ['NYSE', 'Nasdaq', 'OTC']
    results = {}

    for exchange in exchanges:
        companies = (CompanySubset()
                    .from_exchange(exchange)
                    .sample(20, random_state=42)
                    .get())

        passed = 0
        for _, company_info in companies.iterrows():
            try:
                # Test your feature here
                company = Company(company_info['ticker'])
                facts = company.get_facts()

                if facts.get_revenue() is not None:
                    passed += 1
            except:
                continue

        success_rate = (passed / len(companies)) * 100
        results[exchange] = success_rate
        print(f"{exchange}: {passed}/{len(companies)} ({success_rate:.1f}%)")

    return results
```

## Conclusion

The Company Group Testing framework transforms feature validation from ad-hoc testing to systematic, quantified validation across representative company samples. By leveraging the existing company-subsets infrastructure, it provides:

- **Comprehensive coverage** across company types and characteristics
- **Quantified success metrics** for feature robustness assessment
- **Maintainable test code** using existing, well-tested infrastructure
- **Flexible customization** for specific testing scenarios

This approach ensures EdgarTools features work reliably across the diverse landscape of SEC filers, from mega-cap tech companies to small regional businesses.