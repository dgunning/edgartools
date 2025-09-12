from pathlib import Path
from edgar.form144 import Form144
from edgar import Filing
import pytest

@pytest.mark.fast
def test_form_144_from_xml():
    form144_xml = Path('data/144/EDGAR Form 144 XML Samples/Sample 144.xml').read_text()
    form144 = Form144.parse_xml(form144_xml)
    print("------\nForm 144\n------")
    print(form144)

@pytest.mark.network
def test_form144_from_filing():
    filing = Filing(form='144/A', filing_date='2022-12-22', company='Assure Holdings Corp.', cik=1798270,
                    accession_no='0001886261-22-000004')
    form144 = Form144.from_filing(filing)
    print(form144)

@pytest.mark.network
def test_amount_sold_past_3months():
    filing = Filing(form='144', filing_date='2023-04-17', company='DELTA AIR LINES, INC.', cik=27904,
                    accession_no='0001959173-23-000600')
    form144: Form144 = Form144.from_filing(filing)
    print(form144.securities_sold_past_3_months)
    assert len(form144.securities_sold_past_3_months) == 1
    assert form144.securities_sold_past_3_months.iloc[0].amount_sold == 5000

@pytest.mark.network
def test_form144_with_no_xml():
    filing = Filing(company="Esperion Therapeutics, Inc.", cik=1434868, form='144', filing_date='2015-05-08', accession_no='0000903423-15-000301')
    xml = filing.xml()
    if not xml:
        form144 = filing.obj()
        assert form144 is None

@pytest.mark.network
def test_form144_with_multiple_securities_to_be_sold():
    filing = Filing(form='144', filing_date='2023-04-18', company='Owens Corning', cik=1370946,
                    accession_no='0001959173-23-000608')
    form144:Form144 = filing.obj()
    assert len(form144.securities_to_be_sold) == 8
    assert form144.broker_name == "Fidelity Brokerage Services LLC"
    assert form144.units_to_be_sold == 3000
    assert form144.exchange_name == "NYSE"
    assert form144.approx_sale_date == "04/18/2023"
    assert form144.security_class == 'Common'
    assert form144.market_value == 300000.0
    print(form144)
