"""Schedule 13D/G figures a filing does not report are None, not 0 (edgartools-u6tkw, 6.0).

Bead: edgartools-u6tkw. Follows GitHub PR https://github.com/dgunning/edgartools/pull/1379,
which added ``ReportingPerson.reported()``/``unreported_fields`` and
``OwnershipComparison.reported_shares_change``/``reported_percent_change`` in 5.x
and warned that the main properties would become None in 6.0.

In 5.x an unreported figure held a placeholder 0 in ``ReportingPerson``'s six
ownership fields, ``total_voting_power`` and ``total_dispositive_power`` added the
placeholders up, ``total_shares``/``total_percent`` returned 0 for a filing with no
reporting-person rows, and ``OwnershipComparison.shares_change``/``percent_change``
and ``get_summary()`` computed with the placeholders behind a FutureWarning. In 6.0
they are None, and a reported 0 stays 0.

Ground truth: BML Investment Partners' SCHEDULE 13D on Aadi Bioscience, Inc.,
accession 0001373604-24-000118, filed 2024-12-31 (event date 12/31/2024). The
fixture tests/data/beneficial_ownership/schedule13d.xml is that filing's primary
XML (identical to SEC's apart from whitespace and the masked filer CCC). Its cover
pages report:

- BML Investment Partners, L.P.: sole voting 0, shared voting 2,100,000,
  sole dispositive 0, shared dispositive 2,100,000, aggregate 2,100,000, 8.5%
- Leonard Braden Michael: sole voting 335,000, shared voting 2,100,000,
  sole dispositive 335,000, shared dispositive 2,100,000, aggregate 2,435,000, 9.9%
"""
import re
import warnings
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from edgar.beneficial_ownership import ReportingPerson, Schedule13D
from edgar.beneficial_ownership.amendments import OwnershipComparison
from edgar.exceptions import ValidationError

FIXTURE = Path(__file__).resolve().parents[2] / "data" / "beneficial_ownership" / "schedule13d.xml"
ACCESSION = "0001373604-24-000118"


def _schedule(xml_content, form='SCHEDULE 13D', filing_date=date(2024, 12, 31)):
    filing = Mock(form=form, filing_date=filing_date, accession_no=ACCESSION, xml=Mock(return_value=xml_content))
    return Schedule13D.from_filing(filing)


def _header_only():
    filer = Mock()
    filer.company_information.name = 'BML Investment Partners, L.P.'
    filer.company_information.cik = '0001373604'
    filing = Mock(form='SC 13D', filing_date=date(2021, 3, 1), xml=Mock(return_value=None),
                  header=Mock(filers=[filer], subject_companies=[]))
    filing.cik = 1422142
    filing.company = 'Aadi Bioscience, Inc.'
    return Schedule13D.from_filing(filing)


@pytest.fixture
def no_future_warnings():
    with warnings.catch_warnings():
        warnings.simplefilter('error', FutureWarning)
        yield


@pytest.mark.fast
def test_reported_figures_keep_their_filed_values(no_future_warnings):
    """Every figure 0001373604-24-000118 reports, including BML's reported 0 sole voting power."""
    schedule = _schedule(FIXTURE.read_text())
    bml, leonard = schedule.reporting_persons
    assert bml.name == 'BML Investment Partners, L.P.'
    assert bml.unreported_fields == frozenset()
    assert bml.sole_voting_power == 0           # a reported 0 stays 0
    assert bml.sole_dispositive_power == 0
    assert bml.shared_voting_power == 2_100_000
    assert bml.aggregate_amount == 2_100_000
    assert bml.percent_of_class == 8.5
    assert bml.total_voting_power == 2_100_000
    assert bml.total_dispositive_power == 2_100_000

    assert leonard.name == 'Leonard Braden Michael'
    assert leonard.sole_voting_power == 335_000
    assert leonard.aggregate_amount == 2_435_000
    assert leonard.percent_of_class == 9.9
    assert leonard.total_voting_power == 2_435_000
    assert leonard.total_dispositive_power == 2_435_000

    assert schedule.total_shares == 2_435_000
    assert schedule.total_percent == 9.9


@pytest.mark.fast
def test_figure_left_out_is_none(no_future_warnings):
    """An amendment leaving out BML's share count and shared voting power: those are None."""
    xml = FIXTURE.read_text()
    xml = xml.replace('<aggregateAmountOwned>2100000</aggregateAmountOwned>', '', 1)
    xml = xml.replace('<sharedVotingPower>2100000</sharedVotingPower>', '', 1)
    amendment = _schedule(xml, form='SCHEDULE 13D/A', filing_date=date(2025, 2, 4))
    bml, leonard = amendment.reporting_persons

    assert bml.unreported_fields == {'aggregate_amount', 'shared_voting_power'}
    assert bml.aggregate_amount is None
    assert bml.shared_voting_power is None
    assert bml.total_voting_power is None               # 5.x: 0 + 0 = 0
    assert bml.sole_voting_power == 0                   # still reported as 0
    assert bml.total_dispositive_power == 2_100_000     # both halves reported
    assert bml.percent_of_class == 8.5
    assert bml.reported('aggregate_amount') is None     # the 5.x accessor agrees
    assert bml.reported('sole_voting_power') == 0
    assert leonard.aggregate_amount == 2_435_000

    # A counted person leaves its shares out, so the filing's total is unknown;
    # every person reports a percent, so that total is known.
    assert amendment.total_shares is None
    assert amendment.total_percent == 9.9

    comparison = OwnershipComparison(current=amendment, previous=_schedule(FIXTURE.read_text()))
    assert comparison.shares_change is None
    assert comparison.reported_shares_change is None
    assert comparison.percent_change == 0.0
    assert comparison.reported_percent_change == 0.0
    assert comparison.is_accumulating is False
    assert comparison.is_liquidating is False
    assert comparison.is_unchanged is False

    summary = comparison.get_summary()
    assert summary['current_shares'] is None
    assert summary['previous_shares'] == 2_435_000
    assert summary['shares_change'] is None
    assert summary['current_percent'] == 9.9
    assert summary['percent_change'] == 0.0


@pytest.mark.fast
def test_header_only_and_no_rows_report_nothing(no_future_warnings):
    """A pre-2025 header-only filing and an empty <reportingPersons> have no figures."""
    header_only = _header_only()
    assert header_only.has_structured_data is False
    person = header_only.reporting_persons[0]
    assert person.aggregate_amount is None
    assert person.percent_of_class is None
    assert person.total_voting_power is None
    assert header_only.total_shares is None
    assert header_only.total_percent is None

    no_rows = _schedule(re.sub(r'<reportingPersons>.*?</reportingPersons>', '<reportingPersons></reportingPersons>',
                               FIXTURE.read_text(), flags=re.S))
    assert no_rows.reporting_persons == []
    assert no_rows.total_shares is None                 # 5.x: 0
    assert no_rows.total_percent is None                # 5.x: 0.0

    comparison = OwnershipComparison(current=_schedule(FIXTURE.read_text()), previous=header_only)
    assert comparison.shares_change is None             # 5.x: +2,435,000 with a FutureWarning
    assert comparison.percent_change is None
    assert comparison.get_summary()['previous_shares'] is None


@pytest.mark.fast
def test_reported_zero_compares_as_a_number(no_future_warnings):
    """Selling out to a reported 0 is a 2,435,000-share decrease, not an unknown."""
    xml = FIXTURE.read_text()
    sold_out_xml = xml.replace('<aggregateAmountOwned>2100000</aggregateAmountOwned>',
                               '<aggregateAmountOwned>0</aggregateAmountOwned>')
    sold_out_xml = sold_out_xml.replace('<aggregateAmountOwned>2435000</aggregateAmountOwned>',
                                        '<aggregateAmountOwned>0</aggregateAmountOwned>')
    sold_out = _schedule(sold_out_xml, form='SCHEDULE 13D/A', filing_date=date(2025, 6, 1))
    assert sold_out.total_shares == 0
    comparison = OwnershipComparison(current=sold_out, previous=_schedule(xml))
    assert comparison.shares_change == -2_435_000
    assert comparison.is_liquidating is True


@pytest.mark.fast
def test_constructor_keeps_none_and_unreported_fields_in_step():
    """A figure passed as None is named in unreported_fields, and one named there is None."""
    common = dict(cik='0001373604', name='BML Investment Partners, L.P.', citizenship='DE',
                  sole_voting_power=0, shared_voting_power=2_100_000, sole_dispositive_power=0,
                  shared_dispositive_power=2_100_000, type_of_reporting_person='PN')
    from_none = ReportingPerson(aggregate_amount=None, percent_of_class=8.5, **common)
    assert from_none.unreported_fields == {'aggregate_amount'}

    # 5.x-style construction: a placeholder 0 named in unreported_fields
    from_placeholder = ReportingPerson(aggregate_amount=0, percent_of_class=8.5,
                                       unreported_fields=frozenset({'aggregate_amount'}), **common)
    assert from_placeholder.aggregate_amount is None
    assert from_placeholder == from_none

    with pytest.raises(ValidationError):
        from_none.reported('cik')
