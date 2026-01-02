#!/usr/bin/env python3
"""
Integration Tests for apply_mappings.py

Tests the production mapping extraction with real company data.

Usage:
    python test_apply_mappings.py
    python test_apply_mappings.py --sector banking
    python test_apply_mappings.py --verbose
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

from apply_mappings import (
    extract_income_statement,
    detect_sector,
    validate_extraction,
    extract_with_auto_sector,
    normalize_concept_name
)


# Test data - synthetic XBRL facts for different scenarios
TEST_FACTS_TECH = {
    'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax': 100000000,
    'us-gaap_CostOfRevenue': 40000000,
    'us-gaap_GrossProfit': 60000000,
    'us-gaap_OperatingExpenses': 35000000,
    'us-gaap_OperatingIncomeLoss': 25000000,
    'us-gaap_NetIncomeLoss': 20000000,
    'us-gaap_EarningsPerShareBasic': 2.50,
    'us-gaap_EarningsPerShareDiluted': 2.45,
    'us-gaap_WeightedAverageNumberOfSharesOutstandingBasic': 8000000,
    'us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding': 8163265
}

TEST_FACTS_BANKING = {
    'us-gaap_InterestIncomeExpenseNet': 50000000,
    'us-gaap_NoninterestIncome': 20000000,
    'us-gaap_Revenues': 70000000,
    'us-gaap_NoninterestExpense': 35000000,
    'us-gaap_ProvisionForLoanLossesExpensed': 5000000,
    'us-gaap_IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest': 30000000,
    'us-gaap_IncomeTaxExpenseBenefit': 6000000,
    'us-gaap_NetIncomeLoss': 24000000,
    'us-gaap_EarningsPerShareBasic': 3.00,
    'us-gaap_EarningsPerShareDiluted': 2.95
}

TEST_FACTS_INSURANCE = {
    'us-gaap_Revenues': 80000000,
    'us-gaap_PremiumsEarnedNet': 60000000,
    'us-gaap_InvestmentIncomeNet': 20000000,
    'us-gaap_PolicyholderBenefitsAndClaimsIncurredNet': 40000000,
    'us-gaap_OperatingExpenses': 25000000,
    'us-gaap_IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest': 15000000,
    'us-gaap_IncomeTaxExpenseBenefit': 3000000,
    'us-gaap_NetIncomeLoss': 12000000
}

TEST_FACTS_UTILITIES = {
    'us-gaap_Revenues': 90000000,
    'us-gaap_RegulatedOperatingRevenue': 85000000,
    'us-gaap_CostOfRevenue': 50000000,
    'us-gaap_GrossProfit': 40000000,
    'us-gaap_OperatingExpenses': 20000000,
    'us-gaap_OperatingIncomeLoss': 20000000,
    'us-gaap_InterestExpense': 5000000,
    'us-gaap_IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest': 15000000,
    'us-gaap_IncomeTaxExpenseBenefit': 3000000,
    'us-gaap_NetIncomeLoss': 12000000
}


def test_normalize_concept_name():
    """Test concept name normalization."""
    print("\n" + "="*70)
    print("TEST: Concept Name Normalization")
    print("="*70)

    test_cases = [
        ('us-gaap:Revenues', 'us-gaap_Revenues'),
        ('us-gaap_Revenues', 'us-gaap_Revenues'),
        ('Revenues', 'Revenues'),
        ('us-gaap:NetIncomeLoss', 'us-gaap_NetIncomeLoss')
    ]

    passed = 0
    failed = 0

    for input_val, expected in test_cases:
        result = normalize_concept_name(input_val)
        if result == expected:
            print(f"  ✓ {input_val} → {result}")
            passed += 1
        else:
            print(f"  ✗ {input_val} → {result} (expected {expected})")
            failed += 1

    print(f"\nResult: {passed} passed, {failed} failed")
    return failed == 0


def test_basic_extraction():
    """Test basic extraction with tech company facts."""
    print("\n" + "="*70)
    print("TEST: Basic Extraction (Tech Company)")
    print("="*70)

    result = extract_income_statement(TEST_FACTS_TECH)

    print(f"\nExtracted {result['fields_extracted']}/{result['fields_total']} fields")
    print(f"Sector: {result['sector']}")

    # Verify expected fields
    expected_fields = ['revenue', 'costOfRevenue', 'grossProfit', 'operatingExpenses',
                      'operatingIncome', 'netIncome', 'earningsPerShareBasic']

    missing = []
    for field in expected_fields:
        if field in result['data']:
            value = result['data'][field]
            concept = result['metadata'][field]['concept']
            print(f"  ✓ {field}: {value:,} (from {concept})")
        else:
            print(f"  ✗ {field}: MISSING")
            missing.append(field)

    success = len(missing) == 0
    print(f"\nResult: {'PASS' if success else 'FAIL'}")
    if missing:
        print(f"Missing fields: {', '.join(missing)}")

    return success


def test_sector_specific_extraction():
    """Test sector-specific extraction."""
    print("\n" + "="*70)
    print("TEST: Sector-Specific Extraction")
    print("="*70)

    test_cases = [
        ('banking', TEST_FACTS_BANKING, ['revenue', 'netIncome']),
        ('insurance', TEST_FACTS_INSURANCE, ['revenue', 'netIncome']),
        ('utilities', TEST_FACTS_UTILITIES, ['revenue', 'netIncome'])
    ]

    all_passed = True

    for sector, facts, expected_fields in test_cases:
        print(f"\n  Testing {sector.upper()}...")
        result = extract_income_statement(facts, sector=sector)

        print(f"    Extracted: {result['fields_extracted']} fields")
        print(f"    Sector: {result['sector']}")

        missing = []
        for field in expected_fields:
            if field in result['data']:
                value = result['data'][field]
                print(f"    ✓ {field}: {value:,}")
            else:
                print(f"    ✗ {field}: MISSING")
                missing.append(field)
                all_passed = False

        if missing:
            print(f"    Missing: {', '.join(missing)}")

    print(f"\nResult: {'PASS' if all_passed else 'FAIL'}")
    return all_passed


def test_sector_detection():
    """Test automatic sector detection."""
    print("\n" + "="*70)
    print("TEST: Sector Auto-Detection")
    print("="*70)

    test_cases = [
        (TEST_FACTS_BANKING, 6021, 'banking'),  # Commercial bank SIC
        (TEST_FACTS_INSURANCE, 6331, 'insurance'),  # Fire insurance SIC
        (TEST_FACTS_UTILITIES, 4911, 'utilities'),  # Electric services SIC
        (TEST_FACTS_TECH, None, None)  # Tech has no special sector
    ]

    all_passed = True

    for facts, sic, expected_sector in test_cases:
        detected = detect_sector(facts, sic)

        if expected_sector is None:
            if detected is None:
                print(f"  ✓ SIC {sic}: No sector (expected)")
            else:
                print(f"  ✗ SIC {sic}: Detected {detected} (expected None)")
                all_passed = False
        else:
            if detected == expected_sector:
                print(f"  ✓ SIC {sic}: Detected {detected}")
            else:
                print(f"  ✗ SIC {sic}: Detected {detected} (expected {expected_sector})")
                all_passed = False

    print(f"\nResult: {'PASS' if all_passed else 'FAIL'}")
    return all_passed


def test_validation():
    """Test extraction validation."""
    print("\n" + "="*70)
    print("TEST: Extraction Validation")
    print("="*70)

    # Test valid extraction
    result = extract_income_statement(TEST_FACTS_TECH)
    validation = validate_extraction(result, required_fields=['revenue', 'netIncome'])

    print(f"\nValidation for tech company:")
    print(f"  Valid: {validation['valid']}")
    print(f"  Has all required: {validation['has_all_required']}")
    print(f"  Extraction rate: {validation['extraction_rate']:.1%}")
    print(f"  Low confidence fields: {len(validation['low_confidence_fields'])}")

    if validation['missing_required']:
        print(f"  Missing required: {', '.join(validation['missing_required'])}")

    # Test incomplete extraction
    incomplete_facts = {'us-gaap_NetIncomeLoss': 10000}
    result2 = extract_income_statement(incomplete_facts)
    validation2 = validate_extraction(result2, required_fields=['revenue', 'netIncome'])

    print(f"\nValidation for incomplete data:")
    print(f"  Valid: {validation2['valid']}")
    print(f"  Missing required: {', '.join(validation2['missing_required'])}")

    success = validation['valid'] and not validation2['valid']
    print(f"\nResult: {'PASS' if success else 'FAIL'}")
    return success


def test_fallback_chains():
    """Test fallback concept chains."""
    print("\n" + "="*70)
    print("TEST: Fallback Chains")
    print("="*70)

    # Load core mapping to check fallback chains
    mapping_path = Path(__file__).parent / 'map' / 'map_core.json'
    with open(mapping_path, 'r') as f:
        core_map = json.load(f)

    print(f"\nFields with fallbacks:")
    fallback_count = 0

    for field_name, field_data in core_map['fields'].items():
        fallbacks = field_data.get('fallbacks', [])
        if fallbacks:
            fallback_count += 1
            print(f"  {field_name}:")
            print(f"    Primary: {field_data['primary']}")
            print(f"    Fallbacks: {', '.join(fallbacks)}")

    print(f"\nTotal fields with fallbacks: {fallback_count}")

    # Test fallback usage - create facts with only fallback concepts
    facts_with_fallback = {
        'us-gaap_Revenues': 100000000,  # Fallback for revenue
        'us-gaap_ProfitLoss': 20000000  # Fallback for netIncome
    }

    result = extract_income_statement(facts_with_fallback)

    print(f"\nExtraction using fallbacks:")
    for field, value in result['data'].items():
        concept = result['metadata'][field]['concept']
        is_fallback = concept != core_map['fields'][field]['primary']
        marker = "FALLBACK" if is_fallback else "primary"
        print(f"  {field}: {value:,} ({marker})")

    success = fallback_count > 0 and result['fields_extracted'] > 0
    print(f"\nResult: {'PASS' if success else 'FAIL'}")
    return success


def test_coverage_analysis():
    """Test mapping coverage across all test scenarios."""
    print("\n" + "="*70)
    print("TEST: Coverage Analysis")
    print("="*70)

    all_test_facts = [
        ('Tech', TEST_FACTS_TECH, None),
        ('Banking', TEST_FACTS_BANKING, 'banking'),
        ('Insurance', TEST_FACTS_INSURANCE, 'insurance'),
        ('Utilities', TEST_FACTS_UTILITIES, 'utilities')
    ]

    coverage_stats = []

    for name, facts, sector in all_test_facts:
        result = extract_income_statement(facts, sector=sector)
        validation = validate_extraction(result)

        coverage_stats.append({
            'name': name,
            'sector': sector or 'core',
            'extracted': result['fields_extracted'],
            'total': result['fields_total'],
            'rate': validation['extraction_rate'],
            'valid': validation['valid']
        })

    print(f"\n{'Scenario':<12} {'Sector':<12} {'Extracted':<12} {'Rate':<12} {'Valid':<12}")
    print("-" * 70)

    for stat in coverage_stats:
        print(f"{stat['name']:<12} {stat['sector']:<12} "
              f"{stat['extracted']}/{stat['total']:<10} "
              f"{stat['rate']:<11.1%} "
              f"{'✓' if stat['valid'] else '✗':<12}")

    # Average coverage
    avg_rate = sum(s['rate'] for s in coverage_stats) / len(coverage_stats)
    all_valid = all(s['valid'] for s in coverage_stats)

    print(f"\nAverage extraction rate: {avg_rate:.1%}")
    print(f"All validations passed: {all_valid}")

    success = avg_rate >= 0.30 and all_valid
    print(f"\nResult: {'PASS' if success else 'FAIL'}")
    return success


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("INTEGRATION TESTS FOR apply_mappings.py")
    print("="*70)

    tests = [
        ("Concept Normalization", test_normalize_concept_name),
        ("Basic Extraction", test_basic_extraction),
        ("Sector-Specific Extraction", test_sector_specific_extraction),
        ("Sector Detection", test_sector_detection),
        ("Validation", test_validation),
        ("Fallback Chains", test_fallback_chains),
        ("Coverage Analysis", test_coverage_analysis)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed, None))
        except Exception as e:
            print(f"\n✗ {test_name} FAILED with exception: {e}")
            results.append((test_name, False, str(e)))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed_count = sum(1 for _, passed, _ in results if passed)
    failed_count = len(results) - passed_count

    for test_name, passed, error in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {test_name}")
        if error:
            print(f"        Error: {error}")

    print(f"\n{'='*70}")
    print(f"TOTAL: {passed_count}/{len(results)} tests passed")
    print(f"{'='*70}")

    if passed_count == len(results):
        print("\n✅ All tests passed! Mappings are production-ready.")
        return 0
    else:
        print(f"\n❌ {failed_count} test(s) failed. Review issues before deployment.")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(run_all_tests())
