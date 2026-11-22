"""Offline checks for scripts/scan_successor_registrants.py, the weekly succession scan (GH #1821).

The filing rows are real: ExxonMobil Holdings Corp's 8-K12B 0001193125-26-291990 and
Exxon Mobil Corp's own 8-K 0001193125-26-291986, both filed 2026-07-01 through
Donnelley; Bunge Global SA's 8-K12G3 0001104659-23-113123 (2023-11-01).
"""
import importlib.util
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "scan_successor_registrants.py"
_spec = importlib.util.spec_from_file_location("scan_successor_registrants", SCRIPT)
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

XOM_SUCCESSION = {"form": "8-K12B", "company": "ExxonMobil Holdings Corp", "cik": 2115436,
                  "filing_date": date(2026, 7, 1), "accession_number": "0001193125-26-291990"}


def _row(cik, company, accession, form="8-K"):
    return {"form": form, "company": company, "cik": cik, "filing_date": date(2026, 7, 1), "accession_number": accession}


XOM_DAY = [
    _row(2115436, "ExxonMobil Holdings Corp", "0001193125-26-291990", "8-K12B"),
    _row(34088, "EXXON MOBIL CORP", "0001193125-26-291986"),
    _row(34088, "EXXON MOBIL CORP", "0001193125-26-291995", "S-8 POS"),
    _row(886982, "GOLDMAN SACHS GROUP INC", "0001193125-26-291989", "424B2"),   # same agent, unrelated
    _row(320193, "Apple Inc.", "0000320193-26-000050"),                       # another agent
    _row(1800, "ABBOTT LABORATORIES", "0001193125-26-292100"),                # same agent, too far
]


def _facts(values, taxonomy="us-gaap"):
    return {"facts": {taxonomy: {concept: {"units": {"USD": [{"start": "2025-01-01", "end": "2025-12-31", "val": v}]}}
                                 for concept, v in values.items()}}}


class TestCandidates:

    def test_the_predecessor_ranks_first(self):
        candidates = scan.find_candidates(XOM_SUCCESSION, XOM_DAY)
        assert candidates[0].cik == 34088
        assert candidates[0].distance == 4
        assert candidates[0].winding_down
        assert {c.cik for c in candidates} == {34088}

    def test_other_agents_far_accessions_and_the_successor_are_left_out(self):
        ciks = {c.cik for c in scan.find_candidates(XOM_SUCCESSION, XOM_DAY)}
        assert not ciks & {2115436, 320193, 1800}

    def test_nearest_accessions_stand_in_when_no_name_matches(self):
        succession = {"form": "8-K12G3", "company": "Bunge Global SA", "cik": 1996862,
                      "filing_date": date(2023, 11, 1), "accession_number": "0001104659-23-113123"}
        rows = [_row(1144519, "BUNGELTD", "0001104659-23-113122"),
                _row(9999, "Unrelated Trust", "0001104659-23-113140")]
        candidates = scan.find_candidates(succession, rows)
        assert [c.cik for c in candidates] == [1144519, 9999]

    @pytest.mark.parametrize("name,expected", [
        ("RE/MAX Holdings, Inc.", "re max"),
        ("LENNAR CORP /NEW/", "lennar"),
        ("COLUMBIA FINANCIAL, INC./MD/", "columbia financial"),
        ("ExxonMobil Holdings Corp", "exxonmobil"),
    ])
    def test_normalize_name(self, name, expected):
        assert scan.normalize_name(name) == expected


class TestFacts:

    def test_agreeing_facts(self):
        values = {f"C{i}": i for i in range(30)}
        comparison = scan.compare_facts(scan.fact_values(_facts(values)), scan.fact_values(_facts(values)))
        assert (comparison.overlap, comparison.differing) == (30, 0)
        assert scan.verdict(comparison) == "facts agree"

    def test_conflicting_facts(self):
        successor = {f"C{i}": i for i in range(30)}
        predecessor = {f"C{i}": i + (100 if i < 3 else 0) for i in range(30)}
        comparison = scan.compare_facts(scan.fact_values(_facts(successor)), scan.fact_values(_facts(predecessor)))
        assert comparison.differing == 3
        assert scan.verdict(comparison) == "facts conflict"   # 10% > 5%

    def test_dei_is_not_compared(self):
        assert scan.fact_values(_facts({"EntityPublicFloat": 1}, taxonomy="dei")) == {}

    def test_too_few_shared_facts_waits(self):
        values = {f"C{i}": i for i in range(5)}
        comparison = scan.compare_facts(scan.fact_values(_facts(values)), scan.fact_values(_facts(values)))
        assert scan.verdict(comparison) == "waiting for facts"
        assert scan.verdict(None) == "waiting for facts"


def test_review_compares_each_candidate():
    facts = {2115436: _facts({f"C{i}": i for i in range(25)}), 34088: _facts({f"C{i}": i for i in range(40)})}
    review = scan.review_succession(XOM_SUCCESSION, XOM_DAY, load_facts=facts.get,
                                    profile=lambda cik: scan.Profile(["XOM"] if cik == 2115436 else []))
    candidate, comparison, _ = review.rows[0]
    assert candidate.cik == 34088
    assert (comparison.overlap, comparison.differing) == (25, 0)
    assert "| facts agree |" in scan.render_table(review)


def test_a_successor_with_earlier_reports_has_its_own_history():
    assert scan.has_own_history(scan.Profile(first_periodic_date="1999-05-01"), XOM_SUCCESSION)
    assert not scan.has_own_history(scan.Profile(first_periodic_date="2026-08-03"), XOM_SUCCESSION)
    assert not scan.has_own_history(scan.Profile(), XOM_SUCCESSION)


class TestIssueState:

    def _review(self):
        return scan.Review(XOM_SUCCESSION, scan.Profile(["XOM"]), [])

    def test_the_body_carries_the_succession(self):
        body = scan.issue_body(self._review())
        state = scan.parse_state(body)
        assert state["cik"] == 2115436 and state["accession_number"] == "0001193125-26-291990"
        assert state["filing_date"] == "2026-07-01"
        assert "0001193125-26-291990" in scan.issue_title(XOM_SUCCESSION)

    def test_an_unchanged_recheck_matches_the_last_digest(self):
        review = self._review()
        issue = {"body": scan.issue_body(review), "comments": []}
        comment = scan.recheck_comment(review, date(2026, 11, 3))
        assert scan.DIGEST_RE.search(comment).group(1) == scan.latest_digest(issue)

    def test_plan(self):
        def issue(number, succession, state):
            review = scan.Review(succession, scan.Profile(), [])
            return {"number": number, "title": scan.issue_title(succession), "state": state,
                    "body": scan.issue_body(review)}

        navient = {**XOM_SUCCESSION, "company": "Navient Holdings, Inc.", "cik": 2152623,
                   "accession_number": "0001193125-26-436899"}
        remax = {**XOM_SUCCESSION, "company": "Real REMAX Group Inc.", "cik": 2136387,
                 "accession_number": "0001104659-26-100334"}
        remax_amendment = {**remax, "form": "8-K12B/A", "accession_number": "0001104659-26-100999"}
        new = {**XOM_SUCCESSION, "company": "New Co", "cik": 1, "accession_number": "0000000001-26-000001"}
        new_amendment = {**new, "form": "8-K12B/A", "accession_number": "0000000001-26-000002"}

        issues = [issue(1, navient, "OPEN"), issue(2, remax, "CLOSED"), issue(3, XOM_SUCCESSION, "OPEN")]
        to_file, to_close, to_recheck = scan.plan(
            [XOM_SUCCESSION, navient, remax_amendment, new, new_amendment], issues, reviewed_ciks=[2115436])

        assert [s["accession_number"] for s in to_file] == [new["accession_number"]]
        assert [i["number"] for i, _ in to_close] == [3]      # XOM is in the table now
        assert [i["number"] for i, _ in to_recheck] == [1]    # a closed issue is a decision


def test_the_script_refuses_to_run_without_a_destination():
    with pytest.raises(SystemExit):
        scan.main([])
