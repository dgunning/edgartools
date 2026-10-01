"""A joint Schedule 13 filing's total: max, never a sum, and say when max may fall short (edgartools-qsk4).

total_shares took the max over reporting persons while OwnershipComparison summed
them, so a control chain (fund, GP, manager restating one position) counted once
per person: the Jushi Holdings 13G's two 10,000,000-share rows compared as
20,000,000. The comparison now uses the same max.

max() is not always the group's holding either. In a sample of ~40 joint filings
from 2025 most rows restated one position, but GAMCO's sub-advisers hold separate
accounts. aggregation_basis says which shape the rows have.
"""
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from edgar.beneficial_ownership import Schedule13D, Schedule13G
from edgar.beneficial_ownership.models import _aggregation_basis

TEST_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "beneficial_ownership"


def person(amount, excluded=False):
    return SimpleNamespace(reported=lambda figure: amount, is_aggregate_exclude_shares=excluded)


@pytest.mark.fast
@pytest.mark.parametrize("rows, basis", [
    ([person(2_100_000)], 'single'),
    # Jushi Holdings 13G: fund and adviser report the same position
    ([person(10_000_000), person(10_000_000)], 'identical'),
    ([person(10_000_000), person(10_000_000), person(0)], 'identical'),
    # Blackstone 0000950170-25-090888: the holding company consolidates two funds,
    # each also reported by its general partner
    ([person(4_782_781), person(4_782_781), person(2_989_238), person(2_989_238), person(1_793_543)],
     'parent_sums_children'),
    # GAMCO / Nevro 0000807249-25-000053: separate sub-adviser accounts; the parent's
    # row is 0 and flagged as excluding shares
    ([person(0, excluded=True), person(1_322_950), person(88_500), person(712_450)], 'ambiguous'),
    ([], None),
    ([person(None), person(5)], None),
])
def test_aggregation_basis(rows, basis):
    assert _aggregation_basis(rows) == basis


def _from_xml(cls, name, form):
    filing = Mock()
    filing.form = form
    filing.filing_date = date(2025, 3, 31)
    filing.xml = Mock(return_value=(TEST_DATA_DIR / name).read_text())
    return cls.from_filing(filing)


@pytest.mark.fast
def test_fixtures():
    """Aadi Bioscience 13D: BML 2,100,000 and Leonard 2,435,000. Leonard controls BML,
    so his row likely includes it, but nothing in the rows proves that."""
    aadi = _from_xml(Schedule13D, "schedule13d.xml", "SCHEDULE 13D")
    assert aadi.total_shares == 2_435_000
    assert aadi.aggregation_basis == 'ambiguous'
    assert 'persons may hold separate positions' in aadi.to_context()

    jushi = _from_xml(Schedule13G, "schedule13g.xml", "SCHEDULE 13G")
    assert jushi.total_shares == 10_000_000
    assert jushi.aggregation_basis == 'identical'
    assert 'persons may hold separate positions' not in jushi.to_context()


@pytest.mark.network
def test_gamco_nevro_is_ambiguous_and_below_its_stated_group_total():
    """Item 5(a): "The aggregate number of Securities to which this Schedule 13D relates
    is 2,123,900 shares, representing 5.54%"; the largest person reports 1,322,950."""
    from edgar import find
    schedule = find("0000807249-25-000053").obj()
    assert schedule.total_shares == 1_322_950
    assert schedule.aggregation_basis == 'ambiguous'


@pytest.mark.network
def test_blackstone_parent_sums_its_funds():
    from edgar import find
    schedule = find("0000950170-25-090888").obj()
    assert schedule.total_shares == 4_782_781
    assert schedule.aggregation_basis == 'parent_sums_children'
