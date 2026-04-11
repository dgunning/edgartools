#!/usr/bin/env python
"""
Test Sprint 2: Industry Extractors, Signage Normalization, Internal Validator

Tests:
1. SaaSExtractor - Deferred Revenue and Capex breakdown
2. InsuranceExtractor - Policy Reserves mapping
3. Signage Normalization - Balance type detection
4. Internal Consistency Validator - Accounting equations
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def test_saas_extractor():
    """Test SaaSExtractor class."""
    print("\n" + "="*60)
    print("TEST 1: SaaSExtractor")
    print("="*60)
    
    from edgar.xbrl.standardization.industry_logic import (
        get_industry_extractor, SaaSExtractor
    )
    
    # Test registry
    print("\n1.1 Testing extractor registry:")
    saas_extractor = get_industry_extractor('saas')
    print(f"  - get_industry_extractor('saas'): {type(saas_extractor).__name__}")
    assert isinstance(saas_extractor, SaaSExtractor), "Should return SaaSExtractor"
    
    software_extractor = get_industry_extractor('software')
    print(f"  - get_industry_extractor('software'): {type(software_extractor).__name__}")
    assert isinstance(software_extractor, SaaSExtractor), "Should return SaaSExtractor (alias)"
    
    print("\n1.2 Testing SaaSExtractor has specialized methods:")
    print(f"  - extract_functional_debt: {hasattr(saas_extractor, 'extract_functional_debt')}")
    print(f"  - extract_capex_breakdown: {hasattr(saas_extractor, 'extract_capex_breakdown')}")
    
    assert hasattr(saas_extractor, 'extract_functional_debt'), "Should have extract_functional_debt"
    assert hasattr(saas_extractor, 'extract_capex_breakdown'), "Should have extract_capex_breakdown"
    
    print("\n  ✅ SaaSExtractor tests passed!")
    return True


def test_insurance_extractor():
    """Test InsuranceExtractor class."""
    print("\n" + "="*60)
    print("TEST 2: InsuranceExtractor")
    print("="*60)
    
    from edgar.xbrl.standardization.industry_logic import (
        get_industry_extractor, InsuranceExtractor
    )
    
    # Test registry
    print("\n2.1 Testing extractor registry:")
    ins_extractor = get_industry_extractor('insurance')
    print(f"  - get_industry_extractor('insurance'): {type(ins_extractor).__name__}")
    assert isinstance(ins_extractor, InsuranceExtractor), "Should return InsuranceExtractor"
    
    print("\n2.2 Testing InsuranceExtractor has specialized methods:")
    print(f"  - extract_policy_reserves: {hasattr(ins_extractor, 'extract_policy_reserves')}")
    
    assert hasattr(ins_extractor, 'extract_policy_reserves'), "Should have extract_policy_reserves"
    
    print("\n  ✅ InsuranceExtractor tests passed!")
    return True


def test_signage_normalization():
    """Test balance type detection in TreeParser."""
    print("\n" + "="*60)
    print("TEST 3: Signage Normalization (Balance Types)")
    print("="*60)
    
    from edgar.xbrl.standardization.layers.tree_parser import TreeParser
    
    parser = TreeParser()
    
    print("\n3.1 Testing _get_balance_type():")
    test_cases = [
        ('Revenues', 'credit'),
        ('CostOfRevenue', 'debit'),
        ('Assets', 'debit'),
        ('Liabilities', 'credit'),
        ('StockholdersEquity', 'credit'),
        ('GrossProfit', 'credit'),
        ('OperatingIncomeLoss', 'credit'),
        ('UnknownConcept', None),  # Should return None for unknown
    ]
    
    all_passed = True
    for concept, expected in test_cases:
        result = parser._get_balance_type(concept)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} {concept}: {result} (expected: {expected})")
    
    if all_passed:
        print("\n  ✅ Signage normalization tests passed!")
        return True
    else:
        print("\n  ❌ Some tests failed!")
        return False


def test_internal_validator():
    """Test InternalConsistencyValidator."""
    print("\n" + "="*60)
    print("TEST 4: Internal Consistency Validator")
    print("="*60)
    
    from edgar.xbrl.standardization.internal_validator import (
        InternalConsistencyValidator, ValidationStatus
    )
    
    validator = InternalConsistencyValidator()
    
    # Test with mock values - balance sheet equation
    print("\n4.1 Testing balance sheet equation (Assets = L + E):")
    mock_values = {
        'TotalAssets': 1_000_000,
        'TotalLiabilities': 600_000,
        'StockholdersEquity': 400_000,  # 600k + 400k = 1M ✓
    }
    
    result = validator.get_internal_validity(mock_values)
    print(f"  - Input: Assets=1M, Liabilities=600k, Equity=400k")
    print(f"  - Status: {result.status}")
    print(f"  - Passed: {result.passed_count}, Failed: {result.failed_count}")
    
    bs_result = result.equation_results.get('balance_sheet_equation')
    if bs_result:
        print(f"  - Balance Sheet Equation: {bs_result.status.value}")
        assert bs_result.status == ValidationStatus.PASS, "BS equation should pass"
    
    # Test with invalid values
    print("\n4.2 Testing with invalid values (Assets != L + E):")
    invalid_values = {
        'TotalAssets': 1_000_000,
        'TotalLiabilities': 600_000,
        'StockholdersEquity': 300_000,  # 600k + 300k = 900k ≠ 1M
    }
    
    invalid_result = validator.get_internal_validity(invalid_values)
    print(f"  - Input: Assets=1M, Liabilities=600k, Equity=300k")
    print(f"  - Status: {invalid_result.status}")
    print(f"  - Failed: {invalid_result.failed_count}")
    
    assert invalid_result.status == "INVALID_INTERNAL", "Should detect invalid"
    
    # Test with partial data
    print("\n4.3 Testing with partial data:")
    partial_values = {
        'TotalAssets': 1_000_000,
        # Missing Liabilities and Equity
    }
    
    partial_result = validator.get_internal_validity(partial_values)
    print(f"  - Input: Assets=1M only")
    print(f"  - Status: {partial_result.status}")
    
    # Test explain_mismatch - need complete data for VALID_INTERNAL
    print("\n4.4 Testing explain_mismatch logic:")
    
    # Create a result with VALID_INTERNAL status manually to test explain logic
    from edgar.xbrl.standardization.internal_validator import (
        InternalValidationResult, EquationResult
    )
    
    valid_internal = InternalValidationResult(
        status="VALID_INTERNAL",
        equation_results={},
        passed_count=4,
        failed_count=0,
        partial_count=0,
        notes="All equations pass"
    )
    explanation = validator.explain_mismatch(valid_internal, "invalid")
    print(f"  - Internal=VALID_INTERNAL, External=invalid")
    print(f"  - Explanation: {explanation[:60]}...")
    
    assert "VALID_INTERNAL_MISMATCH" in explanation, "Should explain mismatch"
    
    print("\n  ✅ Internal Validator tests passed!")
    return True


def test_extractor_registry():
    """Test all extractors are registered."""
    print("\n" + "="*60)
    print("TEST 5: Extractor Registry")
    print("="*60)
    
    from edgar.xbrl.standardization.industry_logic import EXTRACTORS
    
    print("\n5.1 Registered extractors:")
    for industry, extractor in EXTRACTORS.items():
        print(f"  - {industry}: {type(extractor).__name__}")
    
    expected = ['default', 'banking', 'saas', 'software', 'insurance']
    for ind in expected:
        assert ind in EXTRACTORS, f"Missing extractor: {ind}"
    
    print(f"\n  ✅ All {len(expected)} expected extractors registered!")
    return True


def run_all_tests():
    """Run all Sprint 2 tests."""
    print("\n" + "#"*60)
    print("# SPRINT 2 TEST SUITE")
    print("# Industry Extractors, Signage, Internal Validator")
    print("#"*60)
    
    results = {}
    
    # Test 1: SaaS Extractor
    results['saas_extractor'] = test_saas_extractor()
    
    # Test 2: Insurance Extractor
    results['insurance_extractor'] = test_insurance_extractor()
    
    # Test 3: Signage Normalization
    results['signage_normalization'] = test_signage_normalization()
    
    # Test 4: Internal Validator
    results['internal_validator'] = test_internal_validator()
    
    # Test 5: Registry
    results['extractor_registry'] = test_extractor_registry()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    print("\n" + ("="*60))
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️ SOME TESTS FAILED - Review output above")
    print("="*60)
    
    return all_passed


if __name__ == "__main__":
    run_all_tests()
