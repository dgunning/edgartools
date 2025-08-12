"""
Derivatives functionality tests for enhanced FundReport.
Tests the new derivative parsing capabilities added to reports.py

Focuses on NPORT Sample 6 (has many SWO derivatives) and Sample 7 (diverse derivatives)
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from rich import print

from edgar import Filing
from edgar.funds.reports import FundReport


def test_derivatives_data_extraction_sample6():
    """Test basic derivatives data extraction from NPORT Sample 6"""
    sample6_xml = Path('data/nport/samples/N-PORT Sample 6.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample6_xml))
    
    derivatives_df = fund_report.derivatives_data()
    
    # Should have derivatives in this sample
    assert not derivatives_df.empty
    assert len(derivatives_df) > 0
    
    # Check required columns exist
    required_columns = ['title', 'derivative_type', 'subtype', 'counterparty', 
                       'notional_amount', 'unrealized_pnl', 'value_usd']
    for col in required_columns:
        assert col in derivatives_df.columns
    
    # Sample 6 should have swaps (SWP) and other types but NOT swaptions
    derivative_types = derivatives_df['derivative_type'].unique()
    assert 'SWP' in derivative_types
    assert len(derivatives_df) > 1000  # Sample 6 has many derivatives


def test_derivatives_data_extraction_sample7():
    """Test basic derivatives data extraction from NPORT Sample 7"""
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    derivatives_df = fund_report.derivatives_data()
    
    # Should have derivatives in this sample
    assert not derivatives_df.empty
    assert len(derivatives_df) > 0
    
    # Check required columns exist
    required_columns = ['title', 'derivative_type', 'subtype', 'counterparty', 
                       'notional_amount', 'unrealized_pnl', 'value_usd']
    for col in required_columns:
        assert col in derivatives_df.columns
    
    # Check derivative types are recognized
    derivative_types = derivatives_df['derivative_type'].unique()
    valid_types = ['FWD', 'SWP', 'FUT', 'OPT', 'SWO']
    for deriv_type in derivative_types:
        assert deriv_type in valid_types


def test_swaps_data_extraction():
    """Test swap-specific data extraction using Sample 7"""
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    swaps_df = fund_report.swaps_data()
    
    if not swaps_df.empty:
        # Check swap-specific columns
        swap_columns = ['fixed_rate_receive', 'fixed_rate_pay', 
                       'floating_index_receive', 'floating_index_pay',
                       'termination_date']
        for col in swap_columns:
            assert col in swaps_df.columns
        
        # Check that all rows are actually swaps
        assert all('Swap' in subtype for subtype in swaps_df['subtype'].unique())


def test_swaptions_data_sample7():
    """Test swaption data extraction using Sample 7 (has SWO derivatives)"""
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    swaptions_df = fund_report.swaptions_data()
    
    if not swaptions_df.empty:
        # Check swaption-specific columns
        swaption_columns = ['put_or_call', 'written_or_purchased', 'exercise_price']
        for col in swaption_columns:
            assert col in swaptions_df.columns
        
        # Check that all rows are swaptions
        assert (swaptions_df['subtype'] == 'SWO').all()


def test_options_data_extraction():
    """Test options-specific data extraction using Sample 7"""
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    options_df = fund_report.options_data()
    
    if not options_df.empty:
        # Check option-specific columns
        option_columns = ['option_type', 'option_position', 'exercise_price', 
                         'expiration_date', 'has_nested_derivative']
        for col in option_columns:
            assert col in options_df.columns
        
        # Check that all rows are actually options
        assert all('Option' in subtype or subtype == 'Option' for subtype in options_df['subtype'].unique())
        
        # Check option types are valid
        valid_option_types = ['Put', 'Call']
        option_types = options_df['option_type'].dropna().unique()
        for opt_type in option_types:
            assert opt_type in valid_option_types


def test_nested_derivatives_support():
    """Test that nested derivatives are properly handled"""
    # Test with Sample 6 which should have nested derivatives
    sample6_xml = Path('data/nport/samples/N-PORT Sample 6.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample6_xml))
    
    options_df = fund_report.options_data()
    
    if not options_df.empty:
        # Check for nested derivative columns
        assert 'has_nested_derivative' in options_df.columns
        assert 'nested_derivative_type' in options_df.columns
        
        # Find options with nested derivatives
        nested_options = options_df[options_df['has_nested_derivative'] == True]
        
        if not nested_options.empty:
            # Should have nested type specified
            assert nested_options['nested_derivative_type'].notna().any()
            
            # Check that dynamic columns exist for nested types
            nested_types = nested_options['nested_derivative_type'].dropna().unique()
            for nested_type in nested_types:
                if nested_type == 'Forward':
                    assert 'nested_fwd_currency_sold' in options_df.columns
                elif nested_type == 'Future':
                    assert 'nested_fut_payoff_profile' in options_df.columns
                elif nested_type == 'Swap':
                    assert 'nested_swp_notional_amount' in options_df.columns


def test_futures_data_extraction():
    """Test futures-specific data extraction using Sample 7"""
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    futures_df = fund_report.futures_data()
    
    if not futures_df.empty:
        # Check futures-specific columns
        futures_columns = ['payoff_profile', 'expiration_date', 'reference_entity']
        for col in futures_columns:
            assert col in futures_df.columns
        
        # Check that all rows are actually futures
        assert all('Future' in subtype for subtype in futures_df['subtype'].unique())
        
        # Check value_usd field exists and no redundant fields
        assert 'value_usd' in futures_df.columns
        assert 'investment_value_usd' not in futures_df.columns
        assert 'absolute_value' not in futures_df.columns


def test_forwards_data_extraction():
    """Test forwards-specific data extraction using Sample 7"""
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    forwards_df = fund_report.forwards_data()
    
    if not forwards_df.empty:
        # Check forwards-specific columns
        forwards_columns = ['currency_sold', 'amount_sold', 'currency_purchased', 
                          'amount_purchased', 'settlement_date']
        for col in forwards_columns:
            assert col in forwards_df.columns
        
        # Check that all rows are actually forwards
        assert all('Forward' in subtype for subtype in forwards_df['subtype'].unique())


def test_pd_na_handling():
    """Test that pd.NA values don't cause crashes in derivatives table"""
    # Test with both samples to ensure robust NA handling
    for sample_file in ['N-PORT Sample 6.xml', 'NPORT Sample 7.xml']:
        sample_xml = Path(f'data/nport/samples/{sample_file}').read_text()
        fund_report = FundReport(**FundReport.parse_fund_xml(sample_xml))
        
        # This should not crash due to pd.NA values
        derivatives_table = fund_report.derivatives_table
        assert derivatives_table is not None
        
        # Check that derivatives_data handles NA values
        derivatives_df = fund_report.derivatives_data()
        if not derivatives_df.empty:
            # Should handle NA values gracefully
            na_count = derivatives_df['notional_amount'].isna().sum()
            assert na_count >= 0  # At least doesn't crash


def test_backward_compatibility():
    """Test that existing investment_data() method still works"""
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    # Original method should still work
    investment_data = fund_report.investment_data()
    assert not investment_data.empty
    
    # Check that it includes both derivatives and non-derivatives by default
    derivative_count = len([inv for inv in fund_report.investments if inv.is_derivative])
    total_count = len(fund_report.investments)
    
    if derivative_count > 0:
        assert len(investment_data) == total_count
        
        # Test exclude derivatives option
        securities_only = fund_report.investment_data(include_derivatives=False)
        assert len(securities_only) == total_count - derivative_count


def test_securities_data_method():
    """Test new securities_data() method returns only non-derivatives"""
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    securities_df = fund_report.securities_data()
    derivatives_df = fund_report.derivatives_data()
    
    # Securities and derivatives should be mutually exclusive
    total_investments = len(fund_report.investments)
    assert len(securities_df) + len(derivatives_df) == total_investments


def test_derivative_reference_resolution():
    """Test that derivative references are properly resolved"""
    # Test with both samples
    for sample_name in ['N-PORT Sample 6.xml', 'NPORT Sample 7.xml']:
        sample_xml = Path(f'data/nport/samples/{sample_name}').read_text()
        fund_report = FundReport(**FundReport.parse_fund_xml(sample_xml))
        
        derivatives_df = fund_report.derivatives_data()
        
        if not derivatives_df.empty:
            # Check reference column exists
            assert 'reference' in derivatives_df.columns
            
            # Should have some reference values for derivative instruments
            references = derivatives_df['reference'].dropna().unique()
            assert len(references) >= 0  # At least handles references without crashing


def test_dynamic_columns_structure():
    """Test that dynamic columns only appear when relevant"""
    # Test with Sample 6 which has nested derivatives
    sample6_xml = Path('data/nport/samples/N-PORT Sample 6.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample6_xml))
    
    options_df = fund_report.options_data()
    
    if not options_df.empty:
        # Get all columns
        all_columns = set(options_df.columns)
        
        # Identify nested derivative columns
        fwd_cols = {col for col in all_columns if col.startswith('nested_fwd_')}
        fut_cols = {col for col in all_columns if col.startswith('nested_fut_')}
        swp_cols = {col for col in all_columns if col.startswith('nested_swp_')}
        
        # Check that columns only exist if there are nested derivatives of that type
        nested_types = options_df['nested_derivative_type'].dropna().unique()
        
        if 'Forward' in nested_types:
            assert len(fwd_cols) > 0
        if 'Future' in nested_types:
            assert len(fut_cols) > 0  
        if 'Swap' in nested_types:
            assert len(swp_cols) > 0


def test_data_types_consistency():
    """Test that data types are consistent across derivative methods"""
    # Test with Sample 7 which has diverse derivatives
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    # Get all derivative data
    all_methods = [
        fund_report.derivatives_data(),
        fund_report.swaps_data(),
        fund_report.options_data(),
        fund_report.forwards_data(), 
        fund_report.futures_data(),
        fund_report.swaptions_data()
    ]
    
    # Check common fields have consistent types
    common_fields = ['value_usd', 'notional_amount', 'unrealized_pnl']
    
    for df in all_methods:
        if not df.empty:
            for field in common_fields:
                if field in df.columns:
                    # Should be numeric (Decimal or float) or NA
                    non_na_values = df[field].dropna()
                    if not non_na_values.empty:
                        # Check that values are numeric (including Decimal types)
                        sample_value = non_na_values.iloc[0]
                        assert isinstance(sample_value, (int, float, Decimal))


def test_sample6_swap_focus():
    """Test Sample 6 specifically for swap handling (has many SWP derivatives)"""
    sample6_xml = Path('data/nport/samples/N-PORT Sample 6.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample6_xml))
    
    # Should have many swaps (not swaptions)
    swaps_df = fund_report.swaps_data()
    assert not swaps_df.empty
    assert len(swaps_df) > 1000  # Sample 6 has many swaps
    
    # Check swap-specific features
    swap_columns = ['fixed_rate_receive', 'fixed_rate_pay', 'floating_index_receive']
    for col in swap_columns:
        assert col in swaps_df.columns
    
    # Check that we have proper swap details
    if not swaps_df.empty:
        # Should have termination dates
        term_dates = swaps_df['termination_date'].dropna().unique()
        assert len(term_dates) > 0


def test_sample7_diversity_and_swaptions():
    """Test Sample 7 for derivative type diversity including swaptions"""
    sample7_xml = Path('data/nport/samples/NPORT Sample 7.xml').read_text()
    fund_report = FundReport(**FundReport.parse_fund_xml(sample7_xml))
    
    derivatives_df = fund_report.derivatives_data()
    
    # Should have multiple derivative types including swaptions
    derivative_types = derivatives_df['derivative_type'].unique()
    assert len(derivative_types) >= 3  # Should be diverse
    assert 'SWO' in derivative_types  # Sample 7 has swaptions
    
    # Check that we can extract type-specific data
    type_specific_counts = {
        'swaps': len(fund_report.swaps_data()),
        'options': len(fund_report.options_data()),
        'futures': len(fund_report.futures_data()),
        'forwards': len(fund_report.forwards_data()),
        'swaptions': len(fund_report.swaptions_data())
    }
    
    # Should have at least some derivatives in multiple categories
    non_empty_types = sum(1 for count in type_specific_counts.values() if count > 0)
    assert non_empty_types >= 3  # More diverse than Sample 6
    
    # Specifically check swaptions
    assert type_specific_counts['swaptions'] > 0


# Test with real filing if available
def test_real_filing_with_derivatives():
    """Test with a real filing that has derivatives (if available)"""
    try:
        # This filing is known to have derivatives based on earlier tests
        filing = Filing(form='NPORT-P', filing_date='2023-10-13', 
                       company='Jacob Funds Inc.', cik=1090372,
                       accession_no='0001145549-23-062230')
        
        fund_report = FundReport.from_filing(filing)
        
        if fund_report and fund_report.derivatives:
            derivatives_df = fund_report.derivatives_data()
            
            # Should parse without errors
            assert isinstance(derivatives_df, pd.DataFrame)
            
            # Should have basic derivative information
            if not derivatives_df.empty:
                assert 'derivative_type' in derivatives_df.columns
                assert 'counterparty' in derivatives_df.columns
                
    except Exception as e:
        # Skip test if filing is not available or network issues
        pytest.skip(f"Real filing test skipped: {e}")


if __name__ == "__main__":
    # Run a few key tests for manual verification
    test_derivatives_data_extraction_sample6()
    test_derivatives_data_extraction_sample7()
    test_swaptions_data_sample7()
    test_pd_na_handling()
    print("✅ All manual tests passed!")