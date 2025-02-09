import pytest
from edgar.files.html import TableProcessor

@pytest.fixture
def pattern():
    return TableProcessor._get_period_header_pattern()

def test_standard_period_headers(pattern):
    valid_headers = [
            "Three Months Ended June 30, 2023",
            "nine months ended September 30, 2023",
            "3 months ended Mar. 31, 2023",
            "first quarter ended March 31, 2023",
            "fourth quarter ended December 31, 2023",
            "twelve months ended Dec 31, 2023"
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None

def test_fiscal_period_headers(pattern):
    valid_headers = [
            "fiscal quarter ended",
            "fiscal year ended",
            "Fiscal Quarter Ended June 30, 2023",
            "Fiscal Year Ended December 31, 2023"
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None

def test_balance_sheet_headers( pattern):
    valid_headers = [
            "as of December 31, 2023",
            "As At June 30, 2023",
            "at March 31, 2023",
            "as at September 30, 2023"
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None

def test_multiple_date_sequences(pattern):
    valid_headers = [
        "December 31, 2023 and December 31, 2022",
            "June 30, 2023, March 31, 2023 and December 31, 2022",
            "Sep. 30, 2023 and Sep. 30, 2022"
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None

def test_abbreviated_months( pattern):
    valid_headers = [
            "three months ended Jan 31, 2023",
            "six months ended Jun. 30, 2023",
            "nine months ended Sep 30, 2023",
            "as of Dec. 31, 2023"
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None

def test_period_variants(pattern):
    valid_headers = [
            "three months ending June 30, 2023",
            "quarter end June 30, 2023",
            "three month period June 30, 2023",
            "year ended December 31, 2023"
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None

def test_invalid_headers(pattern):
    invalid_headers = [
            "Invalid Date",
            #"13 months ended December 31, 2023",  # Invalid month count
            "Quarter",  # Too vague
            "as of Tomorrow",  # Invalid date format
            "Year 2023",  # Missing required components
            "31 December 2023"  # Invalid date format (European style)
        ]
    for header in invalid_headers:
        assert pattern.search(header) is None

def test_case_insensitivity(pattern):
    valid_headers = [
            "THREE MONTHS ENDED JUNE 30, 2023",
            "As Of December 31, 2023",
            "Fiscal Quarter Ended",
            "three MONTHS ended DECEMBER 31, 2023"
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None

def test_optional_components(pattern):
    valid_headers = [
            "December 31, 2023",  # Just the date
            "ended December 31, 2023",  # With ended but no period
            "quarter ended",  # No date
            #"three months ended"  # No date
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None

def test_whitespace_variations(pattern):
    valid_headers = [
            "three    months    ended June 30, 2023",
            "as   of   December 31, 2023",
            "quarter  ended  December  31,  2023",
            "December  31,   2023"
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None

def test_real_world_sec_examples(pattern):
    """Test with real examples from SEC filings"""
    valid_headers = [
            "Three and Nine Months Ended September 30, 2023",
            "Years Ended December 31, 2023 and 2022",
            "Three Months Ended March 31, 2023 and 2022",
            "Fiscal Years Ended June 30, 2023, 2022 and 2021",
            "As of and for the Year Ended December 31, 2023"
        ]
    for header in valid_headers:
        assert pattern.search(header) is not None