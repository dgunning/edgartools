#!/usr/bin/env python3
"""
GitHub Issue #{ISSUE_NUMBER} - {ISSUE_TITLE}

Compatibility Issue Template
===========================

Use this template for issues involving:
- Platform-specific bugs (Windows, macOS, Linux)
- Python version compatibility issues  
- Dependency version conflicts
- Library compatibility problems
- Environment-specific failures

Template Usage:
1. Replace {ISSUE_NUMBER} with actual GitHub issue number
2. Replace {ISSUE_TITLE} with brief issue description  
3. Replace {PLATFORM} with affected platform(s)
4. Replace {PYTHON_VERSION} with affected Python version
5. Add additional test cases as needed
6. Remove template comments before committing
"""

from edgar import Company
import pandas as pd
import pytest
import sys
import platform
import os
from pathlib import Path


class TestIssue{ISSUE_NUMBER}:
    """Test case for GitHub issue #{ISSUE_NUMBER} - {ISSUE_TITLE}"""

    def setup_method(self):
        """Set up test data and environment information"""
        self.company = Company("AAPL")  # Default test company
        self.test_period = "2023"
        
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
        # Replace with actual reproduction steps from issue report
        
        print(f"Testing on: {self.platform_info['system']} {self.platform_info['platform']}")
        print(f"Python: {self.platform_info['python_version']}")
        
        try:
            # This should demonstrate the compatibility issue
            # Common compatibility issues:
            
            # 1. Path handling differences
            filings = self.company.get_filings(form="10-K", year=self.test_period)
            filing = filings.latest()
            
            # 2. File encoding issues
            # content = filing.html()
            # assert isinstance(content, str), "Content should be properly decoded string"
            
            # 3. Platform-specific library behavior
            # xbrl = filing.xbrl
            # statements = xbrl.statements
            
            # For now, just ensure basic functionality works
            assert filing is not None, "Basic filing access should work across platforms"
            
        except Exception as e:
            # Capture detailed error information for compatibility debugging
            error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "platform": self.platform_info,
                "working_directory": os.getcwd(),
                "environment_variables": {k: v for k, v in os.environ.items() if 'EDGAR' in k}
            }
            pytest.fail(f"Compatibility error: {error_info}")

    def test_python_version_compatibility(self):
        """Test compatibility across supported Python versions."""
        pytest.skip("Enable for Python version compatibility testing")
        
        min_python = (3, 10)  # EdgarTools minimum Python version
        current_python = sys.version_info[:2]
        
        assert current_python >= min_python, \
            f"Python {current_python} should be >= {min_python}"
        
        # Test version-specific features
        if current_python >= (3, 11):
            # Test features that require Python 3.11+
            pass
        elif current_python >= (3, 10):
            # Test features that work on Python 3.10+
            pass

    def test_path_handling_cross_platform(self):
        """Test file path handling across different platforms."""
        pytest.skip("Enable if issue involves path handling")
        
        # Test path operations that might behave differently across platforms
        from edgar.core import get_edgar_data_directory
        
        data_dir = get_edgar_data_directory()
        
        # Validate path behavior
        assert data_dir.exists(), "Data directory should be accessible on all platforms"
        assert data_dir.is_dir(), "Data directory should be a directory"
        
        # Test path joining and resolution
        test_path = data_dir / "test_file.txt"
        assert isinstance(str(test_path), str), "Path should convert to string properly"
        
        # Test different path separators
        if platform.system() == "Windows":
            # Windows-specific path tests
            assert "\\" in str(data_dir) or "/" in str(data_dir), "Windows paths should be valid"
        else:
            # Unix-like path tests  
            assert "/" in str(data_dir), "Unix paths should use forward slashes"

    def test_dependency_compatibility(self):
        """Test compatibility with required dependencies."""
        pytest.skip("Enable for dependency compatibility testing")
        
        # Test pandas compatibility
        import pandas as pd
        from edgar.core import pandas_version
        
        print(f"Pandas version: {pd.__version__} -> {pandas_version}")
        assert pandas_version >= (2, 0, 0), "Pandas should be version 2.0+"
        
        # Test pyarrow compatibility
        import pyarrow as pa
        print(f"PyArrow version: {pa.__version__}")
        
        # Test other critical dependencies
        dependencies_to_check = [
            ("httpx", "0.25.0"),
            ("rich", "13.8.0"),
            ("beautifulsoup4", "4.10.0"),
        ]
        
        for dep_name, min_version in dependencies_to_check:
            try:
                dep_module = __import__(dep_name)
                if hasattr(dep_module, "__version__"):
                    print(f"{dep_name} version: {dep_module.__version__}")
            except ImportError:
                pytest.fail(f"Required dependency {dep_name} not available")

    def test_encoding_compatibility(self):
        """Test text encoding handling across platforms."""
        pytest.skip("Enable if issue involves text encoding")
        
        filings = self.company.get_filings(form="10-K", year=self.test_period)
        filing = filings.latest()
        
        # Test HTML content encoding
        # html_content = filing.html()
        # assert isinstance(html_content, str), "HTML content should be properly decoded"
        
        # Test for common encoding issues
        # Check for BOM, invalid UTF-8, Windows-1252, etc.
        # self._validate_text_encoding(html_content)

    def test_timezone_handling(self):
        """Test timezone handling across different systems.""" 
        pytest.skip("Enable if issue involves timezone handling")
        
        # This is particularly relevant for the PyArrow timezone issue
        import datetime
        import pytz
        
        # Test basic timezone operations
        eastern = pytz.timezone('America/New_York')
        utc = pytz.UTC
        
        now = datetime.datetime.now(eastern)
        now_utc = now.astimezone(utc)
        
        assert now_utc.tzinfo == utc, "Timezone conversion should work"
        
        # Test with EdgarTools data that uses timestamps
        filings = self.company.get_filings(form="10-K", year=self.test_period)
        filing = filings.latest()
        
        # filing_date = filing.filing_date
        # assert filing_date is not None, "Filing date should be parseable"

    def test_memory_architecture_compatibility(self):
        """Test compatibility across different memory architectures."""
        pytest.skip("Enable for architecture-specific testing")
        
        arch = platform.machine()
        print(f"Architecture: {arch}")
        
        # Test large data handling on different architectures
        if arch in ["x86_64", "AMD64"]:
            # 64-bit architecture tests
            pass
        elif arch in ["i386", "i686"]:
            # 32-bit architecture tests (if supported)
            pass
        elif arch in ["arm64", "aarch64"]:
            # ARM architecture tests (Apple Silicon, etc.)
            pass
            
        # Ensure basic functionality works regardless of architecture
        filings = self.company.get_filings(form="10-K", year=self.test_period)
        assert len(filings) > 0, f"Should work on {arch} architecture"

    def _validate_text_encoding(self, text):
        """Helper method to validate text encoding."""
        # Check for encoding issues:
        # - BOM markers
        # - Invalid UTF-8 sequences  
        # - Windows-1252 characters
        # - Mixed encodings
        
        if text.startswith('\ufeff'):
            pytest.fail("Text contains BOM marker")
            
        try:
            text.encode('utf-8')
        except UnicodeEncodeError as e:
            pytest.fail(f"Text contains non-UTF-8 characters: {e}")

    def _get_environment_info(self):
        """Helper method to collect detailed environment information."""
        return {
            "platform": platform.platform(),
            "python_version": sys.version,
            "python_executable": sys.executable,
            "working_directory": os.getcwd(),
            "environment_variables": dict(os.environ),
            "installed_packages": self._get_installed_packages(),
        }
        
    def _get_installed_packages(self):
        """Helper method to get installed package versions."""
        try:
            import pkg_resources
            return {pkg.key: pkg.version for pkg in pkg_resources.working_set}
        except ImportError:
            return "pkg_resources not available"


if __name__ == "__main__":
    # Allow running as script for manual testing during development
    test = TestIssue{ISSUE_NUMBER}()
    test.setup_method()
    test.test_reproduction_minimal()
    print("✓ Compatibility issue reproduction completed successfully")