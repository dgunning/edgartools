"""A cassette test reads its submissions from its cassette, not from the session memo.

tests/conftest.py memoizes SEC submissions per CIK for the whole session. It used
to serve that memo before vcr saw the request, so a ``@pytest.mark.vcr`` test that
ran after a live test of the same company replayed the live download instead of
its recording. test_issue_1817_edgar_ownership_insiders::test_days_leaves_out_older_form4s
(NVIDIA, cassette recorded 2026-11-02) then saw Form 4 0001197647-26-000013, filed
2026-11-06, whenever another test had fetched NVIDIA's submissions live first.

Origin: bead edgartools-k7mi8.18 (no GitHub issue).
"""
import pytest

from edgar.entity import submissions

NVIDIA_CIK = 1045810


@pytest.fixture
def vcr_cassette_name():
    # NVIDIA's submissions as SEC served them on 2026-11-02.
    return "test_days_leaves_out_older_form4s"


@pytest.fixture
def memo_holds_a_later_download(cache_sec_submissions_for_session):
    """Put a stand-in for a live download from a later day into the session memo."""
    memo = cache_sec_submissions_for_session["memo"]
    previous = memo.get(NVIDIA_CIK, None)
    had_entry = NVIDIA_CIK in memo
    memo[NVIDIA_CIK] = {"cik": "1045810", "name": "LIVE DOWNLOAD FROM A LATER DAY"}
    try:
        yield
    finally:
        if had_entry:
            memo[NVIDIA_CIK] = previous
        else:
            memo.pop(NVIDIA_CIK, None)


@pytest.mark.fast
@pytest.mark.vcr
def test_cassette_test_reads_submissions_from_its_cassette(memo_holds_a_later_download):
    submissions_json = submissions.download_entity_submissions_from_sec(NVIDIA_CIK)

    assert submissions_json["name"] == "NVIDIA CORP"
    recent = submissions_json["filings"]["recent"]
    # The newest filing in the 2026-11-02 recording is a Form 4/A filed 2026-10-13;
    # nothing filed after the recording day (such as the 2026-11-06 Form 4) is in it.
    assert (recent["form"][0], recent["accessionNumber"][0]) == ("4/A", "0002152188-26-000007")
    assert max(recent["filingDate"]) == "2026-10-13"
