"""Six individuals were classified as companies because their names contain "l p".

GitHub Issue: https://github.com/dgunning/edgartools/issues/1019

``_name_suggests_company`` carried the spaced legal suffix ``L P`` as a loose
substring, and a substring does not care where a word ends. "Michael P." is
``MICHAE|L P|.``; so is "Daniel Paul", "Jill P. Meyer", "O'NEIL PATRICK" and
"MICHAEL PHILIP". Every one of them scanned as a limited partnership.

The six CIKs below are the ones on the report, checked against SEC submissions
data on 2026-08-10 — the names are what the SEC returns, not paraphrases. The
assertions are on the name heuristic rather than on ``Entity(cik)`` so the guard
holds without the network; ``is_individual`` follows because the name is the
only company-shaped signal any of these filers has.

``L L C`` had the identical defect and was fixed with it: "MICHAEL L COOPER" is
``MICHAE|L L C|OOPER``. It was never reported, which is the point — the same
substring bug in the same set, one keyword over.
"""
import pytest

from edgar.entity.constants import _classify_is_individual, _name_suggests_company

# CIK -> name exactly as SEC submissions data returns it.
REPORTED_INDIVIDUALS = {
    1306539: "Myers Daniel P",
    1564926: "O'NEIL PATRICK R.",
    1571320: "Regan Daniel Paul",
    1785884: "Pratt Jill P. Meyer",
    2037927: "Wyatt Michael P.",
    2097014: "HARWOOD MICHAEL PHILIP",
}


@pytest.mark.parametrize("cik,name", sorted(REPORTED_INDIVIDUALS.items()))
def test_reported_individuals_are_not_companies(cik, name):
    assert _name_suggests_company(name) is False
    assert _classify_is_individual(name=name, cik=cik) is True


@pytest.mark.parametrize("name", [
    "MICHAEL L COOPER",   # MICHAE|L L C|OOPER
    "DANIEL L CHEN",
    "HALL L CARTER",
    "POWELL L CRAIG",
])
def test_spaced_llc_does_not_match_across_words(name):
    assert _name_suggests_company(name) is False


@pytest.mark.parametrize("name", [
    "ACME L P",
    "BLACKSTONE HOLDINGS L P",
    "ACME L L C",
    "CARLYLE PARTNERS VI L P",
])
def test_spaced_suffixes_still_detect_companies(name):
    assert _name_suggests_company(name) is True


@pytest.mark.parametrize("name", [
    "Ardagh Metal Packaging S.A.",
    "CENTRAL PUERTO S.A.",
    "Greek Organisation of Football Prognostics S.A.",
])
def test_punctuated_sa_survives_the_lp_removal(name):
    """These three were detected only by the accidental "L P" in "CENTRA|L P|UERTO".

    Of the 7,990 companies in the ticker file they were the only ones whose name
    signal came from the bug, because the strict path splits on ``\\W+`` and so
    sees ``{S, A}`` where the name says ``S.A.``. Removing the accident without
    adding the suffix would have quietly cost them their name signal.
    """
    assert _name_suggests_company(name) is True
