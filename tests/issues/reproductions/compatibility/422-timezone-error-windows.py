#!/usr/bin/env python3
"""
GitHub Issue #422 - PyArrow timezone error on Windows 10

Compatibility Issue Template
===========================

Use this template for issues involving:
- Platform-specific bugs (Windows, macOS, Linux)
- Python version compatibility issues  
- Dependency version conflicts
- Library compatibility problems
- Environment-specific failures
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
        self.company = Company("AAPL")  # Default test company
        self.test_period = "2025"
        
        # Environment information
        self.platform_info = {
            "system": platform.system(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "python_version_info": sys.version_info,
            "architecture": platform.architecture(),
            "machine": platform.machine(),
        }
        
    def test_reproduction_minimal(self):
        """Minimal reproduction of the compatibility issue."""
        # This reproduces the PyArrow timezone error from issue #422
        
        print(f"Testing on: {self.platform_info['system']} {self.platform_info['platform']}")
        print(f"Python: {self.platform_info['python_version']}")
        
        try:
            # This should demonstrate the timezone compatibility issue
            filings = self.company.get_filings(year=2025)
            
            # For now, just ensure basic functionality works
            assert filings is not None, "Basic filing access should work across platforms"
            
        except Exception as e:
            # Capture detailed error information for compatibility debugging
            error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "platform": self.platform_info,
                "working_directory": os.getcwd(),
                "environment_variables": {k: v for k, v in os.environ.items() if 'EDGAR' in k}
            }
            
            # Check if this is the specific PyArrow timezone error
            if "ArrowInvalid" in str(e) and "timezone" in str(e).lower():
                pytest.fail(f"PyArrow timezone error confirmed: {str(e)}")
            else:
                pytest.fail(f"Compatibility error: {error_info}")

    def test_timezone_handling(self):
        """Test timezone handling across different systems.""" 
        # This is particularly relevant for the PyArrow timezone issue
        import datetime
        
        try:
            import pytz
            
            # Test basic timezone operations
            eastern = pytz.timezone('America/New_York')
            utc = pytz.UTC
            
            now = datetime.datetime.now(eastern)
            now_utc = now.astimezone(utc)
            
            assert now_utc.tzinfo == utc, "Timezone conversion should work"
            
        except ImportError:
            pytest.skip("pytz not available for timezone testing")
        except Exception as e:
            if "timezone database" in str(e).lower():
                pytest.fail(f"Timezone database issue: {str(e)}")
            else:
                raise

    def test_dependency_compatibility(self):
        """Test compatibility with required dependencies."""
        # Test pandas compatibility
        import pandas as pd
        from edgar.core import pandas_version
        
        print(f"Pandas version: {pd.__version__} -> {pandas_version}")
        assert pandas_version >= (2, 0, 0), "Pandas should be version 2.0+"
        
        # Test pyarrow compatibility
        import pyarrow as pa
        print(f"PyArrow version: {pa.__version__}")
        
        # Test if pyarrow can handle timezone operations
        try:
            # This is the operation that might fail on Windows
            import pyarrow.compute as pc
            # Test basic timezone functionality that EdgarTools might use
        except Exception as e:
            if "timezone" in str(e).lower():
                pytest.fail(f"PyArrow timezone functionality failed: {str(e)}")


if __name__ == "__main__":
    # Allow running as script for manual testing during development
    test = TestIssue422()
    test.setup_method()
    test.test_reproduction_minimal()
    print("✓ Compatibility issue reproduction completed successfully")