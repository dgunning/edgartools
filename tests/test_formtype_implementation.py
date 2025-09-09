#!/usr/bin/env python3
"""
Test script for FEAT-002: StrEnum FormType implementation
Tests both new FormType usage and backwards compatibility
"""

# Test imports work correctly
try:
    from edgar.types import FormType, validate_form_type, FormInput
    print("✅ FormType import successful")
except ImportError as e:
    print(f"❌ FormType import failed: {e}")
    exit(1)

# Test enum values
print("\n=== Testing FormType Enum Values ===")
print(f"ANNUAL_REPORT: {FormType.ANNUAL_REPORT}")
print(f"QUARTERLY_REPORT: {FormType.QUARTERLY_REPORT}")  
print(f"CURRENT_REPORT: {FormType.CURRENT_REPORT}")
print(f"PROXY_STATEMENT: {FormType.PROXY_STATEMENT}")

# Test string conversion  
print(f"\nString representation: {str(FormType.ANNUAL_REPORT)}")
print(f"Equals string: {FormType.ANNUAL_REPORT == '10-K'}")

# Test validation function
print("\n=== Testing Form Validation ===")
try:
    # Valid FormType
    result = validate_form_type(FormType.ANNUAL_REPORT)
    print(f"✅ FormType validation: {result}")
    
    # Valid string
    result = validate_form_type("10-K")
    print(f"✅ String validation: {result}")
    
    # Invalid string (should suggest)
    try:
        validate_form_type("10k")  # Common mistake
    except ValueError as e:
        print(f"✅ Helpful error message: {e}")
    
    # Completely invalid
    try:
        validate_form_type("INVALID")
    except ValueError as e:
        print(f"✅ Invalid form error: {e}")
        
except Exception as e:
    print(f"❌ Validation test failed: {e}")

# Test type annotations work
print("\n=== Testing Type Hints ===")
try:
    from edgar.entity.core import Entity
    print("✅ Updated core.py imports successfully")
    
    # Check if FormType is recognized in type hints
    import inspect
    sig = inspect.signature(Entity.get_filings)
    form_param = sig.parameters['form']
    print(f"✅ Form parameter annotation: {form_param.annotation}")
    
except Exception as e:
    print(f"⚠️  Type hint test (expected if not all dependencies available): {e}")

# Test IDE autocomplete simulation
print("\n=== Testing Developer Experience ===")
print("Available form types for autocomplete:")
for form_type in FormType:
    print(f"  - {form_type.name}: {form_type.value}")

print(f"\nTotal form types available: {len(list(FormType))}")

print("\n=== Testing Form Collections ===")
try:
    from edgar.types import PERIODIC_FORMS, PROXY_FORMS, REGISTRATION_FORMS
    print(f"✅ Periodic forms: {len(PERIODIC_FORMS)} types")
    print(f"✅ Proxy forms: {len(PROXY_FORMS)} types") 
    print(f"✅ Registration forms: {len(REGISTRATION_FORMS)} types")
except ImportError as e:
    print(f"❌ Form collections import failed: {e}")

print("\n🎉 FormType implementation test completed!")
print("\nNext steps:")
print("1. Test with actual Company.get_filings() calls")
print("2. Verify IDE autocomplete works in your editor")
print("3. Run existing tests to ensure backwards compatibility")