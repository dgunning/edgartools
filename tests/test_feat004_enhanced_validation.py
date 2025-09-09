#!/usr/bin/env python3
"""
Test implementation for FEAT-004: Enhanced Parameter Validation

This script tests the enhanced validation framework to ensure:
1. Smart typo detection and suggestions work correctly
2. Helpful error messages are generated
3. Context-aware validation provides appropriate guidance
4. Performance is acceptable for common use cases
5. Backwards compatibility is maintained
"""

import sys
from pathlib import Path

# Add edgar to path for testing
sys.path.insert(0, str(Path(__file__).parent / "edgar"))

from edgar.types import (
    ValidationError,
    enhanced_validate,
    fuzzy_match,
    detect_common_typos,
    validate_form_type,
    validate_period_type,
    FormType,
    PeriodType
)

def test_fuzzy_matching():
    """Test fuzzy string matching functionality."""
    print("🔍 Testing fuzzy matching...")
    
    valid_options = {"annual", "quarterly", "monthly", "ttm", "ytd"}
    
    # Test close matches
    matches = fuzzy_match("anual", valid_options, 0.6)
    assert "annual" in matches
    print(f"   ✅ 'anual' -> {matches}")
    
    matches = fuzzy_match("quartly", valid_options, 0.6) 
    assert "quarterly" in matches
    print(f"   ✅ 'quartly' -> {matches}")
    
    # Test no matches for very different strings
    matches = fuzzy_match("xyz", valid_options, 0.6)
    assert len(matches) == 0
    print(f"   ✅ 'xyz' -> {matches} (no matches)")
    
    print("   ✅ Fuzzy matching works correctly")

def test_typo_detection():
    """Test common typo detection patterns."""
    print("🔍 Testing typo detection...")
    
    valid_options = {"10-K", "10-Q", "8-K", "DEF 14A"}
    
    # Test missing character
    suggestions = detect_common_typos("10-", valid_options)
    assert "10-K" in suggestions or "10-Q" in suggestions
    print(f"   ✅ Missing char '10-' -> {suggestions}")
    
    # Test extra character  
    suggestions = detect_common_typos("10--K", valid_options)
    assert "10-K" in suggestions
    print(f"   ✅ Extra char '10--K' -> {suggestions}")
    
    # Test case mismatch
    suggestions = detect_common_typos("10-k", valid_options)
    assert "10-K" in suggestions  
    print(f"   ✅ Case mismatch '10-k' -> {suggestions}")
    
    print("   ✅ Typo detection works correctly")

def test_enhanced_validation():
    """Test the enhanced validation framework."""
    print("🔍 Testing enhanced validation framework...")
    
    valid_forms = {"10-K", "10-Q", "8-K", "DEF 14A"}
    
    # Test valid input
    result = enhanced_validate("10-K", valid_forms, "form")
    assert result == "10-K"
    print("   ✅ Valid input passes through")
    
    # Test case insensitive match
    result = enhanced_validate("10-k", valid_forms, "form")
    assert result == "10-K"
    print("   ✅ Case insensitive matching works")
    
    # Test typo with suggestion
    try:
        enhanced_validate("10-X", valid_forms, "form", enum_type=FormType)
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "10-K" in str(e) or "10-Q" in str(e)
        assert "FormType" in str(e)
        print(f"   ✅ Typo detection: {e}")
    
    # Test None input
    try:
        enhanced_validate(None, valid_forms, "form")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "cannot be None" in str(e)
        print(f"   ✅ None handling: {e}")
        
    # Test wrong type
    try:
        enhanced_validate(123, valid_forms, "form", enum_type=FormType)
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert "must be FormType or str" in str(e)
        print(f"   ✅ Type validation: {e}")

def test_form_type_validation():
    """Test enhanced FormType validation."""
    print("🔍 Testing FormType validation enhancements...")
    
    # Test enum input
    result = validate_form_type(FormType.ANNUAL_REPORT)
    assert result == "10-K"
    print("   ✅ Enum input works")
    
    # Test valid string
    result = validate_form_type("10-Q")
    assert result == "10-Q"
    print("   ✅ Valid string works")
    
    # Test typo with context
    try:
        validate_form_type("10-X")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        error_msg = str(e)
        assert "Did you mean" in error_msg
        assert "FormType" in error_msg
        assert "Common forms" in error_msg  # Context hint
        print(f"   ✅ Enhanced error: {e}")
    
    # Test completely invalid
    try:
        validate_form_type("invalid-form")
        assert False, "Should have raised ValidationError"  
    except ValidationError as e:
        error_msg = str(e)
        assert "Valid form types" in error_msg
        assert "'10-K'" in error_msg
        print(f"   ✅ Invalid form error: {e}")

def test_period_type_validation():
    """Test enhanced PeriodType validation."""
    print("🔍 Testing PeriodType validation enhancements...")
    
    # Test enum input
    result = validate_period_type(PeriodType.ANNUAL)
    assert result == "annual"
    print("   ✅ Enum input works")
    
    # Test alias handling
    result = validate_period_type("annual")  
    assert result == "annual"
    print("   ✅ Direct string works")
    
    # Test typo with context
    try:
        validate_period_type("anual")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        error_msg = str(e)
        assert "Did you mean" in error_msg
        assert "annual" in error_msg
        assert "PeriodType" in error_msg
        assert "Common periods" in error_msg  # Context hint
        print(f"   ✅ Enhanced error: {e}")
    
    # Test multiple suggestions
    try:
        validate_period_type("quarter")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        # Should suggest "quarterly" 
        assert "quarterly" in str(e)
        print(f"   ✅ Multiple suggestions: {e}")

def test_error_message_quality():
    """Test that error messages are helpful and professional."""
    print("🔍 Testing error message quality...")
    
    test_cases = [
        # (input, expected_in_message)
        ("10-X", ["Did you mean", "10-K"]),  # Should suggest similar forms
        ("10k", ["Did you mean", "10-K"]),   # Missing hyphen
        ("invalid", ["Valid", "10-K", "10-Q"]),
        (123, ["must be", "FormType or str", "not int"])
    ]
    
    for test_input, expected_parts in test_cases[:3]:  # Skip type error test
        try:
            validate_form_type(test_input)
            assert False, f"Should have raised error for {test_input}"
        except (ValidationError, TypeError) as e:
            error_msg = str(e)
            for part in expected_parts:
                assert part in error_msg, f"Expected '{part}' in error message: {error_msg}"
            print(f"   ✅ '{test_input}' -> Professional error message")
    
    # Test type error separately
    try:
        validate_form_type(123)
        assert False, "Should have raised TypeError"
    except TypeError as e:
        error_msg = str(e) 
        for part in ["must be", "FormType or str", "not int"]:
            assert part in error_msg
        print(f"   ✅ Type error -> Professional error message")

def test_performance():
    """Test that validation performance is acceptable."""
    print("🔍 Testing validation performance...")
    
    import time
    
    # Test form validation performance
    start_time = time.time()
    for _ in range(1000):
        try:
            validate_form_type("10-X")  # Invalid, will generate suggestions
        except ValidationError:
            pass
    form_time = time.time() - start_time
    
    # Test period validation performance  
    start_time = time.time()
    for _ in range(1000):
        try:
            validate_period_type("anual")  # Invalid, will generate suggestions
        except ValidationError:
            pass
    period_time = time.time() - start_time
    
    print(f"   ✅ 1000 form validations: {form_time:.3f}s ({form_time/1000*1000:.2f}ms each)")
    print(f"   ✅ 1000 period validations: {period_time:.3f}s ({period_time/1000*1000:.2f}ms each)")
    
    # Performance should be reasonable (< 10ms per validation)
    assert form_time < 10.0, "Form validation too slow"
    assert period_time < 10.0, "Period validation too slow"
    print("   ✅ Performance is acceptable")

def test_backwards_compatibility():
    """Test that existing validation behavior is preserved."""
    print("🔍 Testing backwards compatibility...")
    
    # Valid inputs should work exactly the same
    assert validate_form_type("10-K") == "10-K"
    assert validate_form_type(FormType.ANNUAL_REPORT) == "10-K"
    assert validate_period_type("annual") == "annual"
    assert validate_period_type(PeriodType.QUARTERLY) == "quarterly"
    print("   ✅ Valid inputs unchanged")
    
    # Invalid inputs should still raise errors (but better ones)
    validation_cases = [
        (validate_form_type, "invalid"),
        (validate_period_type, "invalid")
    ]
    
    for validator, invalid_input in validation_cases:
        try:
            validator(invalid_input)
            assert False, f"Should have raised error for {invalid_input}"
        except (ValueError, ValidationError):
            # Error raised as expected (ValidationError is subclass of ValueError)
            pass
    
    print("   ✅ Invalid inputs still raise errors")
    print("   ✅ Backwards compatibility maintained")

def test_real_world_scenarios():
    """Test realistic usage scenarios."""
    print("🔍 Testing real-world scenarios...")
    
    # Scenario 1: Common typos users make
    common_typos = {
        # Form type typos
        "10k": "10-K",
        "10-k": "10-K", 
        "10q": "10-Q",
        "8k": "8-K",
        "def14a": "DEF 14A",
        # Period type typos
        "anual": "annual",
        "quartly": "quarterly",
        "montly": "monthly"
    }
    
    for typo, expected in common_typos.items():
        try:
            if "10" in typo or "8" in typo or "def" in typo.lower():
                validate_form_type(typo)
            else:
                validate_period_type(typo)
            # If it doesn't raise, the case-insensitive matching worked
        except ValidationError as e:
            # Should suggest the correct value
            assert expected in str(e), f"Expected '{expected}' suggested for '{typo}'"
        print(f"   ✅ '{typo}' -> suggests '{expected}'")
    
    # Scenario 2: Completely invalid inputs
    invalid_inputs = ["xyz123", "random", ""]
    for invalid in invalid_inputs:
        try:
            validate_form_type(invalid)
            assert False, f"Should reject {invalid}"
        except ValidationError as e:
            # Should show valid options instead of suggestions
            assert "Valid form types" in str(e) or "Did you mean" in str(e)
        print(f"   ✅ '{invalid}' -> shows valid options")
    
    print("   ✅ Real-world scenarios handled well")

def main():
    """Run all tests."""
    print("🚀 Testing FEAT-004: Enhanced Parameter Validation\n")
    
    try:
        test_fuzzy_matching()
        test_typo_detection()
        test_enhanced_validation()
        test_form_type_validation()
        test_period_type_validation()
        test_error_message_quality()
        test_performance()
        test_backwards_compatibility()
        test_real_world_scenarios()
        
        print("\n🎉 All tests passed! FEAT-004 Enhanced Parameter Validation is working correctly.")
        print("\n📋 Summary:")
        print("   ✅ Smart typo detection with helpful suggestions")
        print("   ✅ Context-aware error messages")
        print("   ✅ Professional, user-friendly error text")
        print("   ✅ Acceptable performance for real-world usage")
        print("   ✅ Backwards compatibility maintained")
        print("   ✅ Enhanced developer experience")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())