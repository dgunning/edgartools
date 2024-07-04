from pathlib import Path

import pandas as pd
from rich import print

from edgar import Filing
from edgar._xbrl import FilingXbrl, XbrlFacts, get_period

pd.options.display.max_columns = 10

CARBO_CERAMICS_FILING_XBRL = FilingXbrl.parse(Path('data/crr.xbrl.xml').read_text())


def test_filing_xbrl_parse():
    xbrl_text = Path('data/crr.xbrl.xml').read_text()
    filing_xbrl: FilingXbrl = FilingXbrl.parse(xbrl_text)
    assert filing_xbrl
    assert not filing_xbrl.facts.empty
    pd.options.display.max_columns = 7


def test_filing_xbrl_properties():
    filing_xbrl: FilingXbrl = CARBO_CERAMICS_FILING_XBRL
    assert filing_xbrl.company_name == 'CARBO CERAMICS INC'
    assert filing_xbrl.cik == int('0001009672')
    assert filing_xbrl.form_type == '10-K'
    assert filing_xbrl.fiscal_year_end_date == '2017-12-31'
    assert len(filing_xbrl.gaap) > 100

    print(filing_xbrl)
    print(filing_xbrl.facts)


def test_filing_get_facts():
    gaap_facts_2017 = CARBO_CERAMICS_FILING_XBRL.facts.get_facts_for_namespace("us-gaap", end_date="2017-12-31")
    assert all([d in gaap_facts_2017.end_date.unique().tolist() for d in ['2017-12-31']])

    gaap_facts_2016 = CARBO_CERAMICS_FILING_XBRL.facts.get_facts_for_namespace("us-gaap", end_date="2016-12-31")
    assert all([d in gaap_facts_2016.end_date.tolist() for d in ['2016-12-31']])

    dei_facts = CARBO_CERAMICS_FILING_XBRL.facts.get_facts_for_namespace("dei", end_date="2017-12-31")
    assert all([fact in dei_facts.fact.tolist() for fact in ['DocumentType',
                                                             'AmendmentFlag',
                                                             'EntityWellKnownSeasonedIssuer',
                                                             'DocumentPeriodEndDate']])


def test_xbrl_gaap_facts():
    gaap_facts = CARBO_CERAMICS_FILING_XBRL.gaap
    assert all([fact in gaap_facts.fact.tolist() for fact in ['CostOfGoodsAndServicesSold',
                                                              'IncomeTaxesPaid']])


def test_get_fact():
    xbrl_facts = CARBO_CERAMICS_FILING_XBRL.facts
    assert xbrl_facts.get_fact(fact='GrossProfit', namespace='us-gaap', end_date='2017-12-31') == '-53325000'
    assert xbrl_facts.get_fact(fact='GrossProfit', namespace='us-gaap', end_date='2016-12-31') == '-85014000'
    assert xbrl_facts.get_fact(fact='GrossProfit', namespace='dei', end_date='2017-12-31') is None
    assert xbrl_facts.get_fact(fact='EntityRegistrantName', namespace='dei',
                               end_date='2017-12-31') == 'CARBO CERAMICS INC'


def test_xbrl_facts_get_dei():
    xbrl_facts = CARBO_CERAMICS_FILING_XBRL.facts
    assert xbrl_facts.get_dei("EntityRegistrantName") == 'CARBO CERAMICS INC'
    assert xbrl_facts.get_dei("DocumentType") == '10-K'
    assert xbrl_facts.get_dei("DocumentPeriodEndDate") == '2017-12-31'
    assert xbrl_facts.get_dei("DocumentFiscalYearFocus") == '2017'
    assert xbrl_facts.get_dei("DocumentFiscalPeriodFocus") == 'FY'

    assert xbrl_facts.get_dei("EntityCentralIndexKey") == '0001009672'
    assert xbrl_facts.get_dei("EntityFilerCategory") == 'Accelerated Filer'
    assert xbrl_facts.period_end_date == '2017-12-31'


def test_xbrl_get_dei():
    filing = Filing(company='ADVANCED MICRO DEVICES INC', cik=2488, form='10-K', filing_date='2023-02-27',
                    accession_no='0000002488-23-000047')
    xbrl = filing.xbrl()
    assert xbrl.facts.get_dei('DocumentPeriodEndDate') == '2022-12-31'
    assert xbrl.period_end_date == '2022-12-31'


def test_default_gaap_dimension():
    filing_xbrl: FilingXbrl = FilingXbrl.parse(Path('data/crr.xbrl.xml').read_text())
    assert filing_xbrl.facts._default_gaap_dimension() == "{'us-gaap:ConsolidationItemsAxis': 'us-gaap:OperatingSegmentsMember', 'us-gaap:StatementBusinessSegmentsAxis': 'crr:OilfieldTechnologiesAndServicesSegmentMember'}"


def test_get_period_for_start_and_end_dates():
    assert get_period("2024-01-01", "2024-12-31") == '2024'
    assert get_period("2024-04-01", "2024-06-30") == 'Q2 2024'
    assert get_period("2024-07-04", "2024-07-04") == '2024-07-04'
    assert get_period("2024-05-01", "2024-08-31") == '2024-05-01 to 2024-08-31'
    assert get_period("2024-01-01", "2024-01-31") == 'Jan 2024'
    assert get_period("2024-01-01", "2024-01-30") == '2024-01-01 to 2024-01-30'
    assert get_period("2023-02-01", "2023-02-28") == 'Feb 2023'
    assert get_period("2024-02-01", "2024-02-29") == 'Feb 2024'


def test_period_column_set_for_filing():
    data = (CARBO_CERAMICS_FILING_XBRL
            .facts.data.filter(['fact', 'period', 'start_date', 'end_date'])
            )
    data_2017 = data.query("period=='2017'")
    assert data_2017.start_date.unique().tolist() == ['2017-01-01']
    assert data_2017.end_date.unique().tolist() == ['2017-12-31']

    xbrl = FilingXbrl.parse(Path('data/WatersCorp.8-K.xbrl.xml').read_text())
    data = xbrl.facts.data
    assert data.period.unique().tolist() == ['2024-01-08']


def test_filing_xbrl_years_quarters():
    assert CARBO_CERAMICS_FILING_XBRL.facts.years == ['2011', '2014', '2015', '2016', '2017', '2018', '2019', '2020']


def test_find_facts_by_value():
    filing = Filing(company='Tesla, Inc.', cik=1318605, form='10-K', filing_date='2023-01-31',
                    accession_no='0000950170-23-001409')
    xbrl = filing.xbrl()
    facts: XbrlFacts = xbrl.facts.get_facts_for_namespace('us-gaap', end_date='2022-12-31')
    print(facts.query("value.str.contains('60609')"))

    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2023-11-03',
                    accession_no='0000320193-23-000106')
    xbrl = filing.xbrl()
    facts: XbrlFacts = xbrl.facts.get_facts_for_namespace('us-gaap', end_date='2023-09-30')
    print(facts.query("value.str.contains('214')"))


def test_read_inline_xbrl():
    import lxml.etree as ET
    html = Path('data/NextPoint.8K.html').read_text()
    html = bytes(html, encoding='utf-8')
    root = ET.fromstring(html)
    # XPath expression to find all <ix:*> tags
    ix_tags = root.xpath("//*[starts-with(name(), 'ix:')]")

    # Remove each ix tag from the tree
    for tag in ix_tags:
        # Create a new text node with the content of the ix tag
        if tag.text:
            new_text = ET.fromstring(f"<span>{tag.text}</span>")
            tag.getparent().replace(tag, new_text)
        else:
            tag.getparent().remove(tag)

    # Convert the modified tree back to a string
    cleaned_html = ET.tostring(root, encoding='unicode')
    print(cleaned_html)


def test_get_get_periods_for_xbrl_facts():
    print()
    periods = CARBO_CERAMICS_FILING_XBRL.get_fiscal_periods()
    assert len(periods) == 5

    assert len(CARBO_CERAMICS_FILING_XBRL.get_fiscal_periods(period_type='FY')) == 5
    assert len(CARBO_CERAMICS_FILING_XBRL.get_fiscal_periods(period_type='FY', include_instant_periods=False)) == 3


def test_get_fiscal_periods():
    periods = CARBO_CERAMICS_FILING_XBRL.get_fiscal_periods(period_type='FY', include_instant_periods=False)

    expected_periods = pd.DataFrame([('2017-01-01', '2017-12-31', 'FY'),
                                     ('2016-01-01', '2016-12-31', 'FY'),
                                     ('2015-01-01', '2015-12-31', 'FY')],
                                    columns=['start_date', 'end_date', 'period_type'])
    row, col = periods.shape
    for row in range(row):
        for col in range(col):
            assert periods.iloc[row, col] == expected_periods.iloc[row, col]

    periods = CARBO_CERAMICS_FILING_XBRL.get_fiscal_periods(period_type='instant')
    assert periods.iloc[0, 0] == periods.iloc[0, 1] == '2017-12-31'
    assert periods.iloc[1, 0] == periods.iloc[1, 1] == '2016-12-31'


def test_get_fact_by_periods_for_10K():
    # 10-K filing
    data = CARBO_CERAMICS_FILING_XBRL.get_facts_by_periods()
    assert data.columns.tolist() == ['2017-12-31', '2016-12-31', '2015-12-31']


def test_get_fact_by_periods_for_10Q():
    # 10-Q filing
    filing = Filing(form='10-Q', filing_date='2024-04-25', company='1ST SOURCE CORP', cik=34782,
                    accession_no='0000034782-24-000054')
    xbrl = filing.xbrl()
    data = xbrl.get_facts_by_periods()
    # assert data.columns.tolist() == ['2024-03-31', '2023-03-31']
    print(filing.obj().financials)


def test_get_facts_by_periods_nflx():
    filing = Filing(company='NETFLIX INC', cik=1065280, form='10-K', filing_date='2024-01-26',
                    accession_no='0001065280-24-000030')
    xbrl = filing.xbrl()
    assert 'CashAndCashEquivalentsAtCarryingValue' in xbrl.facts.data.fact.tolist()
    period_facts = xbrl.get_facts_by_periods()
    assert 'CashAndCashEquivalentsAtCarryingValue' in period_facts.index


def test_get_fiscal_period_fact_for_apple_2016():
    filing = Filing(company='Apple Inc.', cik=320193, form='10-K', filing_date='2016-10-26',
                    accession_no='0001628280-16-020309')
    xbrl: FilingXbrl = filing.xbrl()
    fiscal_periods = xbrl.get_fiscal_periods()
    facts_by_periods = xbrl.get_facts_by_periods()
    # print(facts_by_periods)

    # fiscal_period_facts = xbrl.get_fiscal_period_facts(fact_names=['SalesRevenueNet'])

    # print(fiscal_period_facts)
