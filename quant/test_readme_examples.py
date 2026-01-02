"""
Test all Python examples from README.md to ensure they work correctly.
"""
import sys
import os
import traceback
from datetime import date

# Add parent directory to path to enable 'import quant'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_quick_start_ttm():
    """Test Quick Start - TTM Calculations example"""
    print("\n" + "="*80)
    print("TEST: Quick Start - TTM Calculations")
    print("="*80)

    try:
        from quant import QuantCompany

        # Create enhanced company object (drop-in replacement for edgar.Company)
        company = QuantCompany("AAPL")

        # Get TTM income statement (most recent 12 months)
        ttm_income = company.income_statement(period='ttm')
        print(ttm_income)

        # Get specific TTM metrics
        ttm_revenue = company.get_ttm_revenue()
        print(f"TTM Revenue: ${ttm_revenue.value / 1e9:.1f}B as of {ttm_revenue.as_of_date}")

        # Get quarterly data with automatic Q4 derivation
        quarterly_income = company.income_statement(period='quarterly', periods=8)
        print(f"Quarterly income statement: {len(quarterly_income.items)} line items")

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_quick_start_xbrl():
    """Test Quick Start - XBRL Standardization example"""
    print("\n" + "="*80)
    print("TEST: Quick Start - XBRL Standardization")
    print("="*80)

    try:
        from quant.xbrl_standardize.extractors.ic import Evaluator
        import json
        from pathlib import Path

        # Load income statement schema
        schema_path = Path(__file__).parent / 'xbrl_standardize' / 'schemas' / 'income-statement.json'
        with open(schema_path) as f:
            schema = json.load(f)

        # Extract standardized fields from raw XBRL facts
        # Note: Concepts must include the taxonomy prefix (us-gaap:)
        facts = {
            'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax': 100000000,
            'us-gaap:NetIncomeLoss': 20000000,
            'us-gaap:EarningsPerShareBasic': 2.50
        }

        evaluator = Evaluator(mapping=schema, facts=facts)
        result = evaluator.standardize()
        revenue = result.get('revenue') or 0
        net_income = result.get('netIncome') or 0
        print(f"Extracted revenue: ${revenue:,.0f}")
        print(f"Extracted net income: ${net_income:,.0f}")

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_api_ttm_calculator():
    """Test API Reference - TTMCalculator example"""
    print("\n" + "="*80)
    print("TEST: API Reference - TTMCalculator")
    print("="*80)

    try:
        from quant.utils import TTMCalculator
        from edgar import Company

        company = Company("MSFT")
        facts = company.facts._facts
        revenue_facts = [f for f in facts if f.concept == 'us-gaap:Revenues']

        calc = TTMCalculator(revenue_facts)
        ttm = calc.calculate_ttm()

        print(f"TTM Revenue: ${ttm.value / 1e9:.1f}B")
        print(f"Periods: {ttm.periods}")
        print(f"Warning: {ttm.warning}")

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_api_ttm_trend():
    """Test API Reference - TTM Trend example"""
    print("\n" + "="*80)
    print("TEST: API Reference - TTM Trend")
    print("="*80)

    try:
        from quant.utils import TTMCalculator
        from edgar import Company

        company = Company("MSFT")
        facts = company.facts._facts
        revenue_facts = [f for f in facts if f.concept == 'us-gaap:Revenues']

        calc = TTMCalculator(revenue_facts)
        trend = calc.calculate_ttm_trend(periods=8)
        print(trend[['as_of_quarter', 'ttm_value', 'yoy_growth']])

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_api_xbrl_extraction():
    """Test API Reference - XBRL Extraction examples"""
    print("\n" + "="*80)
    print("TEST: API Reference - XBRL Extraction")
    print("="*80)

    try:
        from quant.xbrl_standardize.extractors.ic import Evaluator
        import json
        from pathlib import Path

        # Load schema
        schema_path = Path(__file__).parent / 'xbrl_standardize' / 'schemas' / 'income-statement.json'
        with open(schema_path) as f:
            schema = json.load(f)

        facts = {
            'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax': 100000000,
            'us-gaap:NetIncomeLoss': 20000000,
            'us-gaap:EarningsPerShareBasic': 2.50
        }

        evaluator = Evaluator(mapping=schema, facts=facts)
        result = evaluator.standardize()

        # Access extracted data
        revenue = result.get('revenue', 0)
        net_income = result.get('netIncome', 0)
        print(f"Revenue: ${revenue:,.0f}, Net Income: ${net_income:,.0f}")

        # Test with industry context
        evaluator_banking = Evaluator(mapping=schema, facts=facts, industry='banking')
        result_banking = evaluator_banking.standardize()
        banking_revenue = result_banking.get('revenue', 0)
        print(f"Banking extraction: Revenue ${banking_revenue:,.0f}")

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_example1_quarterly_analysis():
    """Test Example 1: Quarterly Analysis with Q4 Derivation"""
    print("\n" + "="*80)
    print("TEST: Example 1 - Quarterly Analysis with Q4 Derivation")
    print("="*80)

    try:
        from quant import QuantCompany
        import pandas as pd

        # Get company
        company = QuantCompany("NVDA")

        # Get 8 quarters of income statement (includes derived Q4)
        stmt = company.income_statement(period='quarterly', periods=8, as_dataframe=True)

        # Analyze quarterly revenue trend
        revenue_row = stmt[stmt['label'].str.contains('Revenue', case=False, na=False)].iloc[0]
        quarters = [col for col in stmt.columns if col.startswith('Q')]
        revenue_by_quarter = {q: revenue_row[q] for q in quarters if revenue_row[q] is not None}

        print("Quarterly Revenue (includes derived Q4):")
        for quarter, value in list(revenue_by_quarter.items())[:4]:  # First 4 only
            print(f"  {quarter}: ${value/1e9:.1f}B")

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_example2_ttm_trend():
    """Test Example 2: TTM Trend Analysis"""
    print("\n" + "="*80)
    print("TEST: Example 2 - TTM Trend Analysis")
    print("="*80)

    try:
        from quant import QuantCompany
        from quant.utils import TTMCalculator

        company = QuantCompany("AAPL")
        facts = company._get_adjusted_facts()

        # Get revenue facts
        revenue_facts = [f for f in facts if 'Revenue' in f.concept and 'Contract' in f.concept]

        # Calculate TTM trend
        calc = TTMCalculator(revenue_facts)
        trend = calc.calculate_ttm_trend(periods=8)

        # Analyze growth
        print("TTM Revenue Trend:")
        print(trend[['as_of_quarter', 'ttm_value', 'yoy_growth']].head(3))

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_example3_stock_splits():
    """Test Example 3: Stock Split Detection"""
    print("\n" + "="*80)
    print("TEST: Example 3 - Stock Split Detection")
    print("="*80)

    try:
        from quant import QuantCompany
        from quant.utils import detect_splits

        company = QuantCompany("NVDA")
        facts = company.facts._facts

        # Detect splits
        splits = detect_splits(facts)

        print(f"Found {len(splits)} stock splits:")
        for split in splits[:3]:  # First 3 only
            print(f"  {split['date']}: {split['ratio']:.1f}-for-1 split")

        # Get split-adjusted EPS
        eps_facts = [f for f in company._get_adjusted_facts()
                     if 'EarningsPerShare' in f.concept and f.fiscal_period == 'Q1']

        print("\nQ1 EPS (split-adjusted):")
        for f in sorted(eps_facts, key=lambda x: x.fiscal_year)[-3:]:  # Last 3 years
            print(f"  {f.fiscal_year} Q1: ${f.numeric_value:.2f}")

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_example4_cross_company():
    """Test Example 4: Cross-Company Comparison"""
    print("\n" + "="*80)
    print("TEST: Example 4 - Cross-Company Comparison")
    print("="*80)

    try:
        from quant import QuantCompany

        # Compare companies using QuantCompany (use just 2 to save time)
        companies = ["AAPL", "MSFT"]

        for ticker in companies:
            company = QuantCompany(ticker)

            # Get TTM revenue and net income
            try:
                ttm_rev = company.get_ttm_revenue()
                ttm_ni = company.get_ttm_net_income()

                print(f"\n{ticker}:")
                print(f"  TTM Revenue: ${ttm_rev.value/1e9:.1f}B (as of {ttm_rev.as_of_date})")
                print(f"  TTM Net Income: ${ttm_ni.value/1e9:.1f}B (as of {ttm_ni.as_of_date})")
                print(f"  Q4 Calculated: {ttm_rev.has_calculated_q4}")
            except Exception as e:
                print(f"{ticker}: Error - {e}")

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def test_example5_ttm_vs_annual():
    """Test Example 5: TTM vs Annual Comparison"""
    print("\n" + "="*80)
    print("TEST: Example 5 - TTM vs Annual Comparison")
    print("="*80)

    try:
        from quant import QuantCompany

        company = QuantCompany("MSFT")

        # Get annual income statement
        annual = company.income_statement(period='annual', periods=1)

        # Get TTM income statement
        ttm = company.income_statement(period='ttm')

        # Get TTM metrics for comparison
        ttm_rev = company.get_ttm_revenue()
        ttm_ni = company.get_ttm_net_income()

        print("Revenue Comparison:")
        print(f"  TTM Revenue: ${ttm_rev.value/1e9:.1f}B (as of {ttm_rev.as_of_date})")
        print(f"  TTM periods: {ttm_rev.periods}")
        print(f"  Has calculated Q4: {ttm_rev.has_calculated_q4}")
        print(f"\nNet Income:")
        print(f"  TTM: ${ttm_ni.value/1e9:.1f}B")

        print("✅ PASSED")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("TESTING ALL README.md PYTHON EXAMPLES")
    print("="*80)

    tests = [
        ("Quick Start - TTM", test_quick_start_ttm),
        ("Quick Start - XBRL", test_quick_start_xbrl),
        ("API - TTMCalculator", test_api_ttm_calculator),
        ("API - TTM Trend", test_api_ttm_trend),
        ("API - XBRL Extraction", test_api_xbrl_extraction),
        ("Example 1 - Quarterly Analysis", test_example1_quarterly_analysis),
        ("Example 2 - TTM Trend", test_example2_ttm_trend),
        ("Example 3 - Stock Splits", test_example3_stock_splits),
        ("Example 4 - Cross-Company", test_example4_cross_company),
        ("Example 5 - TTM vs Annual", test_example5_ttm_vs_annual),
    ]

    results = []
    for name, test_func in tests:
        passed = test_func()
        results.append((name, passed))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")

    print("\n" + "="*80)
    print(f"TOTAL: {passed_count}/{total_count} tests passed")
    print("="*80)

    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
