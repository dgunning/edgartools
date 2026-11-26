"""Regression: a successor registrant's filings stopped at the succession.

GitHub Issue: https://github.com/dgunning/edgartools/issues/2034

Company("XOM") is ExxonMobil Holdings Corp (CIK 2115436) since 2026-07-01, and
its 10-Ks up to FY2025 were filed by Exxon Mobil Corp (CIK 34088). get_facts()
already merged the predecessor's facts (GH #1821), but get_filings(), and with
it latest_tenk and get_financials(), saw no 10-K at all. get_filings() now
follows the reviewed predecessor chain by default, and each row names its filer.
"""
import datetime
import warnings

import pyarrow as pa
import pytest

from edgar import Company
from edgar.entity import PredecessorHistoryWarning
from edgar.entity.filings import COMPANY_FILINGS_SCHEMA, EntityFilings, before_succession
from edgar.reference import successors
from edgar.reference.successors import Predecessor, get_predecessor_chain, get_successor

XOM_HOLDINGS = 2115436
EXXON_MOBIL = 34088


def filings_table(*rows):
    """rows: (accession, filing_date, form, report_date)"""
    columns = {name: [] for name in COMPANY_FILINGS_SCHEMA.names}
    for accession, filed, form, report_date in rows:
        row = dict.fromkeys(COMPANY_FILINGS_SCHEMA.names)
        row.update(accession_number=accession, filing_date=datetime.date.fromisoformat(filed),
                   form=form, reportDate=report_date)
        for name in columns:
            columns[name].append(row[name])
    return pa.table(columns, schema=COMPANY_FILINGS_SCHEMA)


class _Data:
    def __init__(self, cik, name, table):
        self.cik, self.name, self.table = cik, name, table

    def get_filings(self, form=None, report_date=None, accession_number=None, **query):
        pc = pa.compute
        table = self.table
        if form:
            table = table.filter(pc.is_in(table['form'], pa.array([form] if isinstance(form, str) else form)))
        if report_date:
            table = table.filter(pc.equal(table['reportDate'], report_date))
        if accession_number:
            table = table.filter(pc.equal(table['accession_number'], accession_number))
        return EntityFilings(table, cik=self.cik, company_name=self.name)


class _OfflineCompany(Company):
    """A Company whose filings come from a table, without asking SEC."""

    def __init__(self, cik, name, table, predecessors=()):
        super().__init__(cik)
        self._offline = _Data(cik, name, table)
        self.__dict__['_predecessor_chain'] = list(predecessors)

    @property
    def data(self):
        return self._offline

    @property
    def tickers(self):
        return ['TICK']


SUCCESSION = Predecessor(EXXON_MOBIL, "2026-07-01", "0001193125-26-291990")


@pytest.fixture
def xom(monkeypatch):
    monkeypatch.setattr(successors, '_get_predecessor_lookup', lambda: {XOM_HOLDINGS: SUCCESSION})
    monkeypatch.setattr(successors, '_get_successor_lookup', lambda: {EXXON_MOBIL: XOM_HOLDINGS})
    old = _OfflineCompany(EXXON_MOBIL, "EXXON MOBIL CORP", filings_table(
        ("0000034088-26-000101", "2026-09-15", "8-K", ""),           # after, as a subsidiary
        ("0000034088-26-000093", "2026-08-03", "10-Q", "2026-06-30"),  # filed under both CIKs
        ("0000034088-26-000090", "2026-07-20", "10-Q", "2026-03-31"),  # late periodic report
        ("0000034088-26-000067", "2026-05-04", "10-Q", "2026-03-31"),
        ("0000034088-26-000045", "2026-02-18", "10-K", "2025-12-31"),
        ("0000034088-25-000010", "2025-02-19", "10-K", "2024-12-31"),
    ))
    new = _OfflineCompany(XOM_HOLDINGS, "ExxonMobil Holdings Corp", filings_table(
        ("0002115436-26-000020", "2026-11-02", "10-Q", "2026-09-30"),
        ("0000034088-26-000093", "2026-08-03", "10-Q", "2026-06-30"),
        ("0001193125-26-291990", "2026-07-01", "8-K12B", ""),
    ), predecessors=[(SUCCESSION, old)])
    return new


@pytest.mark.fast
def test_ten_ks_come_from_the_predecessor_and_name_their_filer(xom):
    tenks = xom.get_filings(form="10-K")
    assert tenks.data['accession_number'].to_pylist() == ["0000034088-26-000045", "0000034088-25-000010"]
    latest = tenks.latest()
    assert (latest.cik, latest.company) == (EXXON_MOBIL, "EXXON MOBIL CORP")
    assert tenks.cik == XOM_HOLDINGS


@pytest.mark.fast
def test_predecessors_false_is_the_registrants_own_filings(xom):
    assert len(xom.get_filings(form="10-K", predecessors=False)) == 0
    assert 'cik' not in xom.get_filings(predecessors=False).data.column_names


@pytest.mark.fast
def test_only_history_before_the_succession_joins(xom):
    rows = [(f.accession_no, f.cik) for f in xom.get_filings()]
    assert rows == [
        ("0002115436-26-000020", XOM_HOLDINGS),
        ("0000034088-26-000093", XOM_HOLDINGS),   # once, as the successor's
        ("0000034088-26-000090", EXXON_MOBIL),    # filed late, for a period before
        ("0001193125-26-291990", XOM_HOLDINGS),
        ("0000034088-26-000067", EXXON_MOBIL),
        ("0000034088-26-000045", EXXON_MOBIL),
        ("0000034088-25-000010", EXXON_MOBIL),
    ]   # the subsidiary's 2026-09-15 8-K stays on its own CIK


@pytest.mark.fast
def test_merged_filings_filter_by_filer(xom):
    assert len(xom.get_filings().filter(cik=EXXON_MOBIL)) == 4


@pytest.mark.fast
def test_get_financials_reads_the_predecessor_10k_without_a_warning(xom, monkeypatch):
    read = []
    monkeypatch.setattr(EntityFilings, 'latest', lambda self, n=1: self[0] if len(self) else None)
    monkeypatch.setattr('edgar.entity.filings.EntityFiling.obj', lambda self: read.append(self.accession_no) or self)
    with warnings.catch_warnings():
        warnings.simplefilter("error", PredecessorHistoryWarning)
        _ = xom.latest_tenk
    assert read == ["0000034088-26-000045"]


@pytest.mark.fast
def test_before_succession_keeps_late_amended_periodic_reports():
    table = filings_table(
        ("a", "2024-08-09", "10-Q", "2024-06-30"),
        ("b", "2024-09-01", "10-K/A", "2023-12-31"),
        ("c", "2024-09-01", "8-K", "2024-06-30"),
        ("d", "2024-11-08", "10-Q", "2024-09-30"),
        ("e", "2024-07-31", "4", ""),
    )
    kept = before_succession(table, "2024-08-01")['accession_number'].to_pylist()
    assert kept == ["a", "b", "e"]


@pytest.mark.fast
def test_chain_follows_every_hop_and_stops_on_a_cycle(monkeypatch):
    lookup = {3: Predecessor(2, "2025-01-01", "x"), 2: Predecessor(1, "2020-01-01", "y"),
              10: Predecessor(11, "2025-01-01", "z"), 11: Predecessor(10, "2020-01-01", "w")}
    monkeypatch.setattr(successors, '_get_predecessor_lookup', lambda: lookup)
    assert [p.cik for p in get_predecessor_chain(3)] == [2, 1]
    assert [p.cik for p in get_predecessor_chain(10)] == [11]
    assert get_predecessor_chain(1) == []


@pytest.mark.fast
def test_successor_is_the_reverse_lookup():
    assert get_successor(EXXON_MOBIL) == XOM_HOLDINGS
    assert get_successor("0000034088") == XOM_HOLDINGS
    assert get_successor(XOM_HOLDINGS) is None
    assert get_successor("not-a-cik") is None


@pytest.mark.fast
def test_an_unreviewed_succession_gets_a_hint_not_a_merge(monkeypatch):
    monkeypatch.setattr(successors, '_get_predecessor_lookup', lambda: {})
    new = _OfflineCompany(999, "New Holdco", filings_table(("0000000999-26-000001", "2026-03-02", "8-K12B", "")))
    monkeypatch.setattr(_OfflineCompany, 'latest_tenk', property(lambda self: None))
    with pytest.warns(PredecessorHistoryWarning, match=r"8-K12B on 2026-03-02.*not been reviewed"):
        assert new.get_financials() is None
    assert 'cik' not in new.get_filings().data.column_names


@pytest.mark.network
def test_xom_10ks_include_exxon_mobil_corp():
    """Exxon Mobil Corp (34088) filed the FY2016-FY2025 10-Ks; the FY2025 one is
    0000034088-26-000045. Pinned by period, so ExxonMobil Holdings Corp's own
    first 10-K does not change what this checks."""
    xom = Company("XOM")
    tenks = xom.get_filings(form="10-K", amendments=False)
    by_period = {f.report_date: (f.accession_no, f.cik) for f in tenks if f.report_date}
    assert by_period["2025-12-31"] == ("0000034088-26-000045", EXXON_MOBIL)
    assert all(by_period[f"{year}-12-31"][1] == EXXON_MOBIL for year in range(2016, 2026))
    own = xom.get_filings(form="10-K", amendments=False, predecessors=False)
    assert all(f.cik == XOM_HOLDINGS and f.report_date > "2026-06-30" for f in own)
    # The 2026-08-03 10-Q was filed under both CIKs: listed once, as the successor's
    tenq = xom.get_filings(accession_number="0000034088-26-000093")
    assert len(tenq) == 1 and tenq[0].cik == XOM_HOLDINGS
    assert Company(EXXON_MOBIL).successor.cik == XOM_HOLDINGS


@pytest.mark.network
def test_northwestern_quarter_reported_by_both_is_listed_once():
    """NorthWestern Corp (73088) and NorthWestern Energy Group (1993004) each filed a
    10-Q for the quarter to 2023-09-30 on 2023-10-27, after the 2023-10-02
    succession, under separate accessions. The successor's is kept."""
    tenqs = Company(1993004).get_filings(form="10-Q", report_date="2023-09-30")
    assert [(f.accession_no, f.cik) for f in tenqs] == [("0001993004-23-000006", 1993004)]


@pytest.mark.network
def test_summit_midstream_late_10q_is_included():
    """Summit Midstream Partners (1549922) filed its 10-Q for the quarter to
    2024-06-30 on 2024-08-09, after Summit Midstream Corp (2024218) succeeded it
    on 2024-08-01."""
    tenqs = Company(2024218).get_filings(form="10-Q", report_date="2024-06-30")
    assert [(f.cik, str(f.filing_date)) for f in tenqs] == [(1549922, "2024-08-09")]


@pytest.mark.network
def test_a_company_without_a_predecessor_is_unchanged():
    apple = Company("AAPL")
    filings = apple.get_filings(form="10-K")
    assert filings.data.equals(apple.get_filings(form="10-K", predecessors=False).data)
    assert 'cik' not in filings.data.column_names


@pytest.mark.fast
def test_a_period_both_reported_after_the_succession_is_the_successors(xom):
    # The successor also files a 10-Q for 2026-03-31, the period of the predecessor's late one
    own = xom._offline.table
    xom._offline.table = pa.concat_tables([own, filings_table(("0002115436-26-000005", "2026-07-20", "10-Q", "2026-03-31"))])
    rows = [(f.accession_no, f.cik) for f in xom.get_filings(form="10-Q", report_date="2026-03-31")]
    # The predecessor's 2026-05-04 report, filed before the succession, is not the same filing
    assert rows == [("0002115436-26-000005", XOM_HOLDINGS), ("0000034088-26-000067", EXXON_MOBIL)]


@pytest.mark.fast
def test_an_accession_the_successor_has_does_not_read_the_predecessor(xom):
    predecessor = xom._predecessor_companies[0]
    predecessor._offline = None   # any read of the predecessor would fail
    found = xom.get_filings(accession_number="0000034088-26-000093")
    assert [f.cik for f in found] == [XOM_HOLDINGS]


@pytest.mark.fast
def test_an_empty_successor_table_still_merges(xom):
    # The empty-submissions path types size/isXBRL as strings; SEC's JSON infers int64
    empty = pa.table({name: pa.array([], pa.string()) if name in ('size', 'isXBRL', 'isInlineXBRL') else
                      pa.array([], COMPANY_FILINGS_SCHEMA.field(name).type) for name in COMPANY_FILINGS_SCHEMA.names})
    xom._offline.table = empty
    predecessor = xom._predecessor_companies[0]
    table = predecessor._offline.table
    for name in ('size', 'isXBRL', 'isInlineXBRL'):
        i = table.schema.get_field_index(name)
        table = table.set_column(i, name, pa.array([1] * table.num_rows, pa.int64()))
    predecessor._offline.table = table
    assert len(xom.get_filings(form="10-K")) == 2


@pytest.mark.fast
def test_filter_by_the_companys_ticker_keeps_predecessor_rows(xom, monkeypatch):
    monkeypatch.setattr('edgar.reference.tickers.find_cik', lambda ticker: XOM_HOLDINGS if ticker == "XOM" else None)
    filings = xom.get_filings()
    assert len(filings.filter(ticker="XOM")) == len(filings)
    assert len(filings.filter(ticker="AAPL")) == 0
    # A registrant's own filings, which have no cik column, filter by ticker and CIK too
    own = xom.get_filings(predecessors=False)
    assert len(own.filter(ticker="XOM")) == len(own)
    assert len(own.filter(cik=XOM_HOLDINGS)) == len(own)
    assert len(own.filter(cik=EXXON_MOBIL)) == 0


@pytest.mark.fast
def test_business_category_reads_only_the_registrants_own_forms(xom):
    assert xom._get_form_types() == {"10-Q", "8-K12B"}


@pytest.mark.fast
def test_facts_chain_continues_past_a_predecessor_without_facts(monkeypatch):
    from edgar.entity import entity_facts
    from edgar.exceptions import CompanyFactsNotFoundError
    monkeypatch.setattr(successors, '_get_predecessor_lookup', lambda: {
        3: Predecessor(2, "2025-01-01", "x"), 2: Predecessor(1, "2020-01-01", "y")})
    oldest = {"facts": {"us-gaap": {"Assets": {"units": {"USD": [{"end": "2019-12-31", "val": 7}]}}}}}

    def load(cik):
        if cik == 2:
            raise CompanyFactsNotFoundError(cik=cik)
        return oldest

    monkeypatch.setattr(entity_facts, '_load_company_facts_json', load)
    with pytest.warns(UserWarning, match="CIK 2, the predecessor of CIK 3"):
        merged = entity_facts._with_predecessor_facts(3, {"facts": {}})
    assert merged["facts"]["us-gaap"]["Assets"]["units"]["USD"] == [{"end": "2019-12-31", "val": 7}]
