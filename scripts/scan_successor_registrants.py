"""
Scan recent 8-K12B / 8-K12G3 filings for successor registrants to review (GH #1821).

``edgar/reference/data/successor_registrants.csv`` lists successions reviewed by hand;
for those, ``get_facts()`` merges the predecessor's history. This script finds new
succession filings, suggests a predecessor, compares the two CIKs' facts, and files one
GitHub issue per succession, labelled ``successor-review``. A person decides, and adding
a row is a pull request.

A person decides because nothing automatic is good enough. Across 119 successions from
2023 to 2026, same-agent same-day accessions plus name similarity found the predecessor
at about 64% precision, and 19 of 31 pairs with shared facts conflict (mergers,
partnership-to-corporation conversions). A merger can still pass the fact check:
Paramount Skydance differs on 4.97% of shared facts.

The issues hold the state:
- a succession that has an issue, open or closed, is not filed again; closing it is the decision
- an open issue is re-checked every run and gets a comment when the comparison changes,
  because a new successor usually has no facts until its first 10-Q
- an open issue whose successor has been added to the table is closed

Usage:
    python scripts/scan_successor_registrants.py --days 14 --dry-run
    python scripts/scan_successor_registrants.py --days 14 --repo dgunning/edgartools

Needs EDGAR_IDENTITY. Filing issues needs the gh CLI and GH_TOKEN.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from rapidfuzz import fuzz

SUCCESSION_FORMS = ["8-K12B", "8-K12B/A", "8-K12G3", "8-K12G3/A"]
LABEL = "successor-review"
SEQUENCE_WINDOW = 30      # the predecessor's own 8-K is usually a few accessions away
NAME_MATCH = 70           # rapidfuzz token_set_ratio on normalized names
MAX_CANDIDATES = 5
MAX_NEAREST = 3           # unnamed fallbacks, shown only when no name matches
MIN_OVERLAP = 20          # shared facts needed before agreement means anything
MAX_DIFFERING = 0.05      # continuations differ on at most ~5% of shared facts

ACCESSION_RE = re.compile(r"\d{10}-\d{2}-\d{6}")
STATE_RE = re.compile(r"<!-- succession: (\{.*?\}) -->")
DIGEST_RE = re.compile(r"<!-- scan-digest: ([0-9a-f]{12}) -->")
_STATE_SUFFIX = re.compile(r"\s*/[a-z]{2,3}/?\s*$")   # "LENNAR CORP /NEW/", "INC./MD/", not "RE/MAX"
# What an old registrant files the day its successor takes over: post-effective amendments
# moving its registration statements, and deregistration (Navient, RE/MAX, Exxon Mobil)
WIND_DOWN_FORMS = {"S-8 POS", "POS AM", "POSASR", "POS EX", "15-12B", "15-12G", "15-15D", "25", "25-NSE"}
_NAME_NOISE = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|holdings?|holdco|parent|group|plc|ltd|limited|"
    r"n\.?v|s\.?a|ag|lp|l\.p|llc|new|old|the|de|del)\b\.?")


def normalize_name(name: str) -> str:
    """Drop legal-form and reorganization words so successor and predecessor names compare."""
    name = (name or "").lower()
    while _STATE_SUFFIX.search(name):
        name = _STATE_SUFFIX.sub("", name)
    name = _NAME_NOISE.sub(" ", name)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", name).split())


@dataclass
class Candidate:
    cik: int
    name: str
    accession: str
    distance: int
    name_score: float
    forms: Tuple[str, ...] = ()

    @property
    def winding_down(self) -> bool:
        return bool(WIND_DOWN_FORMS.intersection(self.forms))


def find_candidates(succession: dict, same_day_rows: Iterable[dict]) -> List[Candidate]:
    """
    Suggest predecessors: filers on the same day, through the same filing agent, a few
    accessions away. A candidate counts when its name resembles the successor's or it
    filed wind-down forms that day; the nearest accessions, which catch renames such as
    Bunge Ltd -> Bunge Global SA, are shown only when nothing counts, because most of
    them are unrelated filers.
    """
    same_day_rows = list(same_day_rows)
    forms_by_cik: Dict[int, set] = {}
    for row in same_day_rows:
        forms_by_cik.setdefault(row["cik"], set()).add(row["form"])
    prefix, _, sequence = succession["accession_number"].split("-")
    successor_name = normalize_name(succession["company"])
    best: Dict[int, Candidate] = {}
    for row in same_day_rows:
        if row["cik"] == succession["cik"]:
            continue
        row_prefix, _, row_sequence = row["accession_number"].split("-")
        distance = abs(int(row_sequence) - int(sequence))
        if row_prefix != prefix or distance > SEQUENCE_WINDOW:
            continue
        score = fuzz.token_set_ratio(successor_name, normalize_name(row["company"]))
        candidate = Candidate(row["cik"], row["company"], row["accession_number"], distance, score,
                              tuple(sorted(forms_by_cik.get(row["cik"], ()))))
        current = best.get(row["cik"])
        if current is None or (score, -distance) > (current.name_score, -current.distance):
            best[row["cik"]] = candidate
    def counts(c):
        return c.name_score >= NAME_MATCH or c.winding_down
    named = sorted((c for c in best.values() if counts(c)),
                   key=lambda c: (-(c.name_score >= NAME_MATCH), -c.winding_down, -c.name_score, c.distance))
    nearest = sorted((c for c in best.values() if not counts(c)), key=lambda c: c.distance)
    return named[:MAX_CANDIDATES] if named else nearest[:MAX_NEAREST]


def fact_values(facts_json: Optional[dict]) -> Dict[Tuple, object]:
    """One value per (taxonomy, concept, unit, start, end) from a companyfacts JSON, dei excluded."""
    values: Dict[Tuple, object] = {}
    for taxonomy, concepts in (facts_json or {}).get("facts", {}).items():
        if taxonomy == "dei":
            continue
        for concept, body in concepts.items():
            for unit, rows in body.get("units", {}).items():
                for row in rows:
                    values.setdefault((taxonomy, concept, unit, row.get("start"), row.get("end")), row.get("val"))
    return values


@dataclass
class Comparison:
    successor_facts: int
    predecessor_facts: int
    overlap: int
    differing: int

    @property
    def differing_share(self) -> float:
        return self.differing / self.overlap if self.overlap else 0.0


def _same_value(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-9 * max(abs(a), abs(b))
    return a == b


def compare_facts(successor_values: Dict[Tuple, object], predecessor_values: Dict[Tuple, object]) -> Comparison:
    shared = successor_values.keys() & predecessor_values.keys()
    differing = sum(1 for key in shared if not _same_value(successor_values[key], predecessor_values[key]))
    return Comparison(len(successor_values), len(predecessor_values), len(shared), differing)


def verdict(comparison: Optional[Comparison]) -> str:
    if comparison is None or comparison.successor_facts == 0:
        return "waiting for facts"
    if comparison.predecessor_facts == 0:
        return "candidate has no facts"
    if comparison.overlap < MIN_OVERLAP:
        return "waiting for facts"
    if comparison.differing_share <= MAX_DIFFERING:
        return "facts agree"
    return "facts conflict"


@dataclass
class Profile:
    tickers: List[str] = field(default_factory=list)
    latest_periodic: str = "none"
    first_periodic_date: Optional[str] = None


def has_own_history(successor: Profile, succession: dict) -> bool:
    """A successor that filed a 10-K or 10-Q before the succession already holds its history
    (ONEOK, or Kimco's old CIK): there is nothing to merge."""
    return bool(successor.first_periodic_date) and successor.first_periodic_date < str(succession["filing_date"])


@dataclass
class Review:
    succession: dict
    successor: Profile
    rows: List[Tuple[Candidate, Optional[Comparison], Profile]]


@lru_cache(maxsize=256)
def _load_facts(cik: int) -> Optional[dict]:
    from edgar.entity.entity_facts import download_company_facts_from_sec
    from edgar.exceptions import CompanyFactsNotFoundError
    try:
        return download_company_facts_from_sec(cik)
    except CompanyFactsNotFoundError:
        return None


@lru_cache(maxsize=256)
def _profile(cik: int) -> Profile:
    from edgar import Company
    company = Company(cik)
    periodic = company.get_filings(form=["10-K", "10-Q", "20-F", "40-F"], amendments=False)
    latest = periodic.latest()
    dates = periodic.data.column("filing_date").to_pylist() if latest else []
    return Profile(list(company.tickers or []), f"{latest.form} {latest.filing_date}" if latest else "none",
                   str(min(dates)) if dates else None)


@lru_cache(maxsize=64)
def _same_day_rows(filing_date: str) -> Tuple[dict, ...]:
    from edgar import get_filings
    filings = get_filings(filing_date=filing_date)
    return tuple(filings.data.to_pylist()) if filings is not None else ()


def review_succession(succession: dict,
                      same_day_rows: Iterable[dict],
                      load_facts: Callable[[int], Optional[dict]] = _load_facts,
                      profile: Callable[[int], Profile] = _profile) -> Review:
    successor_values = fact_values(load_facts(succession["cik"]))
    rows = []
    for candidate in find_candidates(succession, same_day_rows):
        predecessor_json = load_facts(candidate.cik)
        comparison = (compare_facts(successor_values, fact_values(predecessor_json))
                      if successor_values and predecessor_json else None)
        if comparison is None and successor_values:
            comparison = Comparison(len(successor_values), 0, 0, 0)
        rows.append((candidate, comparison, profile(candidate.cik)))
    return Review(succession, profile(succession["cik"]), rows)


def _filing_url(succession: dict) -> str:
    accession = succession["accession_number"]
    return (f"https://www.sec.gov/Archives/edgar/data/{succession['cik']}/"
            f"{accession.replace('-', '')}/{accession}-index.html")


def render_table(review: Review) -> str:
    if not review.rows:
        return "No filer used the same filing agent within 30 accessions on that day. Read the filing for the predecessor."
    lines = []
    if not any(c.name_score >= NAME_MATCH or c.winding_down for c, _, _ in review.rows):
        lines += ["No same-day filer's name resembles the successor's, and none filed wind-down forms. "
                  "These are the nearest accessions and are usually unrelated; read the filing.", ""]
    lines += ["| Predecessor candidate | Name match | Accession distance | Same-day forms | Shared facts | Differing | Latest 10-K/10-Q | Result |",
              "|---|---|---|---|---|---|---|---|"]
    for candidate, comparison, candidate_profile in review.rows:
        shared = comparison.overlap if comparison else "-"
        differing = (f"{comparison.differing} ({comparison.differing_share:.1%})"
                     if comparison and comparison.overlap else "-")
        forms = ", ".join(candidate.forms[:6]) + (" …" if len(candidate.forms) > 6 else "")
        lines.append(f"| {candidate.name} (CIK {candidate.cik}) | {candidate.name_score:.0f} | {candidate.distance} | "
                     f"{forms} | {shared} | {differing} | {candidate_profile.latest_periodic} | {verdict(comparison)} |")
    return "\n".join(lines)


def digest(table: str) -> str:
    return hashlib.sha256(table.encode()).hexdigest()[:12]


def issue_title(succession: dict) -> str:
    return (f"Successor registrant to review: {succession['company']} (CIK {succession['cik']}), "
            f"{succession['form']} {succession['accession_number']}")


def issue_body(review: Review) -> str:
    s = review.succession
    state = json.dumps({k: str(s[k]) if k == "filing_date" else s[k]
                        for k in ("form", "company", "cik", "filing_date", "accession_number")})
    table = render_table(review)
    tickers = ", ".join(review.successor.tickers) or "none"
    return f"""A succession filing to review for `edgar/reference/data/successor_registrants.csv` (GH #1821).

- **Filing:** [{s['form']} {s['accession_number']}]({_filing_url(s)}), filed {s['filing_date']}
- **Successor:** {s['company']}, CIK {s['cik']}, tickers {tickers}, latest 10-K/10-Q: {review.successor.latest_periodic}

### Predecessor candidates

{table}

### Deciding

Add a row to the table only when all of these hold:

1. The successor holds the ticker now, and the predecessor stopped filing 10-Ks and 10-Qs at the succession.
2. At least {MIN_OVERLAP} shared facts, and at most {MAX_DIFFERING:.0%} of them differ.
3. The 8-K12B describes a holding-company reorganization, redomicile or conversion, not a merger with another business.

If the result is "waiting for facts", leave this open: it is re-checked every week and gets a comment when the
successor's first 10-Q arrives. If it is not a continuation, close it with the reason.

<!-- succession: {state} -->
<!-- scan-digest: {digest(table)} -->
"""


def recheck_comment(review: Review, today: date) -> str:
    table = render_table(review)
    return f"### Re-checked {today}\n\n{table}\n\n<!-- scan-digest: {digest(table)} -->\n"


def parse_state(body: str) -> Optional[dict]:
    match = STATE_RE.search(body or "")
    return json.loads(match.group(1)) if match else None


def latest_digest(issue: dict) -> Optional[str]:
    texts = [issue.get("body") or ""] + [c.get("body") or "" for c in issue.get("comments") or []]
    found = [d for text in texts for d in DIGEST_RE.findall(text)]
    return found[-1] if found else None


def accession_of(title: str) -> Optional[str]:
    match = ACCESSION_RE.search(title or "")
    return match.group(0) if match else None


def plan(successions: List[dict], issues: List[dict], reviewed_ciks: Iterable[int]):
    """Split the work: successions to file, open issues to close, open issues to re-check."""
    reviewed = set(reviewed_ciks)
    known_accessions = {accession_of(issue["title"]) for issue in issues}
    # One issue per successor: an 8-K12B/A or a second filing adds nothing to review
    known_ciks = {state["cik"] for state in map(lambda i: parse_state(i.get("body")), issues) if state}
    to_file = []
    for s in successions:
        if s["cik"] in reviewed or s["cik"] in known_ciks or s["accession_number"] in known_accessions:
            continue
        known_ciks.add(s["cik"])
        to_file.append(s)
    to_close, to_recheck = [], []
    for issue in issues:
        if issue.get("state", "").upper() != "OPEN":
            continue
        state = parse_state(issue.get("body"))
        if state is None:
            continue
        (to_close if state["cik"] in reviewed else to_recheck).append((issue, state))
    return to_file, to_close, to_recheck


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def _list_issues(repo: str) -> List[dict]:
    return json.loads(_gh("issue", "list", "--repo", repo, "--label", LABEL, "--state", "all",
                          "--limit", "1000", "--json", "number,title,state,body,comments"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--days", type=int, default=14, help="look back this many days (default 14)")
    parser.add_argument("--repo", help="file issues in this GitHub repo, e.g. dgunning/edgartools")
    parser.add_argument("--dry-run", action="store_true", help="print what would be filed")
    args = parser.parse_args(argv)
    if not args.repo and not args.dry_run:
        parser.error("pass --repo to file issues, or --dry-run")

    from edgar import get_filings
    from edgar.reference.successors import _get_predecessor_lookup

    today = date.today()
    found = get_filings(form=SUCCESSION_FORMS, filing_date=f"{today - timedelta(days=args.days)}:{today}")
    successions = found.data.to_pylist() if found is not None else []
    issues = _list_issues(args.repo) if args.repo else []
    to_file, to_close, to_recheck = plan(successions, issues, _get_predecessor_lookup())
    print(f"{len(successions)} succession filings in the last {args.days} days; "
          f"{len(to_file)} to file, {len(to_close)} to close, {len(to_recheck)} to re-check")

    if args.repo and not args.dry_run:
        subprocess.run(["gh", "label", "create", LABEL, "--repo", args.repo, "--color", "1d76db",
                        "--description", "A succession filing to review for successor_registrants.csv"],
                       capture_output=True)

    for succession in to_file:
        if has_own_history(_profile(succession["cik"]), succession):
            print(f"skip {succession['company']} (CIK {succession['cik']}): it filed 10-K/10-Q reports before the succession")
            continue
        review = review_succession(succession, _same_day_rows(str(succession["filing_date"])))
        title, body = issue_title(succession), issue_body(review)
        if args.dry_run:
            print(f"\n## {title}\n\n{body}")
        else:
            _gh("issue", "create", "--repo", args.repo, "--label", LABEL, "--title", title, "--body", body)

    for issue, _ in to_close:
        message = "Its successor is now in `successor_registrants.csv`."
        if args.dry_run:
            print(f"\nwould close #{issue['number']}: {message}")
        else:
            _gh("issue", "close", str(issue["number"]), "--repo", args.repo, "--comment", message)

    for issue, state in to_recheck:
        review = review_succession(state, _same_day_rows(state["filing_date"]))
        comment = recheck_comment(review, today)
        if DIGEST_RE.search(comment).group(1) == latest_digest(issue):
            continue
        if args.dry_run:
            print(f"\nwould comment on #{issue['number']}:\n{comment}")
        else:
            _gh("issue", "comment", str(issue["number"]), "--repo", args.repo, "--body", comment)
    return 0


if __name__ == "__main__":
    sys.exit(main())
