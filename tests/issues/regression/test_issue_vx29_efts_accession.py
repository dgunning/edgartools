"""Regression tests for edgartools-vx29: resolving an accession without the index.

An accession number carries no CIK, and every document URL is
``/Archives/edgar/data/{cik}/{accession}/...``, so opening a filing from an
accession alone always costs a lookup. It used to be paid by downloading
quarterly full-index files until the accession turned up — 4.1 MB gzipped per
quarter probed, expanding to 41 MB to parse — to learn four short fields.

EDGAR full-text search answers the same question in about 2 KB. It only indexes
2001 onward, so the index remains the fallback and must stay correct.

These tests pin the three things that can go wrong: the wrong filing being
resolved (EFTS is a text search, so a filing quoting another's accession number
matches the query), a half-filled Filing being returned instead of falling back,
and an EFTS outage turning into an exception instead of a fallback.
"""
from datetime import date

import pytest

from edgar._filings import _filing_from_efts
from edgar.search.efts import _clean_display_name, resolve_accession


def _efts_response(payload):
    """Minimal stand-in for the object get_with_retry returns."""
    import orjson

    class _Response:
        content = orjson.dumps(payload)

    return _Response()


def _hit(adsh, ciks, names, form="424B5", file_date="2025-12-31"):
    return {"_source": {"adsh": adsh, "ciks": ciks, "display_names": names,
                        "form": form, "file_date": file_date}}


class TestResolutionIsForTheRequestedFiling:
    """EFTS is a text search; matching the query is not the same as being it."""

    def test_a_filing_quoting_another_accession_does_not_win(self, monkeypatch):
        """The decisive case. A filing that cites 0001493152-25-029712 in its
        text matches a phrase search for it, and ranks first here. Taking
        hits[0] would resolve the citing filing — right accession asked for,
        wrong filing returned, and no error anywhere."""
        wanted = "0001493152-25-029712"
        payload = {"hits": {"hits": [
            _hit("0009999999-25-000001", ["0000111111"], ["Some Other Filer  (CIK 0000111111)"]),
            _hit(wanted, ["0000749647"], ["Imunon, Inc.  (IMNN)  (CIK 0000749647)"]),
        ]}}
        monkeypatch.setattr("edgar.httprequests.get_with_retry",
                            lambda *a, **k: _efts_response(payload))

        fields = resolve_accession(wanted)
        assert fields["cik"] == 749647
        assert fields["company"] == "Imunon, Inc."

    def test_only_a_citing_filing_matches_so_it_falls_back(self, monkeypatch):
        """No hit carries the accession: that is a miss, not a wrong answer."""
        payload = {"hits": {"hits": [
            _hit("0009999999-25-000001", ["0000111111"], ["Some Other Filer  (CIK 0000111111)"]),
        ]}}
        monkeypatch.setattr("edgar.httprequests.get_with_retry",
                            lambda *a, **k: _efts_response(payload))

        assert resolve_accession("0001493152-25-029712") is None


class TestFallbackRatherThanAHalfAnswer:
    """None means "ask the index". A partial Filing would be worse than that."""

    def test_no_hits_returns_none(self, monkeypatch):
        monkeypatch.setattr("edgar.httprequests.get_with_retry",
                            lambda *a, **k: _efts_response({"hits": {"hits": []}}))
        assert resolve_accession("0000912057-97-000920") is None

    @pytest.mark.parametrize("missing", ["ciks", "form", "file_date"])
    def test_a_hit_missing_a_required_field_returns_none(self, monkeypatch, missing):
        """Every one of these is needed to build a usable Filing, and the CIK
        most of all — it is what the document URL is built from."""
        hit = _hit("0001493152-25-029712", ["0000749647"], ["Imunon, Inc.  (IMNN)  (CIK 0000749647)"])
        hit["_source"][missing] = [] if missing == "ciks" else None
        monkeypatch.setattr("edgar.httprequests.get_with_retry",
                            lambda *a, **k: _efts_response({"hits": {"hits": [hit]}}))

        assert resolve_accession("0001493152-25-029712") is None

    def test_efts_failure_is_a_miss_not_an_exception(self, monkeypatch):
        """An EFTS outage must degrade to the slow path, not break lookups."""
        def _boom(*args, **kwargs):
            raise ConnectionError("efts.sec.gov unreachable")

        monkeypatch.setattr("edgar.httprequests.get_with_retry", _boom)
        assert resolve_accession("0001493152-25-029712") is None
        assert _filing_from_efts("0001493152-25-029712") is None


class TestMultiFilerFilings:
    def test_every_filer_is_kept(self, monkeypatch):
        """BofA structured notes are filed by the issuer and guaranteed by the
        parent. EDGAR serves the documents under either CIK; both are kept, the
        first as the filing's own and the rest as related entities."""
        payload = {"hits": {"hits": [_hit(
            "0001918704-24-002559",
            ["0001682472", "0000070858"],
            ["BofA Finance LLC  (CIK 0001682472)",
             "BANK OF AMERICA CORP /DE/  (CIK 0000070858)"],
            form="424B2", file_date="2024-12-31",
        )]}}
        monkeypatch.setattr("edgar.httprequests.get_with_retry",
                            lambda *a, **k: _efts_response(payload))

        filing = _filing_from_efts("0001918704-24-002559")
        assert (filing.cik, filing.company) == (1682472, "BofA Finance LLC")
        assert [e["cik"] for e in filing._related_entities] == [70858]

    def test_a_filer_without_a_display_name_is_still_kept(self, monkeypatch):
        """The lists are parallel in every response seen. If they ever are not,
        losing a CIK is the one outcome that must not happen."""
        payload = {"hits": {"hits": [_hit(
            "0001918704-24-002559", ["0001682472", "0000070858"],
            ["BofA Finance LLC  (CIK 0001682472)"], form="424B2", file_date="2024-12-31",
        )]}}
        monkeypatch.setattr("edgar.httprequests.get_with_retry",
                            lambda *a, **k: _efts_response(payload))

        filing = _filing_from_efts("0001918704-24-002559")
        assert [e["cik"] for e in filing._related_entities] == [70858]


class TestDisplayNameCleaning:
    """EFTS decorates names with ticker and CIK; the index carries them bare."""

    @pytest.mark.parametrize("display,expected", [
        ("Airbnb, Inc.  (ABNB)  (CIK 0001559720)", "Airbnb, Inc."),
        ("BANK OF AMERICA CORP /DE/  (CIK 0000070858)", "BANK OF AMERICA CORP /DE/"),
        ("Imunon, Inc.  (IMNN)  (CIK 0000749647)", "Imunon, Inc."),
    ])
    def test_decoration_is_stripped(self, display, expected):
        assert _clean_display_name(display) == expected

    def test_single_spaced_parentheses_are_part_of_the_name(self):
        """Anchored on the double space EFTS uses, so a filer whose real name
        ends in parentheses keeps them."""
        assert _clean_display_name("ACME HOLDINGS (DELAWARE)") == "ACME HOLDINGS (DELAWARE)"


class TestAgainstEdgar:
    @pytest.mark.network
    def test_resolves_a_known_filing_to_its_index_fields(self):
        """Ground truth: Imunon's 424B5, verified against EDGAR."""
        fields = resolve_accession("0001493152-25-029712")
        assert fields == {
            "cik": 749647,
            "company": "Imunon, Inc.",
            "form": "424B5",
            "filing_date": date(2025, 12, 31),
            "related_entities": [],
        }

    @pytest.mark.network
    def test_filing_date_is_a_date_not_the_string_efts_returns(self):
        """The quarterly index yields datetime.date and callers compare against
        one. EFTS returns "2025-12-31"; handing that through unparsed changes
        Filing.filing_date's type on a path users cannot see."""
        filing = _filing_from_efts("0001493152-25-029712")
        assert filing.filing_date == date(2025, 12, 31)
        assert isinstance(filing.filing_date, date)

    @pytest.mark.network
    def test_pre_2001_accession_is_a_miss_and_the_index_still_resolves_it(self):
        """EFTS starts in 2001. This is why the index route cannot be removed:
        a 1997 filing misses here and must still come back from get_filings."""
        from edgar import get_by_accession_number

        assert resolve_accession("0000912057-97-011160") is None

        filing = get_by_accession_number("0000912057-97-011160")
        assert filing is not None
        assert filing.cik == 225261
        assert filing.form == "10-Q"
        assert str(filing.filing_date) == "1997-03-31"
