"""edgar_ownership insiders returned no insider, role or trades, and ignored ``days``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1817

``_get_insider_transactions`` read ``reporting_owner``, ``is_officer``,
``is_director``, ``officer_title`` and ``transactions`` from the Form 4 object
behind ``hasattr`` guards. ``Form4`` has none of them, so every guard was False
and every entry carried only ``filing_date`` and ``accession_number``. The
``days`` lookback was in the schema and the signature but never used, so
``days=7`` returned Form 4s filed weeks earlier.

The entry is now built from ``insider_name``, ``position``, the reporting
owners' flags and ``get_ownership_summary().transactions``; a Form 4 that cannot
be parsed says so in ``error`` instead of coming back silently empty. ``days``
bounds the filing date passed to ``get_filings``.

Ground truth: NVIDIA Form 4 0001588670-26-000014 (filed 2026-09-18) by Colette
Kress, EVP & Chief Financial Officer. Read from the filing's XML: shares withheld
for tax (F) 40,747 at $212.17, and open-market sales (S) of 4,681 at $218.0144,
20,369 at $219.0172 and 9,868 at $219.5932.

Follow-up: each entry kept only the first five trades, and Form4 lists market
sales before exercises, so a filing with five or more sale lines lost its option
exercise without saying so. Entries now keep up to 25 trades and report
``transaction_total``, ``transactions_truncated`` and ``form`` (4 or 4/A).
Ground truth: Tesla Form 4 0001104659-26-055079 (filed 2026-05-04) by director
Kathleen Wilson-Thompson. Read from the filing's XML: 18 transactions, 16
open-market sales and an option exercise (M) of 40,948 shares at $14.99 reported
in both the non-derivative and derivative tables.
"""
from datetime import date, timedelta

import pytest

from edgar import Filing
from edgar.ai.mcp.tools import ownership
from edgar.ai.mcp.tools.ownership import _insider_entry, edgar_ownership

WILSON_THOMPSON_FORM4 = dict(cik=1318605, company="Tesla, Inc.", form="4",
                             filing_date="2026-05-04", accession_no="0001104659-26-055079")
KRESS_FORM4 = dict(cik=1045810, company="NVIDIA CORP", form="4",
                   filing_date="2026-09-18", accession_no="0001588670-26-000014")


@pytest.mark.vcr
def test_insider_entry_reads_insider_role_and_trades():
    entry = _insider_entry(Filing(**KRESS_FORM4))

    assert "error" not in entry
    assert entry["accession_number"] == "0001588670-26-000014"
    assert entry["form"] == "4"
    assert entry["transaction_total"] == 4
    assert entry["transactions_truncated"] is False
    assert entry["insider_name"] == "Colette Kress"
    assert entry["title"] == "EVP & Chief Financial Officer"
    assert entry["is_officer"] is True
    assert entry["is_director"] is False
    assert entry["is_ten_pct_owner"] is False

    trades = {(t["code"], t["shares"], t["price"]) for t in entry["transactions"]}
    assert trades == {
        ("F", 40747, 212.17),
        ("S", 4681, 218.0144),
        ("S", 20369, 219.0172),
        ("S", 9868, 219.5932),
    }
    sales = [t for t in entry["transactions"] if t["code"] == "S"]
    assert all(t["description"] == "Open Market Sale" for t in sales)


@pytest.mark.vcr
def test_insider_entry_keeps_the_exercise_behind_many_sales():
    entry = _insider_entry(Filing(**WILSON_THOMPSON_FORM4))

    assert entry["insider_name"] == "Kathleen Wilson-Thompson"
    assert entry["is_director"] is True
    assert entry["transaction_total"] == 18
    assert entry["transactions_truncated"] is False
    assert len(entry["transactions"]) == 18

    codes = [t["code"] for t in entry["transactions"]]
    assert codes.count("S") == 16
    exercises = [(t["shares"], t["price"], t["is_derivative"])
                 for t in entry["transactions"] if t["code"] == "M"]
    assert sorted(exercises) == [(40948, 14.99, False), (40948, 14.99, True)]


class _Trade:
    transaction_type = "sale"
    code = "S"
    code_description = "Open Market Sale"
    security_title = "Common Stock"
    shares_numeric = 100
    price_numeric = 10.0
    value_numeric = 1000.0
    is_derivative = False


class _Owner:
    is_officer = False
    is_director = True
    is_ten_pct_owner = False


class _ReportingOwners:
    owners = [_Owner()]


class _ManyTradesForm4:
    insider_name = "Test Insider"
    position = "Director"
    reporting_owners = _ReportingOwners()

    def get_ownership_summary(self):
        class _Summary:
            transactions = [_Trade() for _ in range(30)]
        return _Summary()


class _ManyTradesFiling:
    form = "4/A"
    filing_date = "2026-10-13"
    accession_number = "0000000000-26-000002"

    def obj(self):
        return _ManyTradesForm4()


def test_a_cut_trade_list_says_so():
    entry = _insider_entry(_ManyTradesFiling())

    assert entry["form"] == "4/A"
    assert entry["transaction_total"] == 30
    assert entry["transactions_truncated"] is True
    assert len(entry["transactions"]) == ownership._MAX_TRADES_PER_FILING == 25


class _Filings:
    def __init__(self, filings):
        self._filings = filings

    def head(self, n):
        return self._filings[:n]


class _Filing:
    filing_date = "2026-10-13"

    def __init__(self, n):
        self.accession_number = f"0000000000-26-{n:06d}"


class _Company:
    name = "NVIDIA CORP"
    cik = 1045810

    def __init__(self):
        self.calls = []

    def get_filings(self, **kwargs):
        self.calls.append(kwargs)
        return _Filings([_Filing(n) for n in range(10)])


@pytest.mark.parametrize("days, expected_days", [(7, 7), (0, 1)])
async def test_days_bounds_the_filing_date(monkeypatch, days, expected_days):
    company = _Company()
    monkeypatch.setattr(ownership, "resolve_company", lambda identifier: company)
    monkeypatch.setattr(ownership, "_insider_entry",
                        lambda filing: {"accession_number": filing.accession_number})

    response = await edgar_ownership(identifier="NVDA", analysis_type="insiders",
                                     days=days, limit=3)

    since = (date.today() - timedelta(days=expected_days)).isoformat()
    assert response.success is True
    assert company.calls == [{"form": "4", "filing_date": f"{since}:"}]
    assert response.data["days"] == expected_days
    assert response.data["since"] == since
    assert response.data["transaction_count"] == 3


class _RecordingDay(date):
    """The day the cassette was recorded, so the `days` window replays identically."""

    @classmethod
    def today(cls):
        return cls(2026, 11, 2)


@pytest.mark.vcr
async def test_days_leaves_out_older_form4s(monkeypatch):
    # NVIDIA's five most recent Form 4s as of 2026-11-02, from its EDGAR submissions:
    # 0002152188-26-000007 (2026-10-13), 0001197647-26-000011 (2026-10-09),
    # 0001696841-26-000014 (2026-09-23), 0001199039-26-000016 (2026-09-22) and
    # 0001243821-26-000007 (2026-09-18). A 30-day window from 2026-11-02 starts on
    # 2026-10-03, so only the first two belong in it. Before the fix all five came back.
    # The cassette was recorded against main; raising=False keeps the patch a no-op there.
    monkeypatch.setattr(ownership, "date", _RecordingDay, raising=False)

    response = await edgar_ownership(identifier="NVDA", analysis_type="insiders",
                                     days=30, limit=5)

    assert response.success is True
    filed = {t["accession_number"]: t["filing_date"] for t in response.data["transactions"]}
    assert "0001696841-26-000014" not in filed
    assert filed == {
        "0002152188-26-000007": "2026-10-13",
        "0001197647-26-000011": "2026-10-09",
    }
    assert response.data["since"] == "2026-10-03"


class _UnparseableFiling:
    form = "4"
    filing_date = "2026-10-13"
    accession_number = "0000000000-26-000001"

    def obj(self):
        raise ValueError("no ownershipDocument in the XML")


def test_unparseable_form4_reports_the_error():
    entry = _insider_entry(_UnparseableFiling())

    assert entry["accession_number"] == "0000000000-26-000001"
    assert entry["error"] == "Could not parse Form 4: no ownershipDocument in the XML"
    assert entry["form"] == "4"
    assert "insider_name" not in entry
