import pyarrow as pa
from datetime import date
import pytest
from edgar._filings import sort_filings_by_priority

def create_test_table():
    """Create a test table with known data"""
    test_data = {
        'form': ['10-K', '8-K', '10-Q', 'S-1', '10-K', '8-K', 'DEF 14A'],
        'company': ['Company A', 'Company B', 'Company C', 'Company D', 'Company E', 'Company F', 'Company G'],
        'cik': [1111111, 2222222, 3333333, 4444444, 5555555, 6666666, 7777777],
        'filing_date': [
            date(2024, 3, 15),  # Multiple filings on same date
            date(2024, 3, 15),
            date(2024, 3, 15),
            date(2024, 3, 14),
            date(2024, 3, 14),
            date(2024, 3, 13),
            date(2024, 3, 13)
        ],
        'accession_number': ['001', '002', '003', '004', '005', '006', '007']
    }
    return pa.Table.from_pydict(test_data)


def test_default_priority_sort():
    """Test sorting with default priority forms"""
    table = create_test_table()
    sorted_table = sort_filings_by_priority(table)
    result = sorted_table.to_pandas()

    # Check primary sort is by date (descending)
    assert list(result['filing_date']) == sorted(result['filing_date'], reverse=True)

    # Check ordering within March 15 (3 filings)
    march_15_filings = result[result['filing_date'] == date(2024, 3, 15)]
    assert list(march_15_filings['form']) == [ '10-Q', '10-K', '8-K']

    # Check ordering within March 14 (2 filings)
    march_14_filings = result[result['filing_date'] == date(2024, 3, 14)]
    assert list(march_14_filings['form']) == ['10-K', 'S-1']

    # Last filings should be lowest priority on earliest date
    assert result.iloc[-1]['filing_date'] == date(2024, 3, 13)
    assert result.iloc[-1]['form'] == 'DEF 14A'


def test_custom_priority_sort():
    """Test sorting with custom priority forms"""
    table = create_test_table()
    custom_priorities = ['S-1', 'DEF 14A', '10-K']
    sorted_table = sort_filings_by_priority(table, priority_forms=custom_priorities)
    result = sorted_table.to_pandas()

    # Check primary sort is still by date
    assert list(result['filing_date']) == sorted(result['filing_date'], reverse=True)

    # Check March 15 ordering with custom priorities
    march_15_filings = result[result['filing_date'] == date(2024, 3, 15)]
    assert march_15_filings.iloc[0]['form'] == '10-K'  # 10-K should be first
    assert march_15_filings.iloc[1]['form'] == '10-Q'  # 10-K third priority

    # Check that non-priority forms are after priority forms
    def get_priority(form):
        try:
            return custom_priorities.index(form)
        except ValueError:
            return len(custom_priorities)

    # For each date group, check forms are properly ordered by priority
    for date_val in result['filing_date'].unique():
        date_filings = result[result['filing_date'] == date_val]
        priorities = [get_priority(form) for form in date_filings['form']]
        assert priorities == sorted(priorities)  # Should be in priority order


def test_empty_priority_sort():
    """Test sorting with empty priority list"""
    table = create_test_table()
    sorted_table = sort_filings_by_priority(table, priority_forms=[])
    result = sorted_table.to_pandas()

    # Check primary sort is by date
    assert list(result['filing_date']) == sorted(result['filing_date'], reverse=True)

    # Within each date, forms should be alphabetical
    for date_val in result['filing_date'].unique():
        date_filings = result[result['filing_date'] == date_val]
        forms = list(date_filings['form'])
        assert forms == sorted(forms)


def test_sorting_edge_cases():
    """Test edge cases and corner conditions"""
    # Single form type
    single_form_data = {
        'form': ['10-K'] * 3,
        'company': ['A', 'B', 'C'],
        'cik': [1, 2, 3],
        'filing_date': [date(2024, 3, 15), date(2024, 3, 14), date(2024, 3, 13)],
        'accession_number': ['001', '002', '003']
    }
    table = pa.Table.from_pydict(single_form_data)
    result = sort_filings_by_priority(table)
    assert len(result) == 3
    assert list(result['filing_date'].to_pandas()) == sorted(result['filing_date'].to_pandas(), reverse=True)

    # All same date
    same_date_data = {
        'form': ['10-K', '8-K', 'S-1'],
        'company': ['A', 'B', 'C'],
        'cik': [1, 2, 3],
        'filing_date': [date(2024, 3, 15)] * 3,
        'accession_number': ['001', '002', '003']
    }
    table = pa.Table.from_pydict(same_date_data)
    result = sort_filings_by_priority(table).to_pandas()
    assert result.iloc[0]['form'] == '10-K'  # Highest priority should be first
    assert result.iloc[-1]['form'] == 'S-1'  #