"""
Regression test for Issue #416: Product and service values not appearing

This test ensures that segment member dimensional data is properly extracted
and displayed in income statements when ProductOrServiceAxis dimensions are present.

GitHub Issue: https://github.com/dgunning/edgartools/issues/416
"""

import pytest
from edgar import *


def test_msft_segment_member_values():
    """Test that Microsoft's product and service segment values appear in income statement"""
    
    # Get Microsoft filing from issue #416
    filing = Company('MSFT').get_filings().filter(accession_number="0000950170-25-100235").latest()
    
    # Extract income statement
    financials = Financials.extract(filing)
    income_statement = financials.income_statement()
    df = income_statement.to_dataframe()
    
    # Verify dimensional display is enabled
    # The dataframe should have more than the basic 21 rows due to dimensional breakdowns
    assert df.shape[0] > 40, f"Expected more than 40 rows due to dimensional data, got {df.shape[0]}"
    
    # Verify dimensional rows exist
    dimensional_rows = df[df['dimension'] == True]
    assert len(dimensional_rows) > 25, f"Expected dimensional rows, found {len(dimensional_rows)}"
    
    # Verify segment member concepts exist (these are the member definitions)
    segment_concepts = ['us-gaap_ProductMember', 'us-gaap_ServiceOtherMember']
    found_concepts = df[df['concept'].isin(segment_concepts)]
    assert len(found_concepts) == 2, f"Expected 2 segment member concepts, found {len(found_concepts)}"
    
    # Verify dimensional revenue facts exist with actual values
    revenue_rows = df[
        (df['concept'] == 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax') & 
        (df['dimension'] == True)
    ]
    assert len(revenue_rows) > 15, f"Expected multiple dimensional revenue rows, found {len(revenue_rows)}"
    
    # Find service revenue dimensional fact
    service_revenue_rows = revenue_rows[revenue_rows['label'].str.contains('Service', case=False, na=False)]
    assert len(service_revenue_rows) > 0, "Expected to find service revenue dimensional facts"
    
    # Find the "Service and Other" row which has the largest service revenue
    service_and_other = revenue_rows[revenue_rows['label'] == 'Service and Other']
    assert len(service_and_other) > 0, "Expected to find 'Service and Other' dimensional fact"
    
    # Verify service revenue has actual values (not empty/NaN)
    service_row = service_and_other.iloc[0]
    value_2025 = service_row['2025-06-30']
    assert value_2025 != '' and value_2025 is not None, f"Service revenue should have actual value, got: {value_2025}"
    
    # The "Service and Other" value should be a large number (>$100B for Microsoft)
    assert isinstance(value_2025, (int, float)) and value_2025 > 100_000_000_000, \
        f"Service and Other revenue should be >$100B, got: {value_2025}"


def test_dimension_display_detection():
    """Test that the dimension display detection logic works correctly"""
    
    # Get Microsoft filing
    filing = Company('MSFT').get_filings().filter(accession_number="0000950170-25-100235").latest()
    xbrl = filing.xbrl()
    
    # Test that income statements with ProductOrServiceAxis dimensions enable dimensional display
    should_display = xbrl._is_dimension_display_statement('IncomeStatement', '')
    assert should_display, "Income statements with ProductOrServiceAxis should enable dimensional display"
    
    # Test that other statement types without specific keywords don't enable dimensional display
    should_display_bs = xbrl._is_dimension_display_statement('BalanceSheet', '')
    assert not should_display_bs, "Balance sheets should not enable dimensional display by default"


def test_dimensional_revenue_breakdown():
    """Test that dimensional revenue breakdown includes expected segments"""
    
    # Get Microsoft filing
    filing = Company('MSFT').get_filings().filter(accession_number="0000950170-25-100235").latest()
    financials = Financials.extract(filing)
    income_statement = financials.income_statement()
    df = income_statement.to_dataframe()
    
    # Get all dimensional revenue rows
    revenue_rows = df[
        (df['concept'] == 'us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax') & 
        (df['dimension'] == True)
    ]
    
    # Should include various Microsoft business segments
    revenue_labels = revenue_rows['label'].tolist()
    
    # Check for expected Microsoft segment types (some examples)
    expected_segments = ['Service', 'Product']  # Basic categories that should exist
    
    found_segments = []
    for segment in expected_segments:
        matching_labels = [label for label in revenue_labels if segment in label]
        if matching_labels:
            found_segments.append(segment)
    
    assert len(found_segments) >= 1, f"Expected to find basic segment types, found: {found_segments}"
    
    # Verify all revenue rows have non-zero values for recent period
    for _, row in revenue_rows.iterrows():
        value = row['2025-06-30']
        assert isinstance(value, (int, float)) and value > 0, \
            f"Revenue segment '{row['label']}' should have positive value, got: {value}"


if __name__ == "__main__":
    # Run tests directly
    test_msft_segment_member_values()
    test_dimension_display_detection()
    test_dimensional_revenue_breakdown()
    print("All regression tests passed!")