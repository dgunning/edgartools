#!/usr/bin/env python3
"""
GitHub Issue #{ISSUE_NUMBER} - {ISSUE_TITLE}

Performance Issue Template
=========================

Use this template for issues involving:
- Slow operations (data loading, parsing, queries)
- Memory leaks or excessive memory usage
- Inefficient algorithms or data structures
- Scaling problems with large datasets
- CPU-intensive operations

Template Usage:
1. Replace {ISSUE_NUMBER} with actual GitHub issue number
2. Replace {ISSUE_TITLE} with brief issue description  
3. Replace {COMPANY_TICKER} with affected company ticker
4. Add specific performance metrics and thresholds
5. Add additional test cases as needed
6. Remove template comments before committing
"""

from edgar import Company
import pandas as pd
import pytest
import time
import psutil
import os
from memory_profiler import profile


class TestIssue{ISSUE_NUMBER}:
    """Test case for GitHub issue #{ISSUE_NUMBER} - {ISSUE_TITLE}"""

    def setup_method(self):
        """Set up test data and performance baselines"""
        self.company = Company("{COMPANY_TICKER}")
        self.test_period = "2023"  # Adjust as needed
        
        # Performance thresholds (adjust based on issue)
        self.max_execution_time = 30.0  # seconds
        self.max_memory_usage = 500  # MB
        self.baseline_time = None  # Will be set during testing
        
    def test_reproduction_minimal(self):
        """Minimal reproduction of the performance issue."""
        # Replace with actual reproduction steps from issue report
        
        start_time = time.time()
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            # This should demonstrate the performance issue
            # Example operations that might be slow:
            filings = self.company.get_filings(form="10-K", year=self.test_period)
            filing = filings.latest()
            
            # statements = filing.xbrl.statements  # Might be slow
            # data = statements.get_statement("INCOME")  # Memory intensive
            
            execution_time = time.time() - start_time
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = final_memory - initial_memory
            
            # Performance assertions
            assert execution_time < self.max_execution_time, \
                f"Operation took {execution_time:.2f}s, expected < {self.max_execution_time}s"
            
            assert memory_used < self.max_memory_usage, \
                f"Memory usage {memory_used:.2f}MB, expected < {self.max_memory_usage}MB"
                
            print(f"✓ Performance: {execution_time:.2f}s, {memory_used:.2f}MB")
            
        except Exception as e:
            execution_time = time.time() - start_time
            pytest.fail(f"Performance test failed after {execution_time:.2f}s: {str(e)}")

    def test_large_dataset_performance(self):
        """Test performance with large datasets."""
        pytest.skip("Enable for large dataset performance testing")
        
        # Test with multiple companies or years to simulate large dataset
        test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        
        start_time = time.time()
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        results = []
        for ticker in test_tickers:
            company = Company(ticker)
            filings = company.get_filings(form="10-K", year=self.test_period)
            # Process each company's data
            # results.extend(self._process_company_data(company, filings))
            
        execution_time = time.time() - start_time
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_used = final_memory - initial_memory
        
        # Scale-based performance assertions
        max_time_per_company = self.max_execution_time / len(test_tickers)
        assert execution_time < self.max_execution_time * 2, \
            f"Large dataset processing took {execution_time:.2f}s"
            
        assert memory_used < self.max_memory_usage * 2, \
            f"Large dataset memory usage {memory_used:.2f}MB excessive"

    def test_memory_leak_detection(self):
        """Test for memory leaks in repetitive operations."""
        pytest.skip("Enable for memory leak detection")
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Perform same operation multiple times
        for i in range(10):
            filings = self.company.get_filings(form="10-K", year=self.test_period)
            filing = filings.latest()
            
            # Force garbage collection periodically
            if i % 3 == 0:
                import gc
                gc.collect()
            
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory
            
            # Check for excessive memory growth
            if memory_growth > self.max_memory_usage:
                pytest.fail(f"Memory leak detected: {memory_growth:.2f}MB growth after {i+1} iterations")

    @profile
    def test_memory_profiling(self):
        """Detailed memory profiling of problematic operations."""
        pytest.skip("Enable for detailed memory profiling")
        
        # Use @profile decorator to get line-by-line memory usage
        # Run with: python -m memory_profiler test_file.py
        
        filings = self.company.get_filings(form="10-K", year=self.test_period)
        filing = filings.latest()
        
        # Memory-intensive operations
        # statements = filing.xbrl.statements
        # for statement in statements:
        #     data = statement.to_dataframe()  # Potentially memory-intensive

    def test_cpu_intensive_operations(self):
        """Test CPU-intensive operations for efficiency."""
        pytest.skip("Enable for CPU performance testing")
        
        import cProfile
        import pstats
        from io import StringIO
        
        # Profile CPU-intensive operations
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            # CPU-intensive operation
            filings = self.company.get_filings(form="10-K")
            for filing in filings[:5]:
                # statements = filing.xbrl.statements
                # self._analyze_statements(statements)  # CPU-intensive analysis
                pass
                
        finally:
            profiler.disable()
            
        # Analyze profiling results
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(10)  # Top 10 time-consuming functions
        
        profile_output = s.getvalue()
        print(f"CPU Profiling Results:\n{profile_output}")

    def test_concurrent_performance(self):
        """Test performance under concurrent load."""
        pytest.skip("Enable for concurrency testing")
        
        import threading
        import concurrent.futures
        
        def fetch_company_data(ticker):
            company = Company(ticker)
            filings = company.get_filings(form="10-K", year=self.test_period)
            return len(filings)
        
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
        
        start_time = time.time()
        
        # Test concurrent access
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(fetch_company_data, ticker) for ticker in tickers]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        execution_time = time.time() - start_time
        
        # Concurrent performance should be better than sequential
        assert execution_time < self.max_execution_time, \
            f"Concurrent execution took {execution_time:.2f}s"

    def _process_company_data(self, company, filings):
        """Helper method for processing company data in performance tests."""
        # Simulate data processing that might be performance-sensitive
        results = []
        for filing in filings[:3]:  # Limit for testing
            # Process filing data
            # result = self._extract_financial_metrics(filing)
            # results.append(result)
            pass
        return results
        
    def _analyze_statements(self, statements):
        """Helper method for CPU-intensive statement analysis."""
        # Simulate complex analysis that might be CPU-intensive
        # for statement in statements:
        #     self._perform_complex_calculations(statement)
        pass


if __name__ == "__main__":
    # Allow running as script for manual testing during development
    test = TestIssue{ISSUE_NUMBER}()
    test.setup_method()
    test.test_reproduction_minimal()
    print("✓ Performance issue reproduction completed successfully")