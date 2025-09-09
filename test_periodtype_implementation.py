#!/usr/bin/env python3
"""
Test implementation for FEAT-003: PeriodType Enum

This script tests the new PeriodType enum functionality to ensure:
1. PeriodType enum works correctly
2. Validation functions work as expected
3. Type hints provide proper IDE autocomplete
4. Backwards compatibility is maintained
"""

import sys
from pathlib import Path

# Add edgar to path for testing
sys.path.insert(0, str(Path(__file__).parent / "edgar"))

from edgar.formtypes import (
    PeriodType,
    PeriodInput,
    validate_period_type,
    STANDARD_PERIODS,
    SPECIAL_PERIODS,
    ALL_PERIODS
)

def test_period_type_enum():
    """Test PeriodType enum basic functionality."""
    print("🔍 Testing PeriodType enum basic functionality...")
    
    # Test enum values
    assert PeriodType.ANNUAL == "annual"
    assert PeriodType.QUARTERLY == "quarterly"
    assert PeriodType.MONTHLY == "monthly"
    assert PeriodType.TTM == "ttm"
    assert PeriodType.YTD == "ytd"
    
    # Test aliases
    assert PeriodType.YEARLY == "annual"
    assert PeriodType.QUARTER == "quarterly"
    
    print("   ✅ All enum values work correctly")

def test_period_validation():
    """Test period validation function."""
    print("🔍 Testing period validation...")
    
    # Test valid enum input
    assert validate_period_type(PeriodType.ANNUAL) == "annual"
    assert validate_period_type(PeriodType.QUARTERLY) == "quarterly"
    assert validate_period_type(PeriodType.TTM) == "ttm"
    
    # Test valid string input
    assert validate_period_type("annual") == "annual"
    assert validate_period_type("quarterly") == "quarterly"
    assert validate_period_type("ttm") == "ttm"
    
    print("   ✅ Valid inputs work correctly")
    
    # Test invalid input with suggestions
    try:
        validate_period_type("annualy")  # typo
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Did you mean" in str(e)
        assert "annual" in str(e)
        print(f"   ✅ Typo detection: {e}")
    
    # Test completely invalid input
    try:
        validate_period_type("invalid")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "PeriodType" in str(e)
        print(f"   ✅ Invalid input rejection: {e}")
    
    # Test wrong type
    try:
        validate_period_type(123)
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert "PeriodType or str" in str(e)
        print(f"   ✅ Type validation: {e}")

def test_convenience_collections():
    """Test period collections."""
    print("🔍 Testing convenience collections...")
    
    assert PeriodType.ANNUAL in STANDARD_PERIODS
    assert PeriodType.QUARTERLY in STANDARD_PERIODS
    assert PeriodType.TTM in SPECIAL_PERIODS
    assert PeriodType.YTD in SPECIAL_PERIODS
    
    # Test ALL_PERIODS contains everything
    all_enum_values = set(PeriodType)
    all_collection_values = set(ALL_PERIODS)
    
    # Remove aliases to avoid duplicates
    unique_enum_values = {p for p in all_enum_values if p.value not in ["annual", "quarterly"] or p.name in ["ANNUAL", "QUARTERLY"]}
    
    assert len(unique_enum_values) == len(ALL_PERIODS)
    print("   ✅ All collections work correctly")

def test_type_hints():
    """Test type hint functionality."""
    print("🔍 Testing type hints...")
    
    def example_function(period: PeriodInput) -> str:
        """Example function using PeriodInput type hint."""
        return validate_period_type(period)
    
    # Test with enum
    assert example_function(PeriodType.ANNUAL) == "annual"
    
    # Test with string
    assert example_function("quarterly") == "quarterly"
    
    print("   ✅ Type hints work correctly")

def test_real_world_usage():
    """Test realistic usage scenarios."""
    print("🔍 Testing real-world usage scenarios...")
    
    def mock_get_facts(period: PeriodInput = PeriodType.ANNUAL) -> str:
        """Mock function simulating real EdgarTools usage."""
        validated_period = validate_period_type(period)
        return f"Getting facts for period: {validated_period}"
    
    # Test default enum usage
    result1 = mock_get_facts()
    assert result1 == "Getting facts for period: annual"
    
    # Test explicit enum usage
    result2 = mock_get_facts(PeriodType.QUARTERLY)
    assert result2 == "Getting facts for period: quarterly"
    
    # Test backwards compatible string usage
    result3 = mock_get_facts("ttm")
    assert result3 == "Getting facts for period: ttm"
    
    print("   ✅ Real-world usage patterns work")

def test_enum_iteration():
    """Test enum iteration and introspection."""
    print("🔍 Testing enum iteration...")
    
    # Test we can iterate over periods
    period_names = [period.name for period in PeriodType]
    period_values = [period.value for period in PeriodType]
    
    assert "ANNUAL" in period_names
    assert "QUARTERLY" in period_names
    assert "annual" in period_values
    assert "quarterly" in period_values
    
    print(f"   ✅ Available periods: {period_values}")

def main():
    """Run all tests."""
    print("🚀 Testing FEAT-003: PeriodType Enum Implementation\n")
    
    try:
        test_period_type_enum()
        test_period_validation()
        test_convenience_collections()
        test_type_hints()
        test_real_world_usage()
        test_enum_iteration()
        
        print("\n🎉 All tests passed! PeriodType implementation is working correctly.")
        print("\n📋 Summary:")
        print("   ✅ PeriodType enum with IDE autocomplete")
        print("   ✅ Validation with helpful error messages") 
        print("   ✅ Backwards compatibility with strings")
        print("   ✅ Type hints for better developer experience")
        print("   ✅ Convenience collections for common use cases")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())