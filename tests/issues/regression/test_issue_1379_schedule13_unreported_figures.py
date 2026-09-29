"""Regression tests for OwnershipComparison against filings that do not report their figures.

GitHub PR: https://github.com/dgunning/edgartools/pull/1379

OwnershipComparison added up ``aggregate_amount`` and ``percent_of_class`` over
``reporting_persons`` and read a figure the filing does not report as 0. Compared
with a filing that does report shares, that turned the whole position into a sale
or a purchase. Three ways a filing can leave the figures out:

- a pre-2025 filing read from its SGML header (``has_structured_data`` is False),
  whose reporting persons are identities only;
- structured XML with an empty ``<reportingPersons>``;
- an amendment that omits them. The schema makes every figure on a reporting
  person's cover page optional on 13D/A and 13G/A
  (docs/sec/schedule13/schema-reference.md: "m" on 13D/13G, "o" on the
  amendments), while the reporting-person row itself stays mandatory.

Against the Aadi Bioscience 13D in the test data (2,100,000 + 2,435,000 shares,
8.5% + 9.9%), an amendment omitting its figures came back as shares_change
-4,535,000, percent_change -18.4 and is_liquidating True. Against the Jushi
Holdings 13G (two 10,000,000-share rows) it was -20,000,000.

The parsers now record which figures a filing leaves out
(``ReportingPerson.unreported_fields``, ``ReportingPerson.reported()``) and the
comparison treats them as unknown: ``reported_shares_change`` and
``reported_percent_change`` are None and no direction flag is set. The 5.x
fields keep their types, so an unreported figure still holds the placeholder 0
and ``shares_change``/``percent_change`` still return numbers, with a
FutureWarning that they become None in 6.0 (the 6.0 release plan stages value
changes additively in 5.x). A reported 0 stays 0: the controls below check that
selling out, a single-person sale and a 13G/A that does report its figures
still compare as numbers, without a warning.
"""
import re
import warnings
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from edgar.beneficial_ownership import Schedule13D, Schedule13G
from edgar.beneficial_ownership.amendments import OwnershipComparison
from edgar.exceptions import ValidationError

OWNERSHIP_FIGURES = {'sole_voting_power', 'shared_voting_power', 'sole_dispositive_power',
                     'shared_dispositive_power', 'aggregate_amount', 'percent_of_class'}
TEST_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "beneficial_ownership"
SCHEDULE_13D_XML_PATH = TEST_DATA_DIR / "schedule13d.xml"
SCHEDULE_13G_XML_PATH = TEST_DATA_DIR / "schedule13g.xml"


def _schedule13d_from_xml(xml_content, form='SCHEDULE 13D/A', filing_date=date(2024, 12, 31)):
    filing = Mock()
    filing.form = form
    filing.filing_date = filing_date
    filing.xml = Mock(return_value=xml_content)
    return Schedule13D.from_filing(filing)


def _schedule13g_from_xml(xml_content, form='SCHEDULE 13G/A', filing_date=date(2025, 12, 31)):
    filing = Mock()
    filing.form = form
    filing.filing_date = filing_date
    filing.xml = Mock(return_value=xml_content)
    return Schedule13G.from_filing(filing)


def _header_only_schedule13d():
    """A pre-2025 filing with no XML: identities from the SGML header, no numbers."""
    filer = Mock()
    filer.company_information.name = 'BML Investment Partners, L.P.'
    filer.company_information.cik = '0001373604'
    subject = Mock()
    subject.company_information.name = 'Aadi Bioscience, Inc.'
    subject.company_information.cik = '0001422142'
    filing = Mock()
    filing.form = 'SC 13D'
    filing.filing_date = date(2021, 3, 1)
    filing.xml = Mock(return_value=None)
    filing.header = Mock(filers=[filer], subject_companies=[subject])
    return Schedule13D.from_filing(filing)


def _assert_change_unknown(comparison, placeholder_shares_change):
    """No purchase, sale or "unchanged" is read into a comparison with unreported figures."""
    assert comparison.is_accumulating is False
    assert comparison.is_liquidating is False
    assert comparison.is_unchanged is False
    assert comparison.reported_shares_change is None
    assert comparison.reported_percent_change is None
    # 5.x keeps the numeric properties, counting an unreported figure as 0, and says so.
    with pytest.warns(FutureWarning, match=r'shares_change .* None in edgartools 6\.0'):
        assert comparison.shares_change == placeholder_shares_change
    with pytest.warns(FutureWarning, match=r'percent_change .* None in edgartools 6\.0'):
        assert isinstance(comparison.percent_change, float)


@pytest.mark.fast
def test_ownership_comparison_against_header_only_filing_is_unknown():
    """A header-only filing has no share counts, so there is no change to report.

    Its reporting persons carry placeholder zeros. Adding those up reported the
    structured filing's whole position as bought (or sold, the other way round).
    """
    header_only = _header_only_schedule13d()
    structured = _schedule13d_from_xml(SCHEDULE_13D_XML_PATH.read_text())
    assert header_only.has_structured_data is False

    _assert_change_unknown(OwnershipComparison(current=structured, previous=header_only), 4_535_000)
    _assert_change_unknown(OwnershipComparison(current=header_only, previous=structured), -4_535_000)

    person = header_only.reporting_persons[0]
    assert person.unreported_fields == OWNERSHIP_FIGURES
    assert person.reported('aggregate_amount') is None

    with pytest.warns(FutureWarning):
        summary = OwnershipComparison(current=structured, previous=header_only).get_summary()
    assert summary['reported_shares_change'] is None
    assert summary['reported_percent_change'] is None
    assert summary['is_accumulating'] is False


@pytest.mark.fast
def test_ownership_comparison_without_reporting_person_rows_is_unknown():
    """Structured XML with an empty <reportingPersons> has no share counts either."""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()
    no_rows_xml = re.sub(r'<reportingPersons>.*?</reportingPersons>',
                         '<reportingPersons></reportingPersons>', xml_content, flags=re.S)
    no_rows = _schedule13d_from_xml(no_rows_xml)
    structured = _schedule13d_from_xml(xml_content)
    assert no_rows.has_structured_data is True
    assert no_rows.reporting_persons == []

    _assert_change_unknown(OwnershipComparison(current=no_rows, previous=structured), -4_535_000)
    _assert_change_unknown(OwnershipComparison(current=structured, previous=no_rows), 4_535_000)


@pytest.mark.fast
def test_unreported_figures_keep_their_5x_types():
    """Control: code written against 5.x keeps getting numbers until 6.0.

    Formatting a figure of a header-only filing, or a change against it, printed
    0 and a number before this fix and must not raise TypeError now. Only the new
    accessors answer None.
    """
    header_only = _header_only_schedule13d()
    structured = _schedule13d_from_xml(SCHEDULE_13D_XML_PATH.read_text())
    person = header_only.reporting_persons[0]
    assert format(person.aggregate_amount, ',') == '0'
    assert f"{person.percent_of_class:.2f}%" == '0.00%'
    assert person.total_voting_power == 0
    assert person.total_dispositive_power == 0

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', FutureWarning)
        comparison = OwnershipComparison(current=structured, previous=header_only)
        assert f"{comparison.shares_change:+,}" == '+4,535,000'
        assert f"{comparison.percent_change:+.1f}" == '+18.4'
        summary = comparison.get_summary()
    assert summary['previous_shares'] == 0
    assert summary['current_shares'] == 4_535_000


@pytest.mark.fast
def test_ownership_comparison_reported_zero_is_still_a_number():
    """Control: a row that reports 0 shares is data: selling out is a change, and 0 to 0 is unchanged."""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()
    zero_xml = re.sub(r'<aggregateAmountOwned>\d+</aggregateAmountOwned>',
                      '<aggregateAmountOwned>0</aggregateAmountOwned>', xml_content)
    zero_xml = re.sub(r'<percentOfClass>[\d.]+</percentOfClass>',
                      '<percentOfClass>0</percentOfClass>', zero_xml)
    sold_out = _schedule13d_from_xml(zero_xml)
    structured = _schedule13d_from_xml(xml_content)
    assert [p.aggregate_amount for p in sold_out.reporting_persons] == [0, 0]

    with warnings.catch_warnings():
        warnings.simplefilter('error', FutureWarning)
        comparison = OwnershipComparison(current=sold_out, previous=structured)
        summary = comparison.get_summary()
        assert summary['current_shares'] == 0
        assert summary['current_percent'] == 0
        assert comparison.shares_change == -summary['previous_shares'] < 0
        assert comparison.percent_change < 0
        assert comparison.is_liquidating is True

        unchanged = OwnershipComparison(current=sold_out, previous=_schedule13d_from_xml(zero_xml))
        assert unchanged.shares_change == 0
        assert unchanged.percent_change == 0
        assert unchanged.is_unchanged is True


@pytest.mark.fast
def test_ownership_comparison_single_person_change():
    """Control: one reporting person selling 500,000 shares."""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()
    one_person = re.sub(r'<reportingPersonInfo>\s*<reportingPersonCIK>0001373603</reportingPersonCIK>.*?</reportingPersonInfo>',
                        '', xml_content, flags=re.S)
    after_sale = one_person.replace('<aggregateAmountOwned>2100000</aggregateAmountOwned>',
                                    '<aggregateAmountOwned>1600000</aggregateAmountOwned>')
    after_sale = after_sale.replace('<percentOfClass>8.5</percentOfClass>',
                                    '<percentOfClass>6.5</percentOfClass>')
    previous = _schedule13d_from_xml(one_person)
    current = _schedule13d_from_xml(after_sale)
    assert len(previous.reporting_persons) == 1

    with warnings.catch_warnings():
        warnings.simplefilter('error', FutureWarning)
        comparison = OwnershipComparison(current=current, previous=previous)
        assert comparison.shares_change == -500_000
        assert comparison.percent_change == pytest.approx(-2.0)
        assert comparison.is_liquidating is True
        assert comparison.is_accumulating is False


# On an amendment the schema makes every ownership figure on a reporting person's
# cover page optional (docs/sec/schedule13/schema-reference.md: "m" on 13D/13G,
# "o" on 13D/A and 13G/A). The reporting-person row itself stays mandatory.
_13D_FIGURES = ('soleVotingPower', 'sharedVotingPower', 'soleDispositivePower',
                'sharedDispositivePower', 'aggregateAmountOwned', 'percentOfClass')
_13G_FIGURES = ('soleVotingPower', 'sharedVotingPower', 'soleDispositivePower',
                'sharedDispositivePower', 'reportingPersonBeneficiallyOwnedAggregateNumberOfShares',
                'classPercent')


def _amendment_without_figures(xml_content, form, figures):
    """Turn an original filing's XML into an amendment that reports no ownership figures.

    Adds the elements an amendment requires (previousAccessionNumber, amendmentNo)
    and drops the reporting-person figures an amendment may omit. The 13G Item 4
    classPercent is not a reporting-person figure and is left alone.
    """
    xml_content = xml_content.replace(f'<submissionType>{form}</submissionType>',
                                      f'<submissionType>{form}/A</submissionType>'
                                      '<previousAccessionNumber>0000000000-24-000001</previousAccessionNumber>', 1)
    xml_content = xml_content.replace('<coverPageHeader>', '<coverPageHeader><amendmentNo>1</amendmentNo>', 1)
    persons_tag = 'reportingPersons' if form == 'SCHEDULE 13D' else 'coverPageHeaderReportingPersonDetails'
    persons = re.compile(rf'<{persons_tag}>.*?</{persons_tag}>', re.S)
    figure = re.compile(r'<(%s)>[^<]*</\1>' % '|'.join(figures))

    def drop_figures(match):
        return figure.sub('', match.group(0))

    amended = persons.sub(drop_figures, xml_content)
    # Both reporting persons remain; the source reports every figure for both, the amendment none.
    def tags_in_persons(xml, tag):
        return sum(block.count(f'<{tag}>') for block in persons.findall(xml))

    assert tags_in_persons(xml_content, 'reportingPersonName') == tags_in_persons(amended, 'reportingPersonName') == 2
    for tag in figures:
        assert tags_in_persons(xml_content, tag) == 2
        assert tags_in_persons(amended, tag) == 0
    return amended


@pytest.mark.fast
@pytest.mark.parametrize('schedule_class,xml_path,form,figures', [
    (Schedule13D, SCHEDULE_13D_XML_PATH, 'SCHEDULE 13D', _13D_FIGURES),
    (Schedule13G, SCHEDULE_13G_XML_PATH, 'SCHEDULE 13G', _13G_FIGURES),
])
def test_amendment_omitting_ownership_figures_marks_them_unreported(schedule_class, xml_path, form, figures):
    """A figure the amendment leaves out was not reported: reported() is None, not 0."""
    amended_xml = _amendment_without_figures(xml_path.read_text(), form, figures)
    filing = Mock(form=f'{form}/A', filing_date=date(2025, 12, 31), xml=Mock(return_value=amended_xml))
    amendment = schedule_class.from_filing(filing)

    assert amendment.has_structured_data is True
    assert amendment.is_amendment is True
    assert len(amendment.reporting_persons) == 2
    for person in amendment.reporting_persons:
        assert person.name
        assert person.unreported_fields == OWNERSHIP_FIGURES
        for field_name in OWNERSHIP_FIGURES:
            assert person.reported(field_name) is None
            assert getattr(person, field_name) == 0  # the 5.x placeholder, None in 6.0

    # The display paths show the gap instead of a zero.
    context = amendment.to_context(detail='full')
    assert 'percent not reported (shares not reported)' in context
    assert '(0 shares)' not in context and 'Sole Voting: 0' not in context
    from rich.console import Console
    console = Console(record=True, width=200)
    console.print(amendment)
    rendered = console.export_text()
    assert 'unavailable' in rendered
    assert re.search(r'Total Shares:\s+unavailable', rendered)


@pytest.mark.fast
def test_reported_figures_are_not_marked():
    """Control: the original filings report every figure, including a reported 0."""
    schedule_13d = _schedule13d_from_xml(SCHEDULE_13D_XML_PATH.read_text(), form='SCHEDULE 13D')
    schedule_13g = _schedule13g_from_xml(SCHEDULE_13G_XML_PATH.read_text(), form='SCHEDULE 13G')
    for person in schedule_13d.reporting_persons + schedule_13g.reporting_persons:
        assert person.unreported_fields == frozenset()
    bml = schedule_13d.reporting_persons[0]
    assert bml.reported('sole_voting_power') == 0
    assert bml.reported('aggregate_amount') == 2_100_000
    assert bml.reported('percent_of_class') == 8.5
    with pytest.raises(ValidationError):
        bml.reported('cik')


@pytest.mark.fast
def test_one_person_omitting_shares_leaves_percent_known():
    """Share and percent availability are independent, person by person."""
    xml_content = SCHEDULE_13D_XML_PATH.read_text()
    original = _schedule13d_from_xml(xml_content, form='SCHEDULE 13D')
    partial_xml = xml_content.replace('<aggregateAmountOwned>2100000</aggregateAmountOwned>', '', 1)
    partial = _schedule13d_from_xml(partial_xml, filing_date=date(2025, 3, 31))
    bml, leonard = partial.reporting_persons
    assert bml.unreported_fields == {'aggregate_amount'}
    assert bml.reported('aggregate_amount') is None
    assert leonard.reported('aggregate_amount') == 2_435_000

    comparison = OwnershipComparison(current=partial, previous=original)
    assert comparison.reported_shares_change is None
    assert comparison.reported_percent_change == 0.0
    assert comparison.is_liquidating is False
    assert 'Ownership: 9.9% (shares not reported)' in partial.to_context()


@pytest.mark.fast
def test_ownership_comparison_13d_amendment_omitting_figures_is_unknown():
    """A 13D/A that leaves out the share figures is not a sale of the whole position.

    Summing the parsed rows read the omitted figures as 0, so against the Aadi
    Bioscience 13D (4,535,000 shares over two rows) the amendment came out as a
    4,535,000-share sale, -18.4 points, and is_liquidating True.
    """
    original_xml = SCHEDULE_13D_XML_PATH.read_text()
    original = _schedule13d_from_xml(original_xml, form='SCHEDULE 13D', filing_date=date(2024, 12, 31))
    amendment = _schedule13d_from_xml(_amendment_without_figures(original_xml, 'SCHEDULE 13D', _13D_FIGURES),
                                      filing_date=date(2025, 3, 31))
    assert amendment.has_structured_data is True
    assert len(amendment.reporting_persons) == 2

    _assert_change_unknown(OwnershipComparison(current=amendment, previous=original), -4_535_000)
    _assert_change_unknown(OwnershipComparison(current=original, previous=amendment), 4_535_000)

    with pytest.warns(FutureWarning):
        summary = OwnershipComparison(current=amendment, previous=original).get_summary()
    assert summary['is_liquidating'] is False
    assert summary['reported_shares_change'] is None
    assert summary['reported_percent_change'] is None


@pytest.mark.fast
def test_ownership_comparison_13g_amendment_omitting_figures_is_unknown():
    """The same for a 13G/A against the Jushi Holdings 13G (two 10,000,000-share rows)."""
    original_xml = SCHEDULE_13G_XML_PATH.read_text()
    original = _schedule13g_from_xml(original_xml, form='SCHEDULE 13G', filing_date=date(2025, 11, 26))
    amendment = _schedule13g_from_xml(_amendment_without_figures(original_xml, 'SCHEDULE 13G', _13G_FIGURES))
    assert amendment.has_structured_data is True
    assert len(amendment.reporting_persons) == 2

    _assert_change_unknown(OwnershipComparison(current=amendment, previous=original), -20_000_000)
    _assert_change_unknown(OwnershipComparison(current=original, previous=amendment), 20_000_000)


@pytest.mark.fast
def test_ownership_comparison_13g_amendment_reporting_figures():
    """Control: a 13G/A that does report its figures still compares as numbers."""
    original_xml = SCHEDULE_13G_XML_PATH.read_text()
    original = _schedule13g_from_xml(original_xml, form='SCHEDULE 13G', filing_date=date(2025, 11, 26))
    amended_xml = original_xml.replace(
        '<reportingPersonBeneficiallyOwnedAggregateNumberOfShares>10000000.00</reportingPersonBeneficiallyOwnedAggregateNumberOfShares>',
        '<reportingPersonBeneficiallyOwnedAggregateNumberOfShares>8000000.00</reportingPersonBeneficiallyOwnedAggregateNumberOfShares>')
    amended_xml = amended_xml.replace('<classPercent>5.1</classPercent>', '<classPercent>4.1</classPercent>')
    amendment = _schedule13g_from_xml(amended_xml)
    assert [p.aggregate_amount for p in amendment.reporting_persons] == [8_000_000, 8_000_000]

    with warnings.catch_warnings():
        warnings.simplefilter('error', FutureWarning)
        comparison = OwnershipComparison(current=amendment, previous=original)
        assert comparison.shares_change == -4_000_000
        assert comparison.percent_change == pytest.approx(-2.0)
        assert comparison.is_liquidating is True
        assert amendment.total_shares == 8_000_000
