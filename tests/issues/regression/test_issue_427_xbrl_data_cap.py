#!/usr/bin/env python3
"""
Regression test for GitHub Issue #427
XBRLS cap out at 2018

This test ensures that the .head() method on filings and XBRLS objects
returns recent data (newer than 2018) for major companies.
"""

import pytest
from datetime import date
from edgar import Company
from edgar.xbrl.stitching.xbrls import XBRLS


@pytest.mark.regression
class TestIssue427XBRLDataCap:
    """Regression tests for XBRL data cap issue."""
    
    @pytest.mark.parametrize("ticker,company_name", [
        ("AAPL", "Apple Inc."),
        ("MSFT", "Microsoft Corporation"),
        ("IBM", "International Business Machines Corporation")
    ])
    def test_filings_head_returns_recent_data(self, ticker, company_name):
        """Test that .head() on filings returns data newer than 2018."""
        company = Company(ticker)
        
        # Get 10-K filings
        tenk_filings = company.get_filings(form='10-K')
        
        # Ensure we have some filings
        assert len(tenk_filings) > 0, f"No 10-K filings found for {ticker}"
        
        # Get head filings
        head_filings = tenk_filings.head(10)
        assert len(head_filings) > 0, f"Head filings returned empty for {ticker}"
        
        # Check that the most recent filing is newer than 2018
        most_recent_filing = head_filings[0]  # Filings are sorted by date desc
        most_recent_date = most_recent_filing.filing_date
        
        assert most_recent_date.year > 2018, (
            f"Most recent 10-K filing for {ticker} is from {most_recent_date.year}, "
            f"expected newer than 2018. Date: {most_recent_date}"
        )
        
        # Check that at least some filings in head are from recent years
        recent_filings = [f for f in head_filings if f.filing_date.year >= 2020]
        assert len(recent_filings) > 0, (
            f"No recent filings (2020+) found in head results for {ticker}"
        )
    
    @pytest.mark.parametrize("ticker", ["AAPL", "MSFT"])
    def test_xbrls_head_returns_recent_periods(self, ticker):
        """Test that XBRLS created from head filings has recent periods."""
        company = Company(ticker)
        
        # Get XBRL 10-K filings
        tenk_filings = company.get_filings(form='10-K', is_xbrl=True)
        
        # Skip if no XBRL filings available
        if len(tenk_filings) == 0:
            pytest.skip(f"No XBRL 10-K filings found for {ticker}")
        
        # Get head filings and create XBRLS
        head_filings = tenk_filings.head(3)  # Use fewer filings for performance
        xbrls = XBRLS.from_filings(head_filings)
        
        # Get periods from XBRLS
        periods = xbrls.get_periods()
        assert len(periods) > 0, f"No periods found in XBRLS for {ticker}"
        
        # Extract years from periods
        period_years = []
        for period in periods:
            if period.get('date'):
                year = int(period['date'][:4])
                period_years.append(year)
            elif period.get('end_date'):
                year = int(period['end_date'][:4])
                period_years.append(year)
        
        # Check that we have recent period data
        assert len(period_years) > 0, f"No period years extracted for {ticker}"
        max_year = max(period_years)
        assert max_year > 2018, (
            f"Latest period year for {ticker} XBRLS is {max_year}, "
            f"expected newer than 2018"
        )
        
        # Check that we have some periods from recent years
        recent_years = [y for y in period_years if y >= 2020]
        assert len(recent_years) > 0, (
            f"No recent periods (2020+) found in XBRLS for {ticker}"
        )
    
    def test_data_freshness_threshold(self):
        """Test that major companies have very recent data (within 2 years)."""
        current_year = date.today().year
        min_expected_year = current_year - 2  # Allow 2-year lag for annual filings
        
        company = Company("AAPL")
        tenk_filings = company.get_filings(form='10-K')
        
        assert len(tenk_filings) > 0, "No 10-K filings found for AAPL"
        
        most_recent = tenk_filings[0]
        most_recent_year = most_recent.filing_date.year
        
        assert most_recent_year >= min_expected_year, (
            f"Most recent AAPL 10-K is from {most_recent_year}, "
            f"expected at least {min_expected_year} (within 2 years of {current_year})"
        )
    
    def test_head_preserves_chronological_order(self):
        """Test that .head() preserves chronological order (newest first)."""
        company = Company("AAPL")
        tenk_filings = company.get_filings(form='10-K')
        
        head_filings = tenk_filings.head(5)
        assert len(head_filings) >= 2, "Need at least 2 filings to test ordering"
        
        # Verify that filings are in descending date order
        for i in range(len(head_filings) - 1):
            current_date = head_filings[i].filing_date
            next_date = head_filings[i + 1].filing_date
            
            assert current_date >= next_date, (
                f"Filings not in descending date order: "
                f"{current_date} should be >= {next_date}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])