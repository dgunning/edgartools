from edgar import obj, matches_form, Filing, CurrentFilings, FundReport, find, get_current_filings, CompanySearchResults
from edgar.company_reports import TenK
from edgar.effect import Effect
from edgar.entity import Entity
from edgar.offerings import FormD
from edgar.ownership import Ownership
import pytest

@pytest.fixture(scope="module")
def bioen_filing():
    return Filing(form='3', company='Bio-En Holdings Corp.', cik=1568139,
                  filing_date='2013-04-29', accession_no='0001477932-13-002021')

@pytest.mark.network
def test_matches_form(bioen_filing):
    form3_filing_amendment = Filing(form='3/A', company='Bio-En Holdings Corp.', cik=1568139,
                                    filing_date='2013-04-29', accession_no='0001477932-13-002021')
    assert matches_form(bioen_filing, form=["3", "4", "5"])
    assert matches_form(bioen_filing, form="3")
    assert matches_form(bioen_filing, form=["3"])
    assert not matches_form(bioen_filing, form="4")
    assert matches_form(form3_filing_amendment, form=["3", "4", "5"])

@pytest.mark.network
def test_obj(bioen_filing):
    ownership = obj(bioen_filing)
    assert ownership
    assert isinstance(ownership, Ownership)

    # Effect
    effect_filing = Filing(form='EFFECT',
                           filing_date='2023-02-09',
                           company='Enlight Renewable Energy Ltd.',
                           cik=1922641,
                           accession_no='9999999995-23-000354')
    effect = obj(effect_filing)
    assert isinstance(effect, Effect)

    # Fund Report
    fund = Filing(form='NPORT-P',
                  filing_date='2023-02-08',
                  company='LINCOLN VARIABLE INSURANCE PRODUCTS TRUST',
                  cik=914036,
                  accession_no='0001752724-23-020405')
    fund_report = obj(fund)
    assert isinstance(fund_report, FundReport)

    # Offering
    filing = Filing(form='D',
                    filing_date='2023-02-10',
                    company='Atalaya Asset Income Fund Parallel 345 LP',
                    cik=1965493,
                    accession_no='0001965493-23-000001')
    offering = obj(filing)
    assert isinstance(offering, FormD)

    # 10-K filing
    filing_10k = Filing(form='10-K',
                        filing_date='2023-02-10',
                        company='ALLIANCEBERNSTEIN HOLDING L.P.',
                        cik=825313,
                        accession_no='0000825313-23-000011')
    tenk = obj(filing_10k)
    assert isinstance(tenk, TenK)

    tenk = filing_10k.data_object()
    assert isinstance(tenk, TenK)

    filing = Filing(form='1-A/A', filing_date='2023-03-21', company='CancerVAX, Inc.', cik=1905495,
                    accession_no='0001493152-23-008348')
    assert filing.obj() is None

@pytest.mark.network
def test_find():
    assert find("0001493152-23-008348").accession_no == "0001493152-23-008348"
    assert find("000149315223008348").accession_no == "0001493152-23-008348"
    assert isinstance(find(1905495), Entity)
    assert find("1905495").name == 'CancerVAX, Inc.'
    assert isinstance(find("CancerVAX, Inc."), CompanySearchResults)

@pytest.mark.network
def test_find_a_dot_ticker():
    assert find("BRK.B").cik == 1067983
    assert find("CRD-A").cik == 25475

@pytest.mark.network
def test_find_a_current_filing():
    filings: CurrentFilings = get_current_filings().next()
    accession_number = filings.data['accession_number'].to_pylist()[0]
    filing = find(accession_number)
    assert filing
    assert filing.accession_no == accession_number

    accession_number = filings.next().data['accession_number'].to_pylist()[0]
    filing = find(accession_number)
    assert filing
    assert filing.accession_no == accession_number

