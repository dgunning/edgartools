"""EFTS search results kept the raw display name on ``EFTSResult.company``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1708

``_parse_hit`` copied ``display_names[0]`` unchanged. A hit shaped like
NVIDIA's FY2024 10-K (accession ``0001045810-24-000029``) therefore left
``NVIDIA CORP  (NVDA)  (CIK 0001045810)`` in ``company`` while ``cik`` already
held ``0001045810``. ``resolve_accession`` in the same module already runs that
string through ``_clean_display_name``. The cleaner leaves an empty string
empty and does not accept ``None``, so a missing or empty name stays missing
or empty. Source spelling and a single-spaced parenthetical that is part of
the name are kept. Offline: the hits are dicts shaped like an EFTS response.
"""

import copy

import pytest

from edgar.search.efts import EFTSSearch, _parse_hit

pytestmark = pytest.mark.fast

# Display string, accession, form, filing date, score and id are the
# reproduction in GH #1708 for NVIDIA's FY2024 10-K. Nothing else is claimed
# as a value read from that filing.
NVIDIA_HIT = {
    "_id": "0001045810-24-000029:nvda-20240128.htm",
    "_score": 12.5,
    "_source": {
        "adsh": "0001045810-24-000029",
        "form": "10-K",
        "file_date": "2024-02-21",
        "display_names": ["NVIDIA CORP  (NVDA)  (CIK 0001045810)"],
        "ciks": ["0001045810"],
    },
}


def _hit(display_names, ciks=None, **source):
    body = {
        "adsh": "0001045810-24-000029",
        "form": "10-K",
        "file_date": "2024-02-21",
        "ciks": ["0001045810"] if ciks is None else ciks,
    }
    body.update(source)
    if display_names is not _OMIT:
        body["display_names"] = display_names
    return {"_id": "0001045810-24-000029:nvda-20240128.htm", "_score": 1.0, "_source": body}


_OMIT = object()


def test_nvidia_company_is_cleaned_and_the_rest_of_the_hit_is_unchanged():
    hit = copy.deepcopy(NVIDIA_HIT)
    result = _parse_hit(hit)

    assert result.company == "NVIDIA CORP"
    assert result.cik == "0001045810"
    assert result.accession_number == "0001045810-24-000029"
    assert result.form == "10-K"
    assert result.filed == "2024-02-21"
    assert result.period is None
    assert result.score == 12.5
    assert result.document_id == "nvda-20240128.htm"
    assert hit == NVIDIA_HIT

    assert repr(result) == "EFTSResult(12.5 | 10-K | NVIDIA CORP | 2024-02-21)"
    context = EFTSSearch(query="nvidia", total=1, results=[result]).to_context()
    assert "12.5 | 10-K |  | NVIDIA CORP | 2024-02-21" in context
    assert "(NVDA)" not in context
    assert "(CIK" not in context

    frame = EFTSSearch(query="nvidia", total=1, results=[result]).to_filings().to_pandas()
    assert frame.iloc[0]["company"] == "NVIDIA CORP"
    assert frame.iloc[0]["form"] == "10-K"
    assert frame.iloc[0]["accession_number"] == "0001045810-24-000029"


def test_other_result_metadata_round_trips_beside_the_cleaned_name():
    """Fixture fields, not values read from the filing. They must pass through."""
    result = _parse_hit(_hit(
        ["NVIDIA CORP  (NVDA)  (CIK 0001045810)"],
        period_ending="2024-01-28",
        file_type="EX-99",
        file_description="fixture description",
        items=["2.02"],
        sics=["9999"],
        biz_locations=["Fixture City"],
        biz_states=["ZZ"],
        inc_states=["YY"],
    ))
    assert result.company == "NVIDIA CORP"
    assert result.cik == "0001045810"
    assert (result.period, result.file_type, result.file_description) == (
        "2024-01-28", "EX-99", "fixture description")
    assert result.items == ["2.02"]
    assert (result.sic, result.location, result.state, result.inc_state) == (
        "9999", "Fixture City", "ZZ", "YY")
    assert repr(result) == "EFTSResult(1.0 | 10-K | EX-99 | NVIDIA CORP | 2024-02-21)"


@pytest.mark.parametrize("display, expected", [
    ("Apple Inc.", "Apple Inc."),
    ("Airbnb, Inc.  (ABNB)  (CIK 0001559720)", "Airbnb, Inc."),
    ("Imunon, Inc.  (IMNN)  (CIK 0000749647)", "Imunon, Inc."),
    ("BANK OF AMERICA CORP /DE/  (CIK 0000070858)", "BANK OF AMERICA CORP /DE/"),
    ("ACME HOLDINGS (DELAWARE)", "ACME HOLDINGS (DELAWARE)"),
    ("ACME HOLDINGS (DELAWARE)  (CIK 0000000001)", "ACME HOLDINGS (DELAWARE)"),
])
def test_source_spelling_and_single_spaced_parentheses_survive(display, expected):
    result = _parse_hit(_hit([display]))
    assert result.company == expected
    assert result.cik == "0001045810"


def test_multi_filer_keeps_the_first_name_and_its_cik():
    """BofA Finance LLC 424B2 0001918704-24-002559 is filed with its parent.
    The first filer stays the result; the second name is not substituted.
    """
    result = _parse_hit(_hit(
        ["BofA Finance LLC  (CIK 0001682472)",
         "BANK OF AMERICA CORP /DE/  (CIK 0000070858)"],
        ciks=["0001682472", "0000070858"],
        adsh="0001918704-24-002559",
        form="424B2",
        file_date="2024-12-31",
    ))
    assert result.company == "BofA Finance LLC"
    assert result.cik == "0001682472"
    assert result.accession_number == "0001918704-24-002559"
    assert result.form == "424B2"
    assert result.filed == "2024-12-31"


@pytest.mark.parametrize("display_names", [_OMIT, [], None])
def test_missing_name_stays_none_and_does_not_take_another_entity(display_names):
    result = _parse_hit(_hit(display_names, ciks=["0001045810", "0000070858"]))
    assert result.company is None
    assert result.cik == "0001045810"


def test_empty_string_name_stays_empty_and_does_not_take_the_next_filer():
    result = _parse_hit(_hit(
        ["", "BANK OF AMERICA CORP /DE/  (CIK 0000070858)"],
        ciks=["0001045810", "0000070858"],
    ))
    assert result.company == ""
    assert result.cik == "0001045810"


def test_none_name_stays_none():
    """``_clean_display_name`` rejects ``None``. A present null name stays null."""
    result = _parse_hit(_hit([None], ciks=["0001045810"]))
    assert result.company is None
    assert result.cik == "0001045810"
