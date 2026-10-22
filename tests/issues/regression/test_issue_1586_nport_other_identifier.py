"""Regression: ``investment_data()`` carries the filer's other unique identifier.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1586

Where a holding has no CUSIP, ISIN or ticker, N-PORT item C.1.e.iv states another
unique identifier, ``<other otherDesc="..." value="..."/>``. ``Identifiers.from_xml``
parsed it into ``identifiers.other``, but no ``investment_data()`` column carried
it, and the frame is sorted by value, so a row could not be paired back to
``report.investments`` by position. On BHK's NPORT-P for 2026-06-30
(0001410368-26-085673), 121 of 1,487 non-derivative holdings state one, and for
45 reverse repos with Royal Bank of Canada, all named alike and titled
"2026-07-13-3.74", it is the only field that tells them apart. The type is kept
as filed: BHK writes both "BlackRock Identifier" and "Blackrock Identifier".
"""
from collections import Counter
from pathlib import Path

import pytest


@pytest.mark.fast
def test_a_stated_other_identifier_reaches_investment_data_offline():
    """Keeps the column covered in test-fast: Sample 1's one holding, given an ``<other>`` identifier."""
    from edgar.funds.reports import FundReport

    xml = Path('data/nport/samples/N-PORT Sample 1.xml').read_text()
    holding = '<ticker value="3F708"/>'
    assert xml.count(holding) == 1
    xml = xml.replace(holding, holding + '<other otherDesc="LoanX ID" value="LX123456"/>')

    report = FundReport(**FundReport.parse_fund_xml(xml))
    row = report.investment_data(include_derivatives=False).iloc[0]
    assert (row['cusip'], row['other_id'], row['other_id_type']) == ('379006355', 'LX123456', 'LoanX ID')


@pytest.mark.network
@pytest.mark.vcr
def test_bhk_states_an_other_identifier_on_121_holdings():
    """Ground truth: BHK's NPORT-P for 2026-06-30, accession 0001410368-26-085673."""
    from edgar import find
    from edgar.funds.reports import FundReport

    report = FundReport.from_filing(find('0001410368-26-085673'))
    securities = report.investment_data(include_derivatives=False)
    stated = securities[securities.other_id.notna()]
    assert len(securities) == 1487
    assert len(stated) == 121
    assert stated.other_id.nunique() == 121
    assert Counter(stated.other_id_type) == Counter(
        {'BlackRock Identifier': 117, 'LoanX ID': 3, 'Blackrock Identifier': 1})

    rbc = stated[(stated.name == 'ROYAL BANK OF CANADA (NEW YORK BRANCH)') & (stated.title == '2026-07-13-3.74')]
    assert len(rbc) == 45
    assert rbc.other_id.nunique() == 45

    largest = securities.iloc[0]
    assert (largest['name'], largest['title'], largest['other_id'], largest['other_id_type']) == (
        'BNP PARIBAS SA', 'OPEN-3.68', 'BYJ725YS8', 'BlackRock Identifier')
