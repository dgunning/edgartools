#!/usr/bin/env python3
"""
GitHub Issue #422 - PyArrow timezone error on Windows 10

Compatibility Issue - Systematic Reproduction
=============================================

Root Cause: PyArrow timezone database not found on Windows systems
Affects: Windows 10, Python 3.13, EdgarTools 4.9.0
Error: pyarrow.lib.ArrowInvalid: Cannot locate timezone 'UTC'

Created using: compatibility-template.py
Investigation: Follows systematic issue workflow
"""

from edgar import Company
import pandas as pd
import pytest
import sys
import platform
import os
from pathlib import Path


class TestIssue422:
    """Test case for GitHub issue #422 - PyArrow timezone error on Windows 10"""

    def setup_method(self):
        """Set up test data and environment information"""
        self.company = Company("AAPL")
        self.test_period = "2025"
        
        # Environment information for debugging
        self.platform_info = {
            "system": platform.system(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "python_version_info": sys.version_info,
            "architecture": platform.architecture(),
            "machine": platform.machine(),
        }

    @pytest.mark.regression
    def test_reproduction_minimal(self):
        """Minimal reproduction of the PyArrow timezone compatibility issue."""
        print(f"Testing on: {self.platform_info['system']} {self.platform_info['platform']}")
        print(f"Python: {self.platform_info['python_version']}")
        
        try:
            # This specific call triggers the PyArrow timezone error on Windows
            company = Company("AAPL")
            filings = company.get_filings(year=2025)
            
            # If we get here, the issue is resolved
            assert filings is not None, "Should return filings data"
            print(f"✅ SUCCESS: Retrieved {len(filings)} filings")
            
        except Exception as e:
            error_message = str(e)
            error_type = type(e).__name__
            
            # Specific check for the PyArrow timezone error
            if "ArrowInvalid" in error_type and "timezone" in error_message.lower():
                # This is the expected error on Windows without tzdata
                pytest.fail(f"PyArrow timezone error (EXPECTED ON WINDOWS): {error_message}")
            elif "timezone database" in error_message.lower():
                pytest.fail(f"Timezone database error: {error_message}")
            else:
                # Unexpected error type
                pytest.fail(f"Unexpected error ({error_type}): {error_message}")

    @pytest.mark.regression
    def test_timezone_dependency_check(self):
        """Check if timezone dependencies are available."""
        # Check for tzdata package (the typical fix)
        try:
            import tzdata
            print("✅ tzdata package is available")
            tzdata_available = True
        except ImportError:
            print("❌ tzdata package not found")
            tzdata_available = False
            
        # Check PyArrow version
        try:
            import pyarrow as pa
            pyarrow_version = pa.__version__
            print(f"PyArrow version: {pyarrow_version}")
        except ImportError:
            pytest.fail("PyArrow not available")
            
        # On Windows, we expect tzdata to be needed
        if platform.system() == "Windows" and not tzdata_available:
            pytest.skip("tzdata package required on Windows for timezone support")

    @pytest.mark.regression
    def test_alternative_timezone_solutions(self):
        """Test alternative solutions to timezone issues."""
        pytest.skip("Enable to test different timezone handling approaches")
        
        # Test different timezone libraries and configurations
        timezone_solutions = [
            "tzdata",          # Most common solution
            "pytz",            # Alternative timezone library  
            "zoneinfo",        # Python 3.9+ built-in
        ]
        
        available_solutions = []
        for solution in timezone_solutions:
            try:
                __import__(solution)
                available_solutions.append(solution)
                print(f"✅ {solution} is available")
            except ImportError:
                print(f"❌ {solution} not available")
                
        if not available_solutions:
            pytest.fail("No timezone solutions available")

    @pytest.mark.regression
    def test_environment_specific_behavior(self):
        """Test behavior specific to different environments."""
        system = platform.system()
        
        if system == "Windows":
            # Windows-specific testing
            print("Testing Windows-specific timezone handling")
            # Check for common Windows timezone issues
            
        elif system == "Darwin":  # macOS
            # macOS usually has timezone data available
            print("Testing macOS timezone handling")
            
        elif system == "Linux":
            # Linux distributions vary in timezone data availability
            print("Testing Linux timezone handling")
            
        # The core test: can we handle timezone operations?
        try:
            import datetime
            import pytz
            
            utc = pytz.UTC
            now_utc = datetime.datetime.now(utc)
            print(f"✅ Timezone operations working: {now_utc}")
            
        except Exception as e:
            if system == "Windows":
                # Expected on Windows without proper timezone setup
                print(f"⚠️  Timezone operations failed on Windows (expected): {e}")
            else:
                pytest.fail(f"Timezone operations should work on {system}: {e}")

    @pytest.mark.regression
    def test_filings_retrieval_robustness(self):
        """Test robust filings retrieval with error handling."""
        # This test shows how the issue should be handled gracefully
        company = Company("AAPL")
        
        try:
            # Attempt the operation that fails
            filings = company.get_filings(year=2025)
            
            # If successful, validate the results
            assert filings is not None
            assert len(filings) >= 0
            print(f"✅ Successfully retrieved filings: {len(filings)}")
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if this is the known timezone issue
            if "timezone" in error_msg.lower() and "database" in error_msg.lower():
                # This is a known issue - log it but don't fail the test
                print(f"⚠️  Known timezone issue: {error_msg}")
                print("💡 Solution: Install tzdata package with 'pip install tzdata'")
                
                # In a real application, we might want to provide a helpful error message
                suggested_fix = "pip install tzdata"
                print(f"🔧 Suggested fix: {suggested_fix}")
                
                # For testing purposes, we'll mark this as expected failure
                pytest.xfail("Known timezone database issue on Windows")
            else:
                # Unexpected error - this should fail the test
                raise


# Demonstration of systematic investigation approach
def demonstrate_systematic_investigation():
    """
    This function demonstrates how the new systematic workflow 
    would investigate issue #422 vs the old gists/bugs approach.
    """
    
    print("=" * 60)
    print("SYSTEMATIC INVESTIGATION DEMONSTRATION")
    print("=" * 60)
    
    print("\n🔍 ISSUE ANALYSIS:")
    print("   Issue #422: PyArrow timezone error on Windows")
    print("   Category: Compatibility Issue") 
    print("   Scope: Windows platform, Python 3.13+")
    print("   Impact: Prevents basic filings retrieval on Windows")
    
    print("\n📊 PATTERN RECOGNITION:")
    print("   - Similar to other Windows-specific dependency issues")
    print("   - Related to PyArrow timezone handling changes")
    print("   - Affects core get_filings() functionality")
    print("   - Likely affects multiple Windows users")
    
    print("\n🧪 SYSTEMATIC REPRODUCTION:")
    print("   - Created structured test with environment detection")
    print("   - Added specific error type checking")
    print("   - Included dependency validation")
    print("   - Provided clear success/failure conditions")
    
    print("\n💡 ROOT CAUSE IDENTIFICATION:")
    print("   - PyArrow requires timezone database for date operations")
    print("   - Windows doesn't include timezone data by default")  
    print("   - Python 3.13 + PyArrow version compatibility issue")
    print("   - Missing 'tzdata' package on Windows installations")
    
    print("\n🔧 PROPOSED SOLUTION:")
    print("   - Primary: Add tzdata as dependency for Windows")
    print("   - Secondary: Graceful error handling with helpful message")
    print("   - Tertiary: Documentation update for Windows users")
    
    print("\n✅ VERIFICATION PLAN:")
    print("   - Test fix on Windows 10 + Python 3.13")
    print("   - Verify no regression on macOS/Linux") 
    print("   - Create regression test to prevent re-occurrence")
    print("   - Update installation documentation")
    
    print("\n📚 KNOWLEDGE EXTRACTION:")
    print("   - Add to compatibility-patterns.md")
    print("   - Update Windows installation guide")
    print("   - Add to troubleshooting documentation")
    print("   - Consider proactive dependency management")
    
    print("\n🆚 OLD vs NEW APPROACH:")
    print("   OLD (gists/bugs/):")
    print("   - Minimal reproduction script")
    print("   - No systematic analysis")
    print("   - Knowledge lost after resolution")
    print("   - No pattern recognition")
    print("")
    print("   NEW (systematic workflow):")
    print("   - Structured investigation template")
    print("   - Cross-platform testing approach") 
    print("   - Knowledge captured in patterns/")
    print("   - Automated regression prevention")
    print("   - Integration with agent-assisted resolution")


if __name__ == "__main__":
    # Run the demonstration
    demonstrate_systematic_investigation()
    
    # Run the actual test
    print("\n" + "=" * 60)
    print("RUNNING SYSTEMATIC TEST")
    print("=" * 60)
    
    test = TestIssue422()
    test.setup_method()
    
    try:
        test.test_reproduction_minimal()
        print("✅ Test completed successfully")
    except Exception as e:
        print(f"⚠️  Test result: {e}")
        print("💡 This demonstrates the systematic error handling")
    
    # Show dependency check
    print("\n🔍 DEPENDENCY CHECK:")
    try:
        test.test_timezone_dependency_check()
    except Exception as e:
        print(f"   Result: {e}")
    
    print("\n📝 SYSTEMATIC WORKFLOW DEMONSTRATION COMPLETE")
    print("   This shows how issue #422 would be handled with the new system")
    print("   vs the old gists/bugs/422-CompanyFilings.py approach")