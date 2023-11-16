from edgar.thirteenf import ThirteenF
from pathlib import Path
from edgar import Filing
from decimal import Decimal
import pytest
from edgar import *

def test_parse_infotable():
    infotable = ThirteenF.parse_infotable_xml(Path("data/13F-HR.infotable.xml").read_text())
    assert len(infotable) == 255

MetLife13F = Filing(form='13F-HR',
                    filing_date='2023-03-23',
                    company='METLIFE INC', cik=1099219,
                    accession_no='0001140361-23-013281')
def test_thirteenf_from_filing_with_multiple_related_filing_on_same_day():
    filing = MetLife13F
    thirteenf = ThirteenF(filing)
    assert thirteenf
    # We expect that the holding report will be on the filing with the latest period of report

    assert thirteenf.filing.accession_no == '0001140361-23-013285'

    assert thirteenf.has_infotable()
    assert len(thirteenf.infotable) == 6

    # assert thirteenf.infotable.iloc[0].name_of_issuer == "METLIFE INC"

    print()
    print(thirteenf)
    assert thirteenf.total_holdings == 6
    assert thirteenf.total_value == Decimal('9229022')

    assert thirteenf.primary_form_information.signature.name == 'Steven Goulart'
    assert thirteenf.signer == 'Steven Goulart'

    # Call data object
    assert isinstance(filing.obj(), ThirteenF)

    # 13F-NT
    filing = Filing(form='13F-NT', filing_date='2023-03-17', company='Jasopt Investments Bahamas Ltd', cik=1968770,
                    accession_no='0000950123-23-002952')
    thirteenf = ThirteenF(filing)
    assert not thirteenf.has_infotable()
    assert not thirteenf.infotable_xml
    assert not thirteenf.infotable_html
    assert not thirteenf.infotable

    print(thirteenf)

    # Should throw an AssertionError if you try to parse a 10-K as a 13F
    filing = Filing(form='10-K', filing_date='2023-03-23', company='ADMA BIOLOGICS, INC.', cik=1368514,
                    accession_no='0001140361-23-013467')
    with pytest.raises(AssertionError):
        ThirteenF(filing)

def test_thirteenf_from_filing_with_multiple_related_filing_on_same_day_use_latest_period_of_report():
    filing = MetLife13F
    thirteenf = ThirteenF(filing, use_latest_period_of_report=False)
    assert thirteenf.filing.accession_no == MetLife13F.accession_no
    assert thirteenf.has_infotable()
    assert len(thirteenf.infotable) == 6

    # assert thirteenf.infotable.iloc[0].name_of_issuer == "METLIFE INC"

    print()
    print(thirteenf)
    assert thirteenf.total_holdings == 6
    assert thirteenf.total_value == Decimal('11019796')

    assert thirteenf.primary_form_information.signature.name == 'Steven Goulart'

    # Call data object
    assert isinstance(filing.obj(), ThirteenF)

    # 13F-NT
    filing = Filing(form='13F-NT', filing_date='2023-03-17', company='Jasopt Investments Bahamas Ltd', cik=1968770,
                    accession_no='0000950123-23-002952')
    thirteenf = ThirteenF(filing)
    assert not thirteenf.has_infotable()
    assert not thirteenf.infotable_xml
    assert not thirteenf.infotable_html
    assert not thirteenf.infotable

    print(thirteenf)

    # Should throw an AssertionError if you try to parse a 10-K as a 13F
    filing = Filing(form='10-K', filing_date='2023-03-23', company='ADMA BIOLOGICS, INC.', cik=1368514,
                    accession_no='0001140361-23-013467')
    with pytest.raises(AssertionError):
        ThirteenF(filing)

def test_previous_holding_report():
    thirteenf = ThirteenF(MetLife13F)
    print()
    print(thirteenf)
    print(thirteenf._related_filings)
    assert thirteenf.accession_number == '0001140361-23-013285'
    previous_holding_report = thirteenf.previous_holding_report()
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
    #filing = thirteenF_filings[10]
    filing = Filing(form='13F-HR', filing_date='2023-11-15', company='American Trust', cik=1905128, accession_no='0001905128-23-000004')
    #filing.homepage.open()
    print(str(filing))
    thirteenF = filing.obj()
    print(thirteenF)
