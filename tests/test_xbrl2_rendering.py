"""
Tests for XBRL2 rendering functionality.
"""

from edgar.xbrl2.rendering import render_statement


def test_render_statement_with_shares():
    """Test rendering a statement with share values."""
    # Create minimal test data with share and monetary values
    statement_data = [
        {
            'label': 'Total Assets',
            'level': 0,
            'is_abstract': False,
            'is_total': True,
            'concept': 'us-gaap_Assets',
            'has_values': True,
            'values': {'instant_2023-12-31': 1000000000},
            'decimals': {'instant_2023-12-31': -6}  # In millions
        },
        {
            'label': 'Common Stock Shares Outstanding',
            'level': 1,
            'is_abstract': False,
            'is_total': False,
            'concept': 'us-gaap_CommonStockSharesOutstanding',
            'has_values': True,
            'values': {'instant_2023-12-31': 5123456000},
            'decimals': {'instant_2023-12-31': -3}  # In thousands
        },
        {
            'label': 'Earnings Per Share, Basic',
            'level': 1,
            'is_abstract': False,
            'is_total': False,
            'concept': 'us-gaap_EarningsPerShareBasic',
            'has_values': True,
            'values': {'instant_2023-12-31': 1.25},
            'decimals': {'instant_2023-12-31': 2}  # 2 decimal places
        }
    ]
    
    periods_to_display = [('instant_2023-12-31', 'Dec 31, 2023')]
    
    # Render the statement
    table = render_statement(
        statement_data,
        periods_to_display,
        'Test Statement',
        'BalanceSheet'
    )
    
    # Basic check that the table was created
    assert table is not None
    
    # The title should include the scale note (In millions, except shares in thousands)
    assert "millions" in table.title
    assert "shares" in table.title
    assert "thousands" in table.title