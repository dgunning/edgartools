#!/usr/bin/env python3
"""
Test implementation for FEAT-005: Statement Type Classifications

This script tests the new StatementType enum functionality to ensure:
1. StatementType enum works correctly with all statement types
2. Validation functions work as expected with financial statements
3. Type hints provide proper IDE autocomplete for statements  
4. Backwards compatibility is maintained
5. Convenience collections work properly
6. Enhanced error messages guide users to correct statement types
"""

import sys
from pathlib import Path

# Add project root to path for testing
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from edgar.enums import (
    StatementType,
    StatementInput,
    validate_statement_type,
    ValidationError,
    PRIMARY_STATEMENTS,
    COMPREHENSIVE_STATEMENTS, 
    ANALYTICAL_STATEMENTS,
    SPECIALIZED_STATEMENTS,
    ALL_STATEMENTS
)

def test_statement_type_enum():
    """Test StatementType enum basic functionality."""
    print("🔍 Testing StatementType enum basic functionality...")
    
    # Test primary statement values
    assert StatementType.INCOME_STATEMENT == "income_statement"
    assert StatementType.BALANCE_SHEET == "balance_sheet"
    assert StatementType.CASH_FLOW == "cash_flow_statement"
    assert StatementType.CHANGES_IN_EQUITY == "changes_in_equity"
    
    # Test comprehensive income
    assert StatementType.COMPREHENSIVE_INCOME == "comprehensive_income"
    
    # Test analytical statements
    assert StatementType.SEGMENTS == "segment_reporting"
    assert StatementType.FOOTNOTES == "footnotes"
    assert StatementType.ACCOUNTING_POLICIES == "accounting_policies"
    
    # Test aliases
    assert StatementType.PROFIT_LOSS == "income_statement"
    assert StatementType.PL_STATEMENT == "income_statement"
    assert StatementType.FINANCIAL_POSITION == "balance_sheet"
    assert StatementType.CASH_FLOWS == "cash_flow_statement"
    
    print("   ✅ All enum values work correctly")

def test_statement_validation():
    """Test statement validation function."""
    print("🔍 Testing statement validation...")
    
    # Test valid enum input
    assert validate_statement_type(StatementType.INCOME_STATEMENT) == "income_statement"
    assert validate_statement_type(StatementType.BALANCE_SHEET) == "balance_sheet"
    assert validate_statement_type(StatementType.CASH_FLOW) == "cash_flow_statement"
    
    # Test valid string input
    assert validate_statement_type("income_statement") == "income_statement"
    assert validate_statement_type("balance_sheet") == "balance_sheet"
    assert validate_statement_type("footnotes") == "footnotes"
    
    print("   ✅ Valid inputs work correctly")
    
    # Test typo detection with suggestions
    try:
        validate_statement_type("income")  # partial match
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "income_statement" in str(e)
        print(f"   ✅ Partial match suggestion: {e}")
    
    try:
        validate_statement_type("balanc")  # typo
        assert False, "Should have raised ValidationError" 
    except ValidationError as e:
        assert "balance_sheet" in str(e)
        print(f"   ✅ Typo detection: {e}")
    
    # Test completely invalid input
    try:
        validate_statement_type("invalid_statement")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "StatementType" in str(e)
        assert "Primary statements" in str(e)  # Context hint
        print(f"   ✅ Invalid input with context: {e}")
    
    # Test wrong type
    try:
        validate_statement_type(123)
        assert False, "Should have raised TypeError"
    except TypeError as e:
        assert "StatementType or str" in str(e)
        print(f"   ✅ Type validation: {e}")

def test_statement_collections():
    """Test statement collections."""
    print("🔍 Testing statement collections...")
    
    # Test PRIMARY_STATEMENTS
    assert StatementType.INCOME_STATEMENT in PRIMARY_STATEMENTS
    assert StatementType.BALANCE_SHEET in PRIMARY_STATEMENTS  
    assert StatementType.CASH_FLOW in PRIMARY_STATEMENTS
    assert StatementType.CHANGES_IN_EQUITY in PRIMARY_STATEMENTS
    assert len(PRIMARY_STATEMENTS) == 4
    print("   ✅ Primary statements collection correct")
    
    # Test COMPREHENSIVE_STATEMENTS (includes comprehensive income)
    assert StatementType.COMPREHENSIVE_INCOME in COMPREHENSIVE_STATEMENTS
    assert all(stmt in COMPREHENSIVE_STATEMENTS for stmt in PRIMARY_STATEMENTS)
    assert len(COMPREHENSIVE_STATEMENTS) == 5
    print("   ✅ Comprehensive statements collection correct")
    
    # Test ANALYTICAL_STATEMENTS
    assert StatementType.SEGMENTS in ANALYTICAL_STATEMENTS
    assert StatementType.FOOTNOTES in ANALYTICAL_STATEMENTS
    assert StatementType.ACCOUNTING_POLICIES in ANALYTICAL_STATEMENTS
    print("   ✅ Analytical statements collection correct")
    
    # Test SPECIALIZED_STATEMENTS
    assert StatementType.REGULATORY_CAPITAL in SPECIALIZED_STATEMENTS
    assert StatementType.INSURANCE_RESERVES in SPECIALIZED_STATEMENTS
    print("   ✅ Specialized statements collection correct")
    
    # Test ALL_STATEMENTS includes everything
    all_enum_values = set(StatementType)
    all_collection_values = set(ALL_STATEMENTS)
    
    # Remove aliases to get unique statement types
    unique_enum_values = {s for s in all_enum_values 
                         if s.value not in [alias.value for alias in [
                             StatementType.PROFIT_LOSS, StatementType.PL_STATEMENT,
                             StatementType.FINANCIAL_POSITION, StatementType.STATEMENT_OF_POSITION,
                             StatementType.CASH_FLOWS, StatementType.EQUITY_CHANGES
                         ]] or s.name in [
                             'INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW', 'CHANGES_IN_EQUITY'
                         ]}
    
    assert len(unique_enum_values) == len(ALL_STATEMENTS)
    print("   ✅ All statements collection includes all unique values")

def test_type_hints():
    """Test type hint functionality."""
    print("🔍 Testing type hints...")
    
    def example_function(statement: StatementInput) -> str:
        """Example function using StatementInput type hint."""
        return validate_statement_type(statement)
    
    # Test with enum
    assert example_function(StatementType.INCOME_STATEMENT) == "income_statement"
    
    # Test with string
    assert example_function("balance_sheet") == "balance_sheet"
    
    print("   ✅ Type hints work correctly")

def test_real_world_usage():
    """Test realistic usage scenarios."""
    print("🔍 Testing real-world usage scenarios...")
    
    def mock_get_statement(statement_type: StatementInput) -> str:
        """Mock function simulating real EdgarTools usage."""
        validated_statement = validate_statement_type(statement_type)
        return f"Getting {validated_statement} data..."
    
    # Test default enum usage
    result1 = mock_get_statement(StatementType.INCOME_STATEMENT)
    assert result1 == "Getting income_statement data..."
    
    # Test explicit enum usage
    result2 = mock_get_statement(StatementType.BALANCE_SHEET)
    assert result2 == "Getting balance_sheet data..."
    
    # Test backwards compatible string usage
    result3 = mock_get_statement("cash_flow_statement")
    assert result3 == "Getting cash_flow_statement data..."
    
    # Test alias usage (using enum, not string)
    result4 = mock_get_statement(StatementType.FINANCIAL_POSITION)  # alias for balance_sheet
    assert result4 == "Getting balance_sheet data..."
    
    print("   ✅ Real-world usage patterns work")

def test_financial_statement_categories():
    """Test financial statement categorization."""
    print("🔍 Testing financial statement categorization...")
    
    # Test primary statement identification
    def is_primary_statement(statement_type: StatementInput) -> bool:
        """Check if statement is a primary financial statement."""
        validated = validate_statement_type(statement_type)
        return any(s.value == validated for s in PRIMARY_STATEMENTS)
    
    assert is_primary_statement(StatementType.INCOME_STATEMENT) == True
    assert is_primary_statement("balance_sheet") == True
    assert is_primary_statement(StatementType.FOOTNOTES) == False
    assert is_primary_statement("regulatory_capital") == False
    
    print("   ✅ Primary statement identification works")
    
    # Test comprehensive analysis workflow
    def comprehensive_statement_analysis() -> dict:
        """Mock comprehensive statement analysis."""
        results = {}
        for statement in PRIMARY_STATEMENTS:
            try:
                validated = validate_statement_type(statement)
                results[validated] = f"Analyzed {validated}"
            except ValidationError:
                results[statement.value] = "Not available"
        return results
    
    analysis = comprehensive_statement_analysis()
    assert len(analysis) == 4
    assert "income_statement" in analysis
    assert "balance_sheet" in analysis
    print("   ✅ Comprehensive analysis workflow works")

def test_alias_handling():
    """Test that aliases work correctly."""
    print("🔍 Testing alias handling...")
    
    # Test all aliases resolve to correct values
    alias_tests = [
        (StatementType.PROFIT_LOSS, "income_statement"),
        (StatementType.PL_STATEMENT, "income_statement"), 
        (StatementType.FINANCIAL_POSITION, "balance_sheet"),
        (StatementType.STATEMENT_OF_POSITION, "balance_sheet"),
        (StatementType.CASH_FLOWS, "cash_flow_statement"),
        (StatementType.EQUITY_CHANGES, "changes_in_equity")
    ]
    
    for alias, expected in alias_tests:
        assert validate_statement_type(alias) == expected
        print(f"   ✅ {alias.name} -> {expected}")
    
    print("   ✅ All aliases work correctly")

def test_enum_iteration():
    """Test enum iteration and introspection."""
    print("🔍 Testing enum iteration...")
    
    # Test we can iterate over statements
    statement_names = [stmt.name for stmt in StatementType]
    statement_values = [stmt.value for stmt in StatementType]
    
    assert "INCOME_STATEMENT" in statement_names
    assert "BALANCE_SHEET" in statement_names
    assert "income_statement" in statement_values
    assert "balance_sheet" in statement_values
    
    # Test unique values (aliases share values with primary enums)
    unique_values = set(statement_values)
    expected_unique_count = 11  # Primary (4) + Comprehensive (1) + Analytical (4) + Specialized (2) 
    assert len(unique_values) == expected_unique_count
    
    print(f"   ✅ Available statements: {sorted(unique_values)}")

def test_error_message_quality():
    """Test that error messages are helpful for financial statements."""
    print("🔍 Testing error message quality...")
    
    test_cases = [
        # (input, expected_in_message)
        ("income", ["income_statement"]),  # Should suggest full name
        ("balanc", ["balance_sheet"]),     # Typo detection
        ("cash", ["cash_flow_statement"]), # Partial match
        ("unknown_statement", ["Primary statements", "income_statement"])
    ]
    
    for test_input, expected_parts in test_cases:
        try:
            validate_statement_type(test_input)
            assert False, f"Should have raised error for {test_input}"
        except ValidationError as e:
            error_msg = str(e)
            for part in expected_parts:
                assert part in error_msg, f"Expected '{part}' in error message: {error_msg}"
            print(f"   ✅ '{test_input}' -> Professional error message")

def test_performance():
    """Test that statement validation performance is acceptable."""
    print("🔍 Testing validation performance...")
    
    import time
    
    # Test statement validation performance
    start_time = time.time()
    for _ in range(1000):
        try:
            validate_statement_type("income")  # Invalid, will generate suggestions
        except ValidationError:
            pass
    statement_time = time.time() - start_time
    
    print(f"   ✅ 1000 statement validations: {statement_time:.3f}s ({statement_time/1000*1000:.2f}ms each)")
    
    # Performance should be reasonable (< 5ms per validation)
    assert statement_time < 5.0, "Statement validation too slow"
    print("   ✅ Performance is acceptable")

def main():
    """Run all tests."""
    print("🚀 Testing FEAT-005: Statement Type Classifications\n")
    
    try:
        test_statement_type_enum()
        test_statement_validation()
        test_statement_collections()
        test_type_hints()
        test_real_world_usage()
        test_financial_statement_categories()
        test_alias_handling()
        test_enum_iteration()
        test_error_message_quality()
        test_performance()
        
        print("\n🎉 All tests passed! FEAT-005 Statement Type Classifications is working correctly.")
        print("\n📋 Summary:")
        print("   ✅ StatementType enum with comprehensive financial statement coverage")
        print("   ✅ Enhanced validation with smart suggestions for financial terms")
        print("   ✅ Convenience collections for different statement categories")
        print("   ✅ Alias support for alternative statement naming")
        print("   ✅ Type hints for better financial analysis workflows")
        print("   ✅ Professional error messages with financial context")
        print("   ✅ Excellent performance for production financial applications")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())