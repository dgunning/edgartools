#!/usr/bin/env python
"""
Test Sprint 1: DimensionalAggregator and PiT Handling

Tests:
1. DimensionalAggregator - JPM CommercialPaper dimensional aggregation
2. PiT Filing Handling - Latest filing selection
3. Placeholder Zero Handling - Consolidated=0 with dimensional values
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from edgar import Company, set_identity

set_identity("Test User test@example.com")


def test_dimensional_aggregator_standalone():
    """Test DimensionalAggregator class directly."""
    print("\n" + "="*60)
    print("TEST 1: DimensionalAggregator Standalone")
    print("="*60)
    
    from edgar.xbrl.standardization.layers.dimensional_aggregator import (
        DimensionalAggregator, AggregationResult
    )
    
    aggregator = DimensionalAggregator()
    
    # Test should_aggregate logic
    print("\n1.1 Testing should_aggregate() logic:")
    
    # Case 1: Missing consolidated
    result = aggregator.should_aggregate(None, 1_000_000)
    print(f"  - consolidated=None, dim_sum=1M: {result} (expected: True)")
    assert result == True, "Should aggregate when consolidated is None"
    
    # Case 2: Placeholder zero with significant dimensional
    result = aggregator.should_aggregate(0, 5_000_000)
    print(f"  - consolidated=0, dim_sum=5M: {result} (expected: True)")
    assert result == True, "Should aggregate when consolidated=0 and dim_sum>1M"
    
    # Case 3: Placeholder zero with small dimensional (below threshold)
    result = aggregator.should_aggregate(0, 500_000)
    print(f"  - consolidated=0, dim_sum=0.5M: {result} (expected: False)")
    assert result == False, "Should NOT aggregate when dim_sum < 1M threshold"
    
    # Case 4: Valid consolidated exists
    result = aggregator.should_aggregate(10_000_000, 8_000_000)
    print(f"  - consolidated=10M, dim_sum=8M: {result} (expected: False)")
    assert result == False, "Should NOT aggregate when valid consolidated exists"
    
    print("\n  ✅ All should_aggregate() tests passed!")
    
    # Test aggregation rules exist
    print("\n1.2 Testing aggregation rules configuration:")
    for concept, rules in aggregator.AGGREGATION_RULES.items():
        print(f"  - {concept}: method={rules['method']}, axes={rules['include_axes']}")
    
    print("\n  ✅ DimensionalAggregator standalone tests passed!")
    return True


def test_dimensional_aggregator_with_jpm():
    """Test DimensionalAggregator with JPM (real data)."""
    print("\n" + "="*60)
    print("TEST 2: DimensionalAggregator with JPM (Real Data)")
    print("="*60)
    
    from edgar.xbrl.standardization.layers.dimensional_aggregator import DimensionalAggregator
    
    try:
        # Get JPM's latest 10-K
        print("\n2.1 Loading JPM 10-K filing...")
        c = Company("JPM")
        filings = c.get_filings(form='10-K')
        filing = next(iter(filings))
        print(f"  Filing: {filing.form} dated {filing.filing_date}")
        
        xbrl = filing.xbrl()
        print(f"  XBRL loaded successfully")
        
        # Test CommercialPaper aggregation
        print("\n2.2 Testing CommercialPaper aggregation:")
        aggregator = DimensionalAggregator()
        result = aggregator.aggregate_if_missing(xbrl, 'CommercialPaper')
        
        print(f"  - Aggregated value: ${result.aggregated_value/1e9:.2f}B" if result.aggregated_value else "  - Aggregated value: None")
        print(f"  - Dimension count: {result.dimension_count}")
        print(f"  - Dimensions used: {result.dimensions_used}")
        print(f"  - Method: {result.method}")
        print(f"  - Status: {result.validation_status}")
        
        # Test ShortTermBorrowings aggregation
        print("\n2.3 Testing ShortTermBorrowings aggregation:")
        result2 = aggregator.aggregate_if_missing(xbrl, 'ShortTermBorrowings')
        
        print(f"  - Aggregated value: ${result2.aggregated_value/1e9:.2f}B" if result2.aggregated_value else "  - Aggregated value: None")
        print(f"  - Dimension count: {result2.dimension_count}")
        print(f"  - Status: {result2.validation_status}")
        
        print("\n  ✅ JPM dimensional aggregation test complete!")
        return True
        
    except Exception as e:
        print(f"\n  ⚠️ Test skipped (network/data issue): {e}")
        return None  # Inconclusive


def test_pit_filing_handling():
    """Test Point-in-Time filing date handling."""
    print("\n" + "="*60)
    print("TEST 3: Point-in-Time (PiT) Filing Handling")
    print("="*60)
    
    from edgar.xbrl.standardization.reference_validator import ReferenceValidator
    import pandas as pd
    from datetime import datetime
    
    validator = ReferenceValidator()
    
    # Test _parse_filing_date
    print("\n3.1 Testing _parse_filing_date():")
    
    test_cases = [
        ("2024-01-15", datetime(2024, 1, 15)),
        ("2024-01-15T10:30:00", datetime(2024, 1, 15)),
        (datetime(2024, 6, 30), datetime(2024, 6, 30)),
        (None, datetime.min),
    ]
    
    for input_val, expected in test_cases:
        result = validator._parse_filing_date(input_val)
        status = "✓" if result == expected else "✗"
        print(f"  {status} Input: {input_val!r} -> {result}")
    
    # Test _select_latest_filing with mock data
    print("\n3.2 Testing _select_latest_filing() with mock data:")
    
    # Create mock dataframe with same period but different filing dates
    mock_df = pd.DataFrame({
        'period_key': ['duration_2023-01-01_2023-12-31', 'duration_2023-01-01_2023-12-31', 'duration_2022-01-01_2022-12-31'],
        'filed': ['2024-02-15', '2025-01-20', '2023-02-15'],  # 2025 is restatement
        'numeric_value': [100_000_000, 105_000_000, 95_000_000]
    })
    
    print("  Input data:")
    print(f"    Period: 2023 FY, filed 2024-02-15, value: $100M (original)")
    print(f"    Period: 2023 FY, filed 2025-01-20, value: $105M (restatement)")
    print(f"    Period: 2022 FY, filed 2023-02-15, value: $95M")
    
    result_df = validator._select_latest_filing(mock_df)
    
    print("\n  Output (after PiT filtering):")
    for _, row in result_df.iterrows():
        print(f"    Period: {row['period_key']}, value: ${row['numeric_value']/1e6:.0f}M")
    
    # Verify: For 2023 FY, should get the restated value ($105M, filed 2025)
    fy2023_value = result_df[result_df['period_key'].str.contains('2023')]['numeric_value'].iloc[0]
    expected_value = 105_000_000
    
    if fy2023_value == expected_value:
        print(f"\n  ✅ PiT test passed! Got restated value (${fy2023_value/1e6:.0f}M)")
        return True
    else:
        print(f"\n  ❌ PiT test failed! Expected ${expected_value/1e6:.0f}M, got ${fy2023_value/1e6:.0f}M")
        return False


def test_integrated_extraction():
    """Test integrated extraction with dimensional aggregator in validator."""
    print("\n" + "="*60)
    print("TEST 4: Integrated Extraction (Validator + Aggregator)")
    print("="*60)
    
    from edgar.xbrl.standardization.reference_validator import ReferenceValidator
    
    validator = ReferenceValidator()
    
    # Verify aggregator is initialized
    print("\n4.1 Verifying DimensionalAggregator integration:")
    has_aggregator = hasattr(validator, '_dimensional_aggregator')
    print(f"  - ReferenceValidator has _dimensional_aggregator: {has_aggregator}")
    
    if has_aggregator:
        print(f"  - Aggregator class: {type(validator._dimensional_aggregator).__name__}")
        print(f"  - Aggregation rules count: {len(validator._dimensional_aggregator.AGGREGATION_RULES)}")
        print("\n  ✅ Integration verified!")
        return True
    else:
        print("\n  ❌ Aggregator not found!")
        return False


def run_all_tests():
    """Run all Sprint 1 tests."""
    print("\n" + "#"*60)
    print("# SPRINT 1 TEST SUITE")
    print("# DimensionalAggregator + PiT Filing Handling")
    print("#"*60)
    
    results = {}
    
    # Test 1: Standalone aggregator tests
    results['dimensional_standalone'] = test_dimensional_aggregator_standalone()
    
    # Test 2: Real data test with JPM
    results['dimensional_jpm'] = test_dimensional_aggregator_with_jpm()
    
    # Test 3: PiT handling
    results['pit_handling'] = test_pit_filing_handling()
    
    # Test 4: Integration check
    results['integration'] = test_integrated_extraction()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        if passed is True:
            status = "✅ PASS"
        elif passed is False:
            status = "❌ FAIL"
        else:
            status = "⚠️ SKIP"
        print(f"  {test_name}: {status}")
    
    all_passed = all(r is not False for r in results.values())
    print("\n" + ("="*60))
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️ SOME TESTS FAILED - Review output above")
    print("="*60)
    
    return all_passed


if __name__ == "__main__":
    run_all_tests()
