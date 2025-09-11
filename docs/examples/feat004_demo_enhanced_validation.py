#!/usr/bin/env python3
"""
FEAT-004 Demo: Enhanced Parameter Validation

This demonstrates how the enhanced parameter validation framework transforms
EdgarTools error handling from generic messages to intelligent, helpful guidance.
"""

import sys
from pathlib import Path

# Add edgar to path
sys.path.insert(0, str(Path(__file__).parent / "edgar"))

from edgar.enums import (
    ValidationError,
    enhanced_validate,
    validate_form_type,
    validate_period_type,
    FormType,
    PeriodType
)

def demo_before_and_after():
    """Show the improvement from old validation to enhanced validation."""
    print("🔄 Before vs After: Validation Improvements")
    print("=" * 60)
    
    print("BEFORE (Generic errors):")
    print("  Input: '10-X' -> ValueError: Invalid form type")
    print("  Input: 'anual' -> ValueError: Invalid period")
    print("  Input: 123 -> TypeError: Expected str")
    print()
    
    print("AFTER (Enhanced errors with guidance):")
    
    test_cases = [
        (validate_form_type, "10-X", "form type"),
        (validate_period_type, "anual", "period type"),
        (validate_form_type, 123, "wrong type")
    ]
    
    for validator, test_input, description in test_cases:
        try:
            validator(test_input)
        except (ValidationError, TypeError) as e:
            print(f"  Input: '{test_input}' ({description}):")
            print(f"    -> {e}")
        print()

def demo_smart_typo_detection():
    """Demonstrate intelligent typo detection and suggestions."""
    print("🔍 Smart Typo Detection & Suggestions")
    print("=" * 60)
    
    print("Common typos that are automatically detected:")
    
    typo_cases = [
        # Form type typos
        (validate_form_type, [
            ("10k", "Missing hyphen"),
            ("10-k", "Wrong case"),
            ("10-X", "Wrong letter"),
            ("def14a", "Missing spaces"),
            ("8K", "Wrong case")
        ]),
        # Period type typos  
        (validate_period_type, [
            ("anual", "Missing letter"),
            ("quartly", "Wrong spelling"),
            ("montly", "Missing letter"),
            ("Annual", "Wrong case")
        ])
    ]
    
    for validator, cases in typo_cases:
        validator_name = validator.__name__.replace('validate_', '').replace('_', ' ').title()
        print(f"\n{validator_name} Typos:")
        
        for typo, description in cases:
            try:
                validator(typo)
            except ValidationError as e:
                print(f"  '{typo}' ({description}) -> {str(e).split('.')[0]}.")

def demo_contextual_help():
    """Show how context hints provide additional guidance."""
    print("\n🎯 Context-Aware Help Messages")
    print("=" * 60)
    
    print("Enhanced validation provides context for better understanding:")
    
    try:
        validate_form_type("unknown")
    except ValidationError as e:
        print(f"\nForm Type Context:")
        print(f"  {e}")
        
    try:
        validate_period_type("unknown")
    except ValidationError as e:
        print(f"\nPeriod Type Context:")
        print(f"  {e}")

def demo_different_error_scenarios():
    """Show different types of validation errors."""
    print("\n📚 Different Error Scenarios")
    print("=" * 60)
    
    scenarios = [
        ("Close match with suggestion", validate_form_type, "10-X"),
        ("Multiple suggestions", validate_form_type, "10-"),  
        ("No close matches", validate_form_type, "xyz123"),
        ("Wrong type entirely", validate_form_type, 42),
        ("None value", validate_form_type, None),
        ("Empty string", validate_form_type, "")
    ]
    
    for scenario_name, validator, test_input in scenarios:
        print(f"\n{scenario_name}:")
        try:
            validator(test_input)
        except (ValidationError, TypeError) as e:
            print(f"  Input: {repr(test_input)}")
            print(f"  Error: {e}")

def demo_enum_vs_string_consistency():
    """Show that enum and string validation is consistent."""
    print("\n⚖️ Enum vs String Consistency")
    print("=" * 60)
    
    print("Both enum and string inputs work consistently:")
    
    # Valid cases
    form_enum_result = validate_form_type(FormType.ANNUAL_REPORT)
    form_string_result = validate_form_type("10-K")
    period_enum_result = validate_period_type(PeriodType.ANNUAL)
    period_string_result = validate_period_type("annual")
    
    print(f"  FormType.ANNUAL_REPORT -> '{form_enum_result}'")
    print(f"  '10-K' -> '{form_string_result}'")
    print(f"  PeriodType.ANNUAL -> '{period_enum_result}'")
    print(f"  'annual' -> '{period_string_result}'")
    
    print("\nError handling is also consistent:")
    
    # Error cases
    for invalid_input in ["invalid", 123]:
        for validator_name, validator in [("Form", validate_form_type), ("Period", validate_period_type)]:
            try:
                validator(invalid_input)
            except (ValidationError, TypeError) as e:
                error_type = "ValidationError" if isinstance(e, ValidationError) else "TypeError"
                print(f"  {validator_name} + {repr(invalid_input)} -> {error_type}")

def demo_real_world_usage():
    """Show realistic usage scenarios with enhanced validation."""
    print("\n🌍 Real-World Usage Examples")
    print("=" * 60)
    
    def mock_get_filings(form, period="annual"):
        """Mock function using enhanced validation."""
        validated_form = validate_form_type(form)
        validated_period = validate_period_type(period)
        return f"Getting {validated_period} {validated_form} filings..."
    
    print("Function with enhanced validation:")
    print("def get_filings(form, period='annual'):")
    print("    validated_form = validate_form_type(form)")  
    print("    validated_period = validate_period_type(period)")
    print("    return f'Getting {validated_period} {validated_form} filings...'")
    
    # Show success cases
    print("\nSuccessful calls:")
    success_cases = [
        (FormType.ANNUAL_REPORT, "annual"),
        ("10-Q", PeriodType.QUARTERLY),
        ("8-K", "ttm")
    ]
    
    for form, period in success_cases:
        result = mock_get_filings(form, period)
        print(f"  get_filings({repr(form)}, {repr(period)}) -> '{result}'")
    
    # Show error guidance
    print("\nError scenarios with helpful guidance:")
    error_cases = [
        ("10k", "annual"),    # Typo in form
        ("10-K", "anual"),    # Typo in period
        ("unknown", "annual") # Invalid form
    ]
    
    for form, period in error_cases:
        try:
            mock_get_filings(form, period)
        except ValidationError as e:
            print(f"  get_filings('{form}', '{period}') -> ValidationError:")
            print(f"    {e}")
            break  # Just show one example

def demo_performance_characteristics():
    """Show that enhanced validation performs well."""
    print("\n⚡ Performance Characteristics")  
    print("=" * 60)
    
    import time
    
    # Test validation speed
    iterations = 5000
    
    # Test successful validation (fast path)
    start_time = time.time()
    for _ in range(iterations):
        validate_form_type("10-K")  # Valid input
    success_time = time.time() - start_time
    
    # Test typo detection (slower path)
    start_time = time.time()
    for _ in range(iterations):
        try:
            validate_form_type("10-X")  # Invalid input requiring suggestions
        except ValidationError:
            pass
    error_time = time.time() - start_time
    
    print(f"Performance for {iterations} validations:")
    print(f"  Valid input (fast path): {success_time:.3f}s ({success_time/iterations*1000:.2f}ms each)")
    print(f"  Invalid input (with suggestions): {error_time:.3f}s ({error_time/iterations*1000:.2f}ms each)")
    print(f"  Performance is {'excellent' if error_time < 1.0 else 'good' if error_time < 5.0 else 'acceptable'}")
    
    print("\nValidation overhead is minimal for production usage.")

def demo_developer_experience_improvements():
    """Show how this improves overall developer experience."""
    print("\n💡 Developer Experience Improvements")
    print("=" * 60)
    
    print("FEAT-004 transforms the development experience:")
    
    improvements = [
        ("❌ Frustrating", "✅ Helpful", 
         "Generic 'Invalid input' errors", "Smart suggestions with 'Did you mean?' guidance"),
        ("❌ Time-consuming", "✅ Efficient",
         "Looking up valid options in docs", "Error messages show valid options and suggestions"),
        ("❌ Intimidating", "✅ Educational", 
         "Cryptic error messages scare beginners", "Clear explanations teach correct usage"),
        ("❌ Inconsistent", "✅ Professional",
         "Different error styles across functions", "Consistent, polished error handling"),
        ("❌ Basic", "✅ Intelligent",
         "Simple string matching", "Fuzzy matching detects typos and intent")
    ]
    
    for old_label, new_label, old_desc, new_desc in improvements:
        print(f"\n  {old_label} {old_desc}")
        print(f"  {new_label} {new_desc}")
    
    print("\nResult: EdgarTools feels more professional and user-friendly!")

def main():
    """Run all demos."""
    print("🚀 FEAT-004: Enhanced Parameter Validation Demo")
    print("Transforming EdgarTools Error Handling")
    print("=" * 70)
    print()
    
    demo_before_and_after()
    demo_smart_typo_detection()
    demo_contextual_help()
    demo_different_error_scenarios()
    demo_enum_vs_string_consistency()
    demo_real_world_usage()
    demo_performance_characteristics()
    demo_developer_experience_improvements()
    
    print("\n🎉 FEAT-004 Demo Complete!")
    print("\nKey Achievements:")
    print("  🔍 Smart typo detection with fuzzy matching")
    print("  💬 Context-aware, educational error messages")
    print("  ⚡ Fast performance for production usage")
    print("  🔄 Full backwards compatibility maintained")
    print("  🎯 Enhanced developer experience across all parameters")
    print("  ⚖️ Consistent error handling framework")
    
    print("\nFEAT-004 delivers on EdgarTools' 'Joyful UX' principle by turning")
    print("frustrating validation errors into helpful learning experiences!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())