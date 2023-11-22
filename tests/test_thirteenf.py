
from pathlib import Path
from decimal import Decimal
import pytest
from edgar import *


def test_parse_infotable():
    infotable = ThirteenF.parse_infotable_xml(Path("data/13F-HR.infotable.xml").read_text())
    assert len(infotable) == 255


MetLife13F: Filing = Filing(form='13F-HR',
                               filing_date='2023-03-23',
                               company='METLIFE INC', cik=1099219,
                               accession_no='0001140361-23-013281')


def test_thirteenf_from_filing_with_multiple_related_filing_on_same_day():
    filing:Filing = MetLife13F

    thirteenF:ThirteenF = ThirteenF(filing)
    assert thirteenF

    # We expect that the holding report will be on the filing with the latest period of report
    assert thirteenF.filing.accession_no == '0001140361-23-013285'
    assert thirteenF.has_infotable()
    assert len(thirteenF.infotable) == 6

    # assert thirteenf.infotable.iloc[0].name_of_issuer == "METLIFE INC"

    print()
    print(thirteenF)
    assert thirteenF.total_holdings == 6
    assert thirteenF.total_value == Decimal('9229022')

    assert thirteenF.primary_form_information.signature.name == 'Steven Goulart'
    assert thirteenF.signer == 'Steven Goulart'

    # Call data object
    assert isinstance(filing.obj(), ThirteenF)

    # 13F-NT
    filing = Filing(form='13F-NT', filing_date='2023-03-17', company='Jasopt Investments Bahamas Ltd', cik=1968770,
                    accession_no='0000950123-23-002952')
    thirteenF = ThirteenF(filing)
    assert not thirteenF.has_infotable()
    assert not thirteenF.infotable_xml
    assert not thirteenF.infotable_html
    assert not thirteenF.infotable

    print(thirteenF)

    # Should throw an AssertionError if you try to parse a 10-K as a 13F
    filing = Filing(form='10-K', filing_date='2023-03-23', company='ADMA BIOLOGICS, INC.', cik=1368514,
                    accession_no='0001140361-23-013467')
    with pytest.raises(AssertionError):
        ThirteenF(filing)


def test_thirteenf_multiple_related_filings_dont_use_latest_period_of_report():
    """
    By default a thirteenf uses the filing with the latest period of report. This is a test of setting this false
    :return:
    """
    filing = MetLife13F

    # Don't use latest period of report. We shoul then get the first filing
    thirteenF = ThirteenF(filing, use_latest_period_of_report=False)
    assert thirteenF.filing.accession_no == MetLife13F.accession_no
    assert thirteenF.has_infotable()
    assert len(thirteenF.infotable) == 6
    assert thirteenF.report_period == '2021-12-31'
    assert thirteenF.filing.header.period_of_report == '20211231'
    # The filing is whatever was passed in
    assert thirteenF.filing.accession_no == '0001140361-23-013281' == thirteenF.accession_number

    # Test the report periods
    related_filings = filing.related_filings()
    first_period = related_filings[0].header.period_of_report
    last_period = related_filings[-1].header.period_of_report
    assert first_period == '20171231'
    assert last_period =='20230930'


def test_thirteenf_holdings():
    print()
    thirteenF = ThirteenF(MetLife13F)
    assert thirteenF.total_holdings == 6
    assert thirteenF.total_value == Decimal('9229022')
    assert thirteenF.primary_form_information.signature.name == 'Steven Goulart'


def test_create_thirteenf_from_thirteenf_NT():
    # 13F-NT
    filing = Filing(form='13F-NT', filing_date='2023-03-17', company='Jasopt Investments Bahamas Ltd', cik=1968770,
                    accession_no='0000950123-23-002952')
    thirteenF = ThirteenF(filing)
    assert not thirteenF.has_infotable()
    assert not thirteenF.infotable_xml
    assert not thirteenF.infotable_html
    assert not thirteenF.infotable

    print(thirteenF)

    # Should throw an AssertionError if you try to parse a 10-K as a 13F
    filing = Filing(form='10-K', filing_date='2023-03-23', company='ADMA BIOLOGICS, INC.', cik=1368514,
                    accession_no='0001140361-23-013467')
    with pytest.raises(AssertionError):
        ThirteenF(filing)


def test_previous_holding_report():
    thirteenF = ThirteenF(MetLife13F)
    print()
    print(thirteenF)
    print(thirteenF._related_filings)
    assert thirteenF.accession_number == '0001140361-23-013285'
    previous_holding_report = thirteenF.previous_holding_report()
    assert previous_holding_report.accession_number == '0001140361-23-013284'
    # Get the previous to the previous
    assert previous_holding_report.previous_holding_report().accession_number == '0001140361-23-013283'

    # This filing has no previous holding report on the same filing day
    filing = Filing(form='13F-HR', filing_date='2022-12-01', company='Garde Capital, Inc.', cik=1616328,
                    accession_no='0001616328-22-000004')
    thirteenf = ThirteenF(filing)
    assert len(thirteenf._related_filings) == 1
    assert thirteenf.previous_holding_report() is None


def test_parse_thirteenf_primary_xml():
    res = ThirteenF.parse_primary_document_xml(Path("data/metlife.13F-HR.primarydoc.xml").read_text())
    print(res)


def test_thirteenf_with_issues():
    thirteenF_filings = get_filings(form="13F-HR")
    # filing = thirteenF_filings[10]
    filing = Filing(form='13F-HR', filing_date='2023-11-15', company='American Trust', cik=1905128,
                    accession_no='0001905128-23-000004')
    # filing.homepage.open()
    print(str(filing))
    thirteenF = filing.obj()
    print(thirteenF)
