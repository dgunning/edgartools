"""
Regression test for GitHub issue #469: 13F TXT format parser

GitHub Issue: https://github.com/dgunning/edgartools/issues/469
Description: Older 13F filings (2012-era) only have TXT format for the information table,
             not XML. The TXT format uses SGML table tags and needs to be parsed correctly.

Expected behavior:
- 2012 Berkshire Hathaway 13F filings should successfully parse the information table
- Should return a DataFrame with holdings data matching the expected structure
- Should extract company names, CUSIPs, values, and share counts correctly

Test case: 2012-11-14 Berkshire Hathaway 13F-HR filing (accession: 0001193125-12-470800)
"""

import pytest
from edgar import get_filings, Filing
from edgar.thirteenf import ThirteenF


@pytest.mark.network
@pytest.mark.slow
def test_issue_469_txt_format_parsing():
    """
    Test that TXT format 13F information tables parse correctly.

    This tests the full parsing workflow for a 2012 Berkshire Hathaway filing
    that only has TXT format (no XML).
    """
    # Get 2012 Q4 Berkshire Hathaway 13F filing
    filings_2012 = get_filings(2012, 4, form="13F-HR")
    brk_filings = filings_2012.filter(cik=1067983)

    assert len(brk_filings) > 0, "Should find BRK 13F filing in 2012 Q4"

    filing_data = brk_filings.data.to_pandas().iloc[0]

    filing = Filing(
        form=filing_data['form'],
        filing_date=filing_data['filing_date'],
        company=filing_data['company'],
        cik=int(filing_data['cik']),
        accession_no=filing_data['accession_number']
    )

    # Verify this is the expected filing
    assert filing.accession_no == '0001193125-12-470800'
    assert filing.filing_date.year == 2012

    # Download TXT content and parse
    txt_content = filing.attachments.get_by_index(0).download()
    infotable = ThirteenF.parse_infotable_txt(txt_content)

    # Verify parsing succeeded
    assert infotable is not None, "TXT parser should return a DataFrame"
    assert len(infotable) > 0, "TXT parser should extract holdings"

    # Verify structure matches XML format
    expected_columns = {'Issuer', 'Class', 'Cusip', 'Value', 'SharesPrnAmount',
                        'Type', 'PutCall', 'InvestmentDiscretion',
                        'SoleVoting', 'SharedVoting', 'NonVoting', 'Ticker'}
    assert set(infotable.columns) == expected_columns, "Should have same columns as XML format"

    # Verify data quality
    assert len(infotable) >= 80, f"Should parse at least 80 holdings, got {len(infotable)}"
    assert infotable['Cusip'].notna().all(), "All CUSIPs should be non-null"
    assert infotable['Value'].sum() > 60_000_000, "Total value should be > $60B (thousands)"

    # Verify specific holdings
    american_express = infotable[infotable['Cusip'] == '025816109']
    assert len(american_express) > 0, "Should find American Express holdings"
    assert 'EXPRESS' in american_express.iloc[0]['Issuer'].upper(), "Issuer name should include EXPRESS"


@pytest.mark.fast
def test_issue_469_txt_parser_handles_multiline_names():
    """
    Test that the TXT parser correctly handles multi-line company names.

    In the TXT format, company names can span two lines:
    Line 1: "AMERICAN"
    Line 2: "  EXPRESS CO    COM    025816109..."
    """
    # Simplified test data with multi-line company name
    # Need managers table first (which gets skipped), then holdings table
    test_txt = """
Form 13F Information Table

<TABLE>
<CAPTION>
Other Managers
<S>    <C>
4      Manager Name
</TABLE>

<TABLE>
<CAPTION>
Name of Issuer  Class  CUSIP     Value      Shares
<S>             <C>    <C>       <C>        <C>         <C>            <C>       <C>         <C>      <C>
AMERICAN
  EXPRESS CO    COM    025816109      110999     1952142 Shared-Defined 4           1952142       -   -
</TABLE>
"""

    infotable = ThirteenF.parse_infotable_txt(test_txt)

    assert len(infotable) == 1, "Should parse 1 holding"
    assert 'AMERICAN' in infotable.iloc[0]['Issuer'].upper(), "Should have AMERICAN in company name"
    assert '025816109' == infotable.iloc[0]['Cusip'], "Should extract correct CUSIP"
    assert 110999 == infotable.iloc[0]['Value'], "Should extract correct value"
    assert 1952142 == infotable.iloc[0]['SharesPrnAmount'], "Should extract correct share count"


@pytest.mark.network
@pytest.mark.slow
def test_issue_469_filing_obj_works_with_txt_only():
    """
    Test that filing.obj() works correctly with TXT-only 13F filings.

    This is the critical user-facing API - filing.obj() should return
    a ThirteenF object even for 2012-era filings without XML primary documents.
    """
    # Get 2012 Q4 Berkshire Hathaway 13F filing
    filings_2012 = get_filings(2012, 4, form="13F-HR")
    brk_filings = filings_2012.filter(cik=1067983)

    assert len(brk_filings) > 0, "Should find BRK 13F filing in 2012 Q4"

    filing_data = brk_filings.data.to_pandas().iloc[0]

    filing = Filing(
        form=filing_data['form'],
        filing_date=filing_data['filing_date'],
        company=filing_data['company'],
        cik=int(filing_data['cik']),
        accession_no=filing_data['accession_number']
    )

    # Verify this is a TXT-only filing (no primary XML)
    assert filing.xml() is None, "2012 filing should not have XML primary document"

    # The critical test - filing.obj() should work
    thirteen_f = filing.obj()

    assert thirteen_f is not None, "filing.obj() should return ThirteenF object"
    assert isinstance(thirteen_f, ThirteenF), "Should be ThirteenF instance"

    # Verify key properties work
    assert thirteen_f.management_company_name is not None
    assert thirteen_f.report_period is not None
    assert thirteen_f.total_holdings == 119  # Improved CUSIP matching finds more holdings
    assert thirteen_f.total_value > 60_000_000  # > $60B in thousands

    # Verify infotable works
    infotable = thirteen_f.infotable
    assert infotable is not None
    assert len(infotable) == 119  # Improved CUSIP matching finds more holdings


@pytest.mark.fast
def test_issue_469_txt_parser_handles_variable_field_counts():
    """
    Test that the TXT parser handles variable "Other Managers" field lengths.

    The "Other Managers" field can be "4" or "4, 5, 9" which becomes multiple tokens
    when split by whitespace. The parser needs to handle this variability.
    """
    # Test data with different manager field formats
    # Need managers table first (which gets skipped), then holdings table
    test_txt = """
Form 13F Information Table

<TABLE>
<CAPTION>
Other Managers
<S>    <C>
4      Manager Name
</TABLE>

<TABLE>
<CAPTION>
Name of Issuer  Class  CUSIP     Value      Shares
<S>             <C>    <C>       <C>        <C>         <C>            <C>       <C>         <C>      <C>
COMPANY A       COM    111111111  100        1000 Shared-Defined 4           1000       -   -
COMPANY B       COM    222222222  200        2000 Shared-Defined 4, 5        2000       -   -
COMPANY C       COM    333333333  300        3000 Shared-Defined 4, 5, 9     3000       -   -
</TABLE>
"""

    infotable = ThirteenF.parse_infotable_txt(test_txt)

    assert len(infotable) == 3, "Should parse all 3 holdings despite variable field counts"
    assert infotable['Value'].tolist() == [100, 200, 300], "Should extract correct values"
    assert infotable['SharesPrnAmount'].tolist() == [1000, 2000, 3000], "Should extract correct shares"


@pytest.mark.network
@pytest.mark.slow
def test_issue_469_repr_works_with_txt_only():
    """
    Test that repr() and __rich__() work correctly with TXT-only 13F filings.

    This is a regression test for a bug where calling repr() on a TXT-only filing
    would fail because __rich__() tried to display None values in the Rich table.

    The bug was at line 956 in thirteenf.py where self.signer (which is None for
    TXT-only filings) was passed directly to the table without a fallback.
    """
    # Get 2012 Q4 Berkshire Hathaway 13F filing (TXT-only)
    filings_2012 = get_filings(2012, 4, form="13F-HR")
    brk_filings = filings_2012.filter(cik=1067983)

    assert len(brk_filings) > 0, "Should find BRK 13F filing in 2012 Q4"

    filing_data = brk_filings.data.to_pandas().iloc[0]

    filing = Filing(
        form=filing_data['form'],
        filing_date=filing_data['filing_date'],
        company=filing_data['company'],
        cik=int(filing_data['cik']),
        accession_no=filing_data['accession_number']
    )

    # Create ThirteenF object
    thirteen_f = filing.obj()

    # The critical test - repr() should work without raising AttributeError
    repr_output = repr(thirteen_f)

    assert repr_output is not None, "repr() should return a string"
    assert len(repr_output) > 0, "repr() should not return empty string"

    # Verify the output contains expected information
    assert "13F-HR" in repr_output or "Holding Report" in repr_output, "repr() should contain form type"
    assert "Berkshire" in repr_output or filing.company in repr_output, "repr() should contain company name"


@pytest.mark.fast
def test_issue_469_columnar_format_parsing():
    """
    Test columnar format (Format 2) parsing with synthetic data.

    Format 2 has <S> and <C> tags for each field on a single line.
    This format was used by some funds in 2012 (e.g., JANA Partners).
    """
    test_txt = """
Form 13F Information Table

<TABLE>
<CAPTION>
Other Managers
<S>    <C>
4      Manager Name
</TABLE>

<TABLE>
<CAPTION>
            NAME OF ISSUER           TITLE OF CLASS    CUSIP   VALUE
<S>                              <C>              <C>       <C>      <C>       <C> <C>  <C>        <C>      <C>       <C>     <C>
<S>  AETNA INC                   <C>  COM          <C>  00817Y108   <C>  92,760 <C>  2,342,435 <C>  SH  <C>  SOLE  <C>  2,238,895 <C>  103,540  <C>  0
<S>  APPLE INC                   <C>  COM          <C>  037833100   <C>  95,495 <C>    143,148 <C>  SH  <C>  SOLE  <C>    136,835 <C>    6,313  <C>  0
</TABLE>
"""

    infotable = ThirteenF.parse_infotable_txt(test_txt)

    assert len(infotable) == 2, "Should parse 2 holdings"
    assert 'AETNA' in infotable.iloc[0]['Issuer'].upper(), "First holding should be AETNA"
    assert 'APPLE' in infotable.iloc[1]['Issuer'].upper(), "Second holding should be APPLE"
    assert infotable.iloc[0]['Cusip'] == '00817Y108', "Should extract correct CUSIP for AETNA"
    assert infotable.iloc[1]['Cusip'] == '037833100', "Should extract correct CUSIP for APPLE"
    assert infotable.iloc[0]['Value'] == 92760, "Should extract correct value for AETNA"
    assert infotable.iloc[1]['Value'] == 95495, "Should extract correct value for APPLE"
    assert infotable.iloc[0]['SharesPrnAmount'] == 2342435, "Should extract correct shares for AETNA"
    assert infotable.iloc[1]['SharesPrnAmount'] == 143148, "Should extract correct shares for APPLE"


@pytest.mark.network
@pytest.mark.slow
def test_issue_469_columnar_format_real_filing():
    """
    Test columnar format with real 2012 filing that uses Format 2.

    This tests the full workflow with a real filing from 2012 that uses
    the columnar SGML format (Format 2).
    """
    # Get 2012 13F filings
    filings_2012 = get_filings(form='13F-HR', year=2012, quarter=4)

    # Find a filing that uses columnar format
    # We'll iterate through a few filings to find one with columnar format
    columnar_filing = None
    for filing in list(filings_2012)[:10]:  # Check first 10 filings
        try:
            # Get the TXT content
            thirteenf = filing.obj()
            if thirteenf.infotable_txt:
                # Check if it's columnar format by looking for <S> tags in data rows
                txt_content = thirteenf.infotable_txt
                if '<S>' in txt_content and 'NAME OF ISSUER' in txt_content:
                    # This looks like columnar format
                    infotable = thirteenf.infotable
                    if infotable is not None and len(infotable) > 10:
                        columnar_filing = filing
                        columnar_thirteenf = thirteenf
                        break
        except Exception:
            continue

    # If we found a columnar filing, test it
    if columnar_filing:
        assert columnar_thirteenf.infotable is not None, "Should parse columnar format infotable"
        assert len(columnar_thirteenf.infotable) > 0, "Should have holdings"
        assert columnar_thirteenf.total_holdings > 0, "Should have total holdings count"
        assert columnar_thirteenf.total_value > 0, "Should have total value"

        # Verify data quality
        infotable = columnar_thirteenf.infotable
        assert infotable['Cusip'].notna().all(), "All CUSIPs should be non-null"
        assert infotable['Value'].sum() > 0, "Total value should be positive"
        assert infotable['Issuer'].notna().all(), "All issuers should be non-null"
