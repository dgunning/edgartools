"""
Test current filings parsing, especially edge cases with company names containing dashes
"""
import pytest
from edgar.current_filings import parse_title


@pytest.mark.fast
def test_parse_title_simple():
    """Test parsing a simple title without dashes in company name"""
    title = "4 - WILKS LEWIS (0001076463) (Reporting)"
    form, company, cik, status = parse_title(title)

    assert form == "4"
    assert company == "WILKS LEWIS"
    assert cik == "0001076463"
    assert status == "Reporting"


@pytest.mark.fast
def test_parse_title_with_dash_in_company_name():
    """Test parsing title where company name contains a dash - this was the bug"""
    title = "D - Greenbird Intelligence Fund, LLC Series U - Shield Ai (0002093552) (Filer)"
    form, company, cik, status = parse_title(title)

    assert form == "D", f"Expected form 'D' but got '{form}'"
    assert company == "Greenbird Intelligence Fund, LLC Series U - Shield Ai", \
        f"Expected full company name but got '{company}'"
    assert cik == "0002093552"
    assert status == "Filer"


@pytest.mark.fast
def test_parse_title_schedule_form():
    """Test parsing a schedule form with subject status"""
    title = "SCHEDULE 13G/A - Lucent, Inc. (0001726079) (Subject)"
    form, company, cik, status = parse_title(title)

    assert form == "SCHEDULE 13G/A"
    assert company == "Lucent, Inc."
    assert cik == "0001726079"
    assert status == "Subject"


@pytest.mark.fast
def test_parse_title_multiple_dashes_in_company():
    """Test parsing title with multiple dashes in company name"""
    title = "10-K - ABC-DEF Corporation - GHI Division (0001234567) (Filer)"
    form, company, cik, status = parse_title(title)

    assert form == "10-K"
    assert company == "ABC-DEF Corporation - GHI Division"
    assert cik == "0001234567"
    assert status == "Filer"


@pytest.mark.fast
def test_parse_title_filed_by_status():
    """Test parsing with 'Filed by' status"""
    title = "D - Example Company, Inc. - Series A (0009876543) (Filed by)"
    form, company, cik, status = parse_title(title)

    assert form == "D"
    assert company == "Example Company, Inc. - Series A"
    assert cik == "0009876543"
    assert status == "Filed by"
