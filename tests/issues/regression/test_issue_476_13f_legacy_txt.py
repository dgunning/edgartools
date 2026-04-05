"""
Regression test for GitHub issue #476: Improve 13F-HR TXT parser for pre-2013 filings

GitHub Issue: https://github.com/dgunning/edgartools/issues/476
Description: Pre-2013 13F filings use spaced CUSIPs (e.g., "025816 10 9") and multi-line
             company names. The old regex-based parser incorrectly matched class prefixes
             (e.g., "Com") concatenated with CUSIP digits as valid CUSIPs.
             The fix uses column positions from <S>/<C> marker lines for field extraction.

Test case: 2009 Q4 Berkshire Hathaway 13F-HR (accession: 0000950123-10-013409)
"""

import pytest
from edgar.thirteenf import ThirteenF


@pytest.mark.fast
def test_issue_476_spaced_cusip_extraction():
    """
    Test that spaced CUSIPs (e.g., "025816 10 9") are correctly extracted
    using column positions from the <S>/<C> marker line.
    """
    test_txt = """
Form 13F Information Table

<TABLE>
<CAPTION>
                                        Column 4     Column 5
                Column 2   Column 3      Market      Shares or
Column 1        Title of    CUSIP         Value      Principal  (a)      Column 7           (a)       (b)    (c)
Name of Issuer    Class     Number   (In Thousands)   Amount $  Sole     Other Managers      Sole    Shared   None
- --------------  -------- ----------- -------------- ----------- ---- -------------------- ----------- ------ -------
<S>             <C>      <C>         <C>            <C>         <C>  <C>                  <C>         <C>    <C>
American
   Express Co.    Com    025816 10 9       697,973   17,225,400         X            4, 2, 5, 17           17,225,400
                                           323,943    7,994,634         X            4, 13, 17              7,994,634
Johnson &
   Johnson        Com    478160 10 4       320,324    4,973,200         X            4                      4,973,200
Coca Cola         Com    191216 10 0        22,800      400,000         X            4, 17                    400,000
Comcast Corp    CLA SPL  20030N 20 0       192,120   12,000,000         X            4, 9, 10, 11, 14, 17  12,000,000
</TABLE>
"""

    infotable = ThirteenF.parse_infotable_txt(test_txt)

    assert len(infotable) == 5, f"Should parse 5 holdings (2 AmEx + 1 J&J + 1 Coca Cola + 1 Comcast), got {len(infotable)}"

    # Verify spaced CUSIPs are correctly cleaned
    cusips = set(infotable['Cusip'].tolist())
    assert '025816109' in cusips, "AmEx CUSIP should be 025816109, not Com025816 or similar"
    assert '478160104' in cusips, "J&J CUSIP should be 478160104"
    assert '191216100' in cusips, "Coca-Cola CUSIP should be 191216100"
    assert '20030N200' in cusips, "Comcast CUSIP should be 20030N200"

    # Verify no CUSIPs start with class prefixes (the old bug)
    for cusip in infotable['Cusip'].tolist():
        assert not cusip.startswith('Com'), f"CUSIP should not start with 'Com': {cusip}"

    # Verify multi-line company names
    amex = infotable[infotable['Cusip'] == '025816109']
    assert len(amex) == 2, "AmEx should have 2 rows (2 manager assignments)"
    assert 'Express' in amex.iloc[0]['Issuer'], "AmEx name should include 'Express'"

    jj = infotable[infotable['Cusip'] == '478160104']
    assert 'Johnson' in jj.iloc[0]['Issuer'], "J&J name should include 'Johnson'"

    # Verify Comcast with CLA SPL class
    comcast = infotable[infotable['Cusip'] == '20030N200']
    assert comcast.iloc[0]['Class'] == 'CLA SPL', f"Comcast class should be 'CLA SPL', got {comcast.iloc[0]['Class']}"

    # Verify continuation rows have correct values
    amex_first = amex.iloc[0]
    assert amex_first['Value'] == 697973, f"AmEx first row value should be 697973, got {amex_first['Value']}"
    assert amex_first['SharesPrnAmount'] == 17225400, f"AmEx shares should be 17225400, got {amex_first['SharesPrnAmount']}"


@pytest.mark.fast
def test_issue_476_multi_table_no_managers():
    """
    Test that filings with multiple holdings tables but no managers table
    process all tables (don't skip the first one).
    """
    test_txt = """
Form 13F Information Table

<TABLE>
<CAPTION>
Column 1        Column 2   Column 3      Column 4       Column 5
Name of Issuer  Title of    CUSIP         Value          Shares       Disc     Managers        Sole    Shared   None
                  Class     Number   (In Thousands)      Amount
- ------------- -------- ----------- -------------- ------------ ---- ---- -------------------- ----------- ------ -------
<S>             <C>      <C>         <C>            <C>          <C>  <C>  <C>                  <C>         <C>    <C>
Company A         Com    111111111       100,000    1,000,000         X    4                      1,000,000
                                       -----------
                                        100,000
                                       -----------
</TABLE>

<TABLE>
<CAPTION>
Column 1        Column 2   Column 3      Column 4       Column 5
Name of Issuer  Title of    CUSIP         Value          Shares       Disc     Managers        Sole    Shared   None
                  Class     Number   (In Thousands)      Amount
- ------------- -------- ----------- -------------- ------------ ---- ---- -------------------- ----------- ------ -------
<S>             <C>      <C>         <C>            <C>          <C>  <C>  <C>                  <C>         <C>    <C>
Company B         Com    222222222       200,000    2,000,000         X    4                      2,000,000
                                       -----------
                                        200,000
                                       -----------
</TABLE>
"""

    infotable = ThirteenF.parse_infotable_txt(test_txt)

    assert len(infotable) == 2, f"Should parse holdings from both tables, got {len(infotable)}"
    cusips = set(infotable['Cusip'].tolist())
    assert '111111111' in cusips, "Should find Company A from first table"
    assert '222222222' in cusips, "Should find Company B from second table"


@pytest.mark.fast
def test_issue_476_continuation_rows():
    """
    Test that continuation rows (same CUSIP, different manager assignments)
    are correctly associated with the current company.
    """
    test_txt = """
Form 13F Information Table

<TABLE>
<CAPTION>
Column 1        Column 2   Column 3      Column 4       Column 5
Name of Issuer  Title of    CUSIP         Value          Shares       Disc     Managers        Sole    Shared   None
                  Class     Number   (In Thousands)      Amount
- ------------- -------- ----------- -------------- ------------ ---- ---- -------------------- ----------- ------ -------
<S>             <C>      <C>         <C>            <C>          <C>  <C>  <C>                  <C>         <C>    <C>
Wells Fargo &
   Co. Del        Com    949746 10 1     1,443,679   53,489,420         X    4, 2, 5, 17        53,489,420
                                           341,240   12,643,200         X    4, 3, 17           12,643,200
                                         1,034,069   38,313,040         X    4, 13, 17          38,313,040
Next Company      Com    111111111        50,000     1,000,000         X    4                    1,000,000
</TABLE>
"""

    infotable = ThirteenF.parse_infotable_txt(test_txt)

    wf = infotable[infotable['Cusip'] == '949746101']
    assert len(wf) == 3, f"Wells Fargo should have 3 rows, got {len(wf)}"
    for _, row in wf.iterrows():
        assert 'Wells Fargo' in row['Issuer'], f"All WF rows should have Wells Fargo name, got {row['Issuer']}"
        assert row['Cusip'] == '949746101', f"All WF rows should have CUSIP 949746101"

    nc = infotable[infotable['Cusip'] == '111111111']
    assert len(nc) == 1, "Next Company should have 1 row"


@pytest.mark.network
@pytest.mark.slow
def test_issue_476_brk_2009q4_full_parsing():
    """
    Test full parsing of BRK 2009 Q4 13F-HR filing with spaced CUSIPs.

    This filing has 109 holdings across 3 paginated tables, all with
    spaced CUSIPs in the format "XXXXXX YY Z".
    """
    from edgar import set_identity, Filing
    set_identity("Test test@test.com")

    f = Filing(
        form='13F-HR',
        filing_date='2010-02-16',
        company='BERKSHIRE HATHAWAY INC',
        cik=1067983,
        accession_no='0000950123-10-013409',
    )

    thirteenf = f.obj()
    assert isinstance(thirteenf, ThirteenF)

    infotable = thirteenf.infotable
    assert infotable is not None
    assert len(infotable) == 109, f"Should parse 109 holdings (matches filing summary), got {len(infotable)}"

    # Verify specific CUSIPs are correct (not mangled by class prefix)
    assert len(infotable[infotable['Cusip'] == '025816109']) == 7, "AmEx should have 7 manager rows"
    assert len(infotable[infotable['Cusip'] == '478160104']) == 7, "J&J should have 7 manager rows"
    assert len(infotable[infotable['Cusip'] == '191216100']) == 8, "Coca-Cola should have 8 manager rows"
    assert len(infotable[infotable['Cusip'] == '949746101']) == 14, "Wells Fargo should have 14 manager rows"

    # Verify multi-line company names
    brn = infotable[infotable['Cusip'] == '12189T104']
    assert 'Burlington' in brn.iloc[0]['Issuer'] and 'Santa Fe' in brn.iloc[0]['Issuer']

    # Verify total value matches filing summary ($57,929,532 thousands)
    total_value_thousands = infotable['Value'].sum() / 1000  # Value already multiplied by 1000
    assert abs(total_value_thousands - 57929532) < 100, f"Total value should be ~$57.9B, got {total_value_thousands:,.0f}"
