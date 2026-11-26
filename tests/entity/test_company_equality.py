"""Entities compare and hash by CIK: two objects for one registrant are equal.

Before, equality was identity, so ``Company("XOM") == Company(2115436)`` was False
although both are ExxonMobil Holdings Corp, and a set of companies kept duplicates.
A successor and its predecessor are different registrants and stay unequal
(GH #2034 discussion).
"""
import pytest

from edgar import Company
from edgar.entity import Entity
from edgar.funds import FundCompany

APPLE = 320193
XOM_HOLDINGS = 2115436
EXXON_MOBIL = 34088


@pytest.mark.fast
def test_same_cik_is_equal_however_it_was_written():
    assert Company(APPLE) == Company("320193") == Company("0000320193")
    assert Company(APPLE) is not Company(APPLE)


@pytest.mark.fast
def test_different_ciks_are_not_equal():
    assert Company(APPLE) != Company(789019)
    # A successor is not its predecessor, though its history includes the other's
    assert Company(XOM_HOLDINGS) != Company(EXXON_MOBIL)


@pytest.mark.fast
def test_entity_types_with_one_cik_are_one_registrant():
    assert Entity(APPLE) == Company(APPLE)
    assert FundCompany(36405) == Entity(36405)


@pytest.mark.fast
def test_hash_follows_equality():
    companies = {Company(APPLE), Company("0000320193"), Entity(APPLE), Company(789019)}
    assert len(companies) == 2
    names = {Company(APPLE): "Apple"}
    assert names[Company("320193")] == "Apple"


@pytest.mark.fast
def test_never_equal_to_a_plain_cik_or_other_object():
    assert Company(APPLE) != APPLE
    assert Company(APPLE) != "320193"
    assert Company(APPLE) != None  # noqa: E711


@pytest.mark.network
def test_ticker_and_cik_give_the_same_company():
    """XOM resolves to ExxonMobil Holdings Corp, CIK 2115436, since 2026-07-01."""
    assert Company("XOM") == Company(XOM_HOLDINGS)
    assert Company("XOM").predecessor == Company(EXXON_MOBIL)
    assert Company(EXXON_MOBIL).successor == Company("XOM")
