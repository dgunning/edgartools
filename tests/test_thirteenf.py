from pathlib import Path
from decimal import Decimal
import pytest
from edgar import *


def test_parse_infotable():
    infotable = ThirteenF.parse_infotable_xml(Path("data/xml/13F-HR.infotable.xml").read_text())
    assert len(infotable) == 255


MetLife13F: Filing = Filing(form='13F-HR',
                            filing_date='2023-03-23',
                            company='METLIFE INC', cik=1099219,
                            accession_no='0001140361-23-013281')


def test_thirteenf_from_filing_with_multiple_related_filing_on_same_day():
    filing: Filing = MetLife13F

    thirteenF: ThirteenF = ThirteenF(filing)
    assert thirteenF

    # We expect that the holding report will be on the filing with the latest period of report
    assert thirteenF.filing.accession_no == '0001140361-23-013281'
    assert thirteenF.has_infotable()
    assert len(thirteenF.infotable) == 6

    # assert thirteenf.infotable.iloc[0].name_of_issuer == "METLIFE INC"

    print()
    print(thirteenF)
    assert thirteenF.total_holdings == 6
    assert thirteenF.total_value == Decimal('11019796')

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
    assert thirteenF.filing.header.period_of_report == '2021-12-31'
    # The filing is whatever was passed in
    assert thirteenF.filing.accession_no == '0001140361-23-013281' == thirteenF.accession_number

    # Test the report periods
    related_filings = filing.related_filings()
    first_period = related_filings[0].header.period_of_report
    last_period = related_filings[-1].header.period_of_report
    assert first_period == '2017-12-31'
    assert last_period >= '2023-09-30'


def test_thirteenf_holdings():
    print()
    thirteenF = ThirteenF(MetLife13F)
    assert thirteenF.total_holdings == 6
    assert thirteenF.total_value == Decimal('11019796')
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
    assert thirteenF.accession_number == '0001140361-23-013281'
    previous_holding_report = thirteenF.previous_holding_report()
    assert previous_holding_report.accession_number == '0001140361-23-013280'
    # Get the previous to the previous
    assert previous_holding_report.previous_holding_report().accession_number == '0001140361-23-013279'

    # This filing has no previous holding report on the same filing day
    filing = Filing(form='13F-HR', filing_date='2022-12-01', company='Garde Capital, Inc.', cik=1616328,
                    accession_no='0001616328-22-000004')
    thirteenf = ThirteenF(filing)
    assert len(thirteenf._related_filings) == 1
    assert thirteenf.previous_holding_report() is None


def test_parse_thirteenf_primary_xml():
    res = ThirteenF.parse_primary_document_xml(Path("data/metlife.13F-HR.primarydoc.xml").read_text())
    print(res)


def test_get_thirteenf_infotable():
    # This filing had an issue due to the name of the infotable attachment has XML in the name
    filing = Filing(form='13F-HR',
                    filing_date='2023-11-06',
                    company='Financial Freedom, LLC',
                    cik=1965484,
                    accession_no='0001965484-23-000006')
    hr: ThirteenF = filing.obj()
    print()
    assert "informationTable" in hr.infotable_xml
    information_table = hr.infotable
    print(information_table)
    assert len(information_table) == 375


def test_thirteenf_with_broken_infotable_xml():
    """
    This filing has an infotable with broken XML. We test that we can still get the information table

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <directory>
    <name>/Archives/edgar/data</name>
    <item>
    <name type="text.gif">0001894188-23-000007-23AndMe.index-headers.html</name>
    <size></size>
    <href>/Archives/edgar/data/1894188/000189418823000007/0001894188-23-000007-23AndMe.index-headers.html</href>
    <last-modified>2023-11-14 09:38:54</last-modified>
    </item>
    :return:
    """
    filing = Filing(form='13F-HR', filing_date='2023-11-14', company='LTS One Management LP', cik=1894188,
                    accession_no='0001894188-23-000007')
    hr: ThirteenF = filing.obj()
    information_table = hr.infotable
    print()
    print(information_table)
    assert len(information_table) == 14
    assert information_table.iloc[0].Issuer == "AMAZON COM INC"


def test_thriteenf_actual_filing_is_not_notice_report():
    """"""
    filing = Filing(form='13F-HR', filing_date='2023-11-07', company='BARCLAYS PLC', cik=312069, accession_no='0000312070-23-000017')
    assert filing.form == '13F-HR'
    hr: ThirteenF = filing.obj()

    # Check the holding report's filing
    hr_filing = hr.filing
    assert hr_filing.accession_no == filing.accession_no

    # The holding report's filing is not a notice report
    assert hr_filing.form == '13F-HR'
    assert hr.has_infotable()
    xml = hr.infotable_xml
    assert xml
    information_table = hr.infotable
    print(information_table)

def test_13FNT_other_included_managers():
    filing = Filing(form='13F-NT', filing_date='2024-02-02', company='AEW CAPITAL MANAGEMENT INC', cik=1042008, accession_no='0001104659-24-010142')
    thirteenf:ThirteenF = ThirteenF(filing)
    assert thirteenf.primary_form_information.summary_page.other_included_managers_count == 0
    assert thirteenf.primary_form_information.summary_page.total_holdings == 0
    assert thirteenf.primary_form_information.summary_page.total_value == 0


def test_thirteenf_put_call():
    filing = Filing(form='13F-HR/A', filing_date='2024-06-07', company='SG Capital Management LLC', cik=1510099, accession_no='0001172661-24-002551')
    thirteenf:ThirteenF = ThirteenF(filing)
    puts = thirteenf.infotable.query("PutCall == 'Put'")
    assert len(puts) == 3
    print(thirteenf)