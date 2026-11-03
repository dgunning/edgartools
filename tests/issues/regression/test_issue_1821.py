"""Regression test for GitHub issue #1821.

SEC moved ticker XOM from Exxon Mobil Corp (CIK 34088) to ExxonMobil Holdings
Corp (CIK 2115436) when the holding company was formed on 2026-07-01 (8-K12B
0001193125-26-291990). Since GH #1588, Company("XOM") follows SEC to the new
registrant, which has filed no 10-K, so get_financials() returned None and the
annual income statement from get_facts() was empty, with no hint that the
history is under CIK 34088. For successions reviewed by hand, get_facts() now
merges the predecessor's facts from before the succession, Company exposes
.predecessor, and get_financials() warns when the successor has no 10-K yet.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1821
"""
import warnings

import pytest

from edgar import Company
from edgar.entity import PredecessorHistoryWarning, entity_facts
from edgar.entity.entity_facts import merge_predecessor_facts
from edgar.exceptions import CompanyFactsNotFoundError
from edgar.reference.successors import Predecessor, _get_predecessor_lookup, get_predecessor

XOM_HOLDINGS = 2115436
EXXON_MOBIL = 34088
APPLE = 320193


class _NoFilings:
    def latest(self):
        return None


@pytest.fixture
def no_annual_reports(monkeypatch):
    # A company with no 10-K, 20-F or 40-F, without asking SEC
    monkeypatch.setattr(Company, "latest_tenk", property(lambda self: None))
    monkeypatch.setattr(Company, "get_filings", lambda self, **kwargs: _NoFilings())
    monkeypatch.setattr(Company, "name", property(lambda self: f"Company {self.cik}"))


def test_successor_lists_its_predecessor():
    assert get_predecessor(XOM_HOLDINGS) == Predecessor(EXXON_MOBIL, "2026-07-01", "0001193125-26-291990")
    assert get_predecessor("0002115436").cik == EXXON_MOBIL


def test_a_company_without_a_succession_has_no_predecessor():
    assert get_predecessor(APPLE) is None
    assert get_predecessor(EXXON_MOBIL) is None
    assert get_predecessor("not-a-cik") is None
    assert Company(APPLE).predecessor is None


def test_company_predecessor_is_the_old_registrant():
    predecessor = Company(XOM_HOLDINGS).predecessor
    assert isinstance(predecessor, Company)
    assert predecessor.cik == EXXON_MOBIL


def test_get_financials_points_a_successor_to_its_predecessor(no_annual_reports):
    with pytest.warns(PredecessorHistoryWarning, match=r"succeeded CIK 34088 on 2026-07-01.*Company\(34088\)\.get_financials\(\)"):
        assert Company(XOM_HOLDINGS).get_financials() is None


def test_get_financials_stays_quiet_without_a_predecessor(no_annual_reports):
    with warnings.catch_warnings():
        warnings.simplefilter("error", PredecessorHistoryWarning)
        assert Company(APPLE).get_financials() is None


def _row(start, end, val, accn="0000000000-00-000000"):
    row = {"end": end, "val": val, "accn": accn, "fy": int(end[:4]), "fp": "FY", "form": "10-K", "filed": end}
    if start:
        row["start"] = start
    return row


def _facts(cik, concepts):
    return {"cik": cik, "entityName": f"Company {cik}",
            "facts": {"us-gaap": {c: {"label": c, "units": {"USD": rows}} for c, rows in concepts.items()}}}


def test_merge_takes_predecessor_history_before_the_succession():
    successor = _facts(2, {"Revenues": [_row("2026-07-01", "2026-09-30", 30)]})
    predecessor = _facts(1, {"Revenues": [_row("2025-01-01", "2025-12-31", 100),
                                          _row("2026-07-01", "2026-09-30", 999)],   # filed as a subsidiary afterwards
                             "Assets": [_row(None, "2025-12-31", 500)]})
    merged = merge_predecessor_facts(successor, predecessor, "2026-07-01")
    revenues = merged["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    assert sorted((r["end"], r["val"]) for r in revenues) == [("2025-12-31", 100), ("2026-09-30", 30)]
    assert merged["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["val"] == 500
    assert merged["entityName"] == "Company 2"


def test_merge_keeps_the_successor_value_for_a_shared_period():
    successor = _facts(2, {"Revenues": [_row("2025-01-01", "2025-12-31", 101)]})
    predecessor = _facts(1, {"Revenues": [_row("2025-01-01", "2025-12-31", 100)]})
    merged = merge_predecessor_facts(successor, predecessor, "2026-07-01")
    assert [r["val"] for r in merged["facts"]["us-gaap"]["Revenues"]["units"]["USD"]] == [101]
    # The inputs are left alone; get_company_facts caches the parsed result, not these
    assert len(successor["facts"]["us-gaap"]["Revenues"]["units"]["USD"]) == 1


def test_a_missing_predecessor_leaves_the_successor_facts_and_says_so(monkeypatch):
    successor = _facts(XOM_HOLDINGS, {"Revenues": [_row("2026-07-01", "2026-09-30", 30)]})

    def load(cik):
        if cik == EXXON_MOBIL:
            raise CompanyFactsNotFoundError(cik=cik)
        return successor

    monkeypatch.setattr(entity_facts, "_load_company_facts_json", load)
    with pytest.warns(UserWarning, match="predecessor of CIK 2115436"):
        assert entity_facts._with_predecessor_facts(XOM_HOLDINGS, successor) is successor


def test_listed_successions_are_well_formed():
    lookup = _get_predecessor_lookup()
    assert len(lookup) == 10
    for successor, predecessor in lookup.items():
        assert successor != predecessor.cik
        assert predecessor.cik not in lookup, "chained successions are not supported"
        assert len(predecessor.effective_date) == 10 and predecessor.effective_date[4] == "-"


@pytest.mark.network
def test_xom_facts_include_the_predecessor_history():
    xom = Company("XOM")
    assert xom.cik == XOM_HOLDINGS
    income = xom.get_facts().income_statement(periods=10, annual=True, as_dataframe=True)
    assert "FY 2016" in income.columns
    # Total revenues FY2025, 10-K 0000034088-26-000045 (SEC companyconcept, read 2026-11-03)
    assert income.loc["Revenues", "FY 2025"] == 332_238_000_000
    # Q3 2026 comes from the successor's own 10-Q 0002115436-26-000020
    quarterly = xom.get_facts().income_statement(periods=4, annual=False, as_dataframe=True)
    assert quarterly.loc["Revenues", "Q3 2026"] == 113_164_000_000


@pytest.mark.network
def test_xom_history_is_reachable_through_the_predecessor():
    financials = Company("XOM").predecessor.get_financials()
    assert financials.get_revenue() == 332_238_000_000
