"""
Network verification of AssetData against whole ABS-EE filings on sec.gov.

The EX-102 exhibits here are 63 MB (World Omni) and 121 MB (BMW), so these run
in the slow network lane. Row counts were counted by hand from the downloaded
files (``grep -c '<assets>'``).
"""
from datetime import date

import pytest

from edgar import find
from edgar.abs import AssetData
from edgar.exceptions import DataObjectError

pytestmark = [pytest.mark.network, pytest.mark.slow]


def test_autoloan_filing_obj_reads_every_loan():
    # World Omni Auto Receivables Trust 2022-C, ABS-EE filed 2026-09-29
    data = find("0001104659-26-111517").obj()
    assert isinstance(data, AssetData)
    info = data.info
    assert (info.schema, info.curated, info.row_count) == ('autoloan', True, 17_425)
    assert info.accession_no == "0001104659-26-111517"
    assert info.form == "ABS-EE" and info.is_amendment is False
    assert info.document == "woart2022cex102aug26.xml"
    assert info.reporting_period_end == date(2026, 8, 31)
    assert info.coercion_failures == {}
    # In 6.2 these were 100% empty on this filing (edgartools-pjlj5.3)
    assets = data.assets
    for column in ('obligor_credit_score', 'obligor_geographic_location', 'original_loan_amount',
                   'original_loan_term', 'reporting_period_beginning_date', 'reporting_period_ending_date',
                   'reporting_period_beginning_loan_balance_amount'):
        assert assets[column].notna().all(), column
    first = assets.set_index('asset_number').loc['998989999995338439']
    assert first['obligor_credit_score'] == 760
    assert first['original_loan_amount'] == 40241.75


def test_autolease_filing_obj_reads_every_lease():
    # BMW Vehicle Lease Trust 2023-2, ABS-EE filed 2025-12-09
    data = find("0000929638-25-004537").obj()
    assert (data.info.schema, data.info.row_count) == ('autolease', 31_924)
    lease = data.assets.set_index('asset_number').loc['361929D918B654E80248']
    assert lease['lessee_credit_score'] == 792
    assert lease['acquisition_cost'] == 46002.46


def test_filing_without_ex102_raises():
    # Apple 10-K: no asset-level exhibit
    filing = find("0000320193-24-000123")
    with pytest.raises(DataObjectError, match="no EX-102"):
        AssetData.from_filing(filing)
