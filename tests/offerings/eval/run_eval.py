"""
Offerings extraction eval harness — Tier A (coverage & validity).

Runs the offerings extractors over the frozen corpus (corpus.json), buckets each
facet's output, and prints a dashboard plus a failure catalog. This is the
systematic version of the manual "sample → bucket → trace the biggest bucket"
loop that found edgartools-fu3x/2w5y/2h4c/zxnj.

    python tests/offerings/eval/run_eval.py                # full corpus
    python tests/offerings/eval/run_eval.py --facet fee_capacity
    python tests/offerings/eval/run_eval.py --json out.json # machine-readable

Buckets per facet:
    ok       clean, usable value
    null     no value (may be legitimate — see cluster reason)
    deferred legitimately indeterminate (fee capacity on pay-as-you-go ASRs)
    bad      garbage or out-of-range  <-- the thing we never want to ship
    error    extractor raised

Metrics:  coverage = (ok + deferred) / n     bad_rate = (bad + error + suspect) / n
(a justified `deferred` is a correct resolution — an indeterminate pay-as-you-go
shelf has no determinate amount — so it counts toward coverage, not against it.)

Tier B (self-check oracles: fee cross-check, lifecycle consistency) plugs into
each facet via the `ORACLES` hook: an `ok` value is cross-checked against the
filing's own internal redundancy (fee / rate = aggregate; takedown dates within
the shelf's effective window). A failed oracle demotes `ok` -> `suspect`.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

CORPUS_PATH = Path(__file__).with_name("corpus.json")

OUTLIER_HIGH = 1e12  # > $1T registered capacity is implausible


# --------------------------------------------------------------------------
# Facet definitions: extract a value from a filing, classify it into a bucket.
# Each returns (bucket, value, reason). Keep classifiers pure so Tier B oracles
# can wrap them.
# --------------------------------------------------------------------------

def _facet_fee_capacity(filing):
    from edgar.offerings._fee_table import extract_registration_fee_table, _get_filing_fees_attachment
    ft = extract_registration_fee_table(filing)
    if ft is None:
        reason = "no EX-FILING-FEES attachment" if _get_filing_fees_attachment(filing) is None \
            else "attachment present, no table parsed"
        return "null", None, reason, None
    val = ft.total_offering_amount
    if val is None:
        if getattr(ft, "fee_deferred", False):
            return "deferred", None, "indeterminate (pay-as-you-go fees)", None
        att = _get_filing_fees_attachment(filing)
        return "null", None, ("no EX-FILING-FEES attachment" if att is None
                              else "attachment present, amount not found"), None
    if val == 0:
        return "bad", val, "zero offering amount", ft
    if val > OUTLIER_HIGH:
        return "bad", val, "implausible (> $1T)", ft
    return "ok", val, "", ft


# --------------------------------------------------------------------------
# Tier B — self-check oracles. Validate a covered value against the filing's own
# internal redundancy (no labels). Return (passed | None, detail); None = the
# oracle lacked the data to judge.
# --------------------------------------------------------------------------

def _oracle_fee_crosscheck(ft, tol=0.03):
    """fee ÷ rate must reconcile with the extracted offering amount.

    For newly-registered securities sharing one fee rate, Σ fee_amount / rate is
    the registered aggregate, derived from cells independent of the offering-
    amount cell. If it doesn't match total_offering_amount within tolerance, the
    headline number was extracted from the wrong cell.
    """
    # Carry-forward and previously-paid offsets break the simple fee = aggregate
    # × rate identity on the newly-registered rows; don't judge those here.
    if ft.has_carry_forward or ft.total_fees_previously_paid:
        return None, "carry-forward / offset fees — not judged by this oracle"
    rates = {round(s.fee_rate, 8) for s in ft.securities if s.fee_rate}
    fees = [s.fee_amount for s in ft.securities if s.fee_amount]
    total = ft.total_offering_amount
    if not (total and fees and len(rates) == 1):
        return None, "insufficient data (need one fee rate + per-row fees)"
    rate = next(iter(rates))
    if rate <= 0:
        return None, "non-positive fee rate"
    implied = sum(fees) / rate
    ok = abs(implied - total) <= max(1.0, total * tol)
    return ok, f"implied={implied:,.0f} vs extracted={total:,.0f}"


def _oracle_lifecycle_consistency(lc):
    """Cross-check shelf dates against the takedowns' own filing dates.

    Two internal-redundancy checks, independent of how ``status`` is classified:

    1. Arithmetic identity — ``shelf_expires`` must equal current effectiveness
       + 3 years (Rule 415(a)(5)). A regression guard on the date anchoring that
       the fu3x fix established.
    2. Takedown containment — a 424B takedown cannot legally occur after the
       shelf expires. Takedown dates come from the 424B filings; the expiry is
       derived from the EFFECT/ASR side, so a takedown past ``shelf_expires``
       exposes a mis-dated or mis-linked shelf (the exact fu3x failure mode: an
       expiry anchored too early leaves recent takedowns stranded past it).

    Deliberately does *not* flag takedowns *before* the earliest effectiveness:
    an old EFFECT scrolling out of the loaded related-filing window would falsely
    trip that, whereas recent filings (the upper bound) are never truncated.

    Returns None when there is no current-effective/expiry anchor (e.g.
    effectiveness proven only by a takedown, with the EFFECT date out of window)
    or no takedowns to cross-check against — the oracle then verified only a
    tautology, which is not independent confirmation.
    """
    from edgar.offerings.prospectus import _parse_filing_date, _plus_three_years
    exp = lc.shelf_expires
    eff = _parse_filing_date(lc.current_effective_date) if lc.current_effective_date else None
    if exp is None or eff is None:
        return None, "no current-effective/expiry anchor"
    if _plus_three_years(eff) != exp:
        return False, f"shelf_expires {exp} != current effective {eff} + 3y"
    td_dates = [d for d in (_parse_filing_date(f.filing_date) for f in lc.takedowns) if d]
    if not td_dates:
        return None, "arithmetic identity holds; no takedowns to cross-check"
    late = [d for d in td_dates if d > exp]
    if late:
        return False, f"{len(late)} takedown(s) after expiry {exp} (latest {max(late)})"
    return True, f"{len(td_dates)} takedowns <= expiry {exp}"


ORACLES = {
    "fee_capacity": _oracle_fee_crosscheck,
    "shelf_status": _oracle_lifecycle_consistency,
}


def _prospectus(filing):
    from edgar.offerings.prospectus import Prospectus424B
    return Prospectus424B.from_filing(filing)


def _facet_lead_bookrunner(filing):
    from edgar.offerings._424b_tables import is_plausible_underwriter_name
    uw = _prospectus(filing).underwriting
    val = uw.lead_manager if uw else None
    if val is None:
        return "null", None, "no underwriting extracted", None
    if not is_plausible_underwriter_name(val):
        return "bad", val, "implausible underwriter name", None
    return "ok", val, "", None


_VALID_STATUS = {"registered", "effective", "expired", "withdrawn"}


def _facet_shelf_status(filing):
    lc = _prospectus(filing).lifecycle
    if lc is None:
        return "null", None, "no lifecycle (related filings not found)", None
    val = lc.status
    if val not in _VALID_STATUS:
        return "bad", val, "unexpected status value", None
    # Tier A date-ordering sanity (a cheap consistency guard).
    if lc.shelf_expires and lc.current_effective_date:
        from edgar.offerings.prospectus import _parse_filing_date
        eff = _parse_filing_date(lc.current_effective_date)
        if eff and lc.shelf_expires < eff:
            return "bad", val, "shelf_expires before current effective date", None
    # Hand the lifecycle to the Tier B oracle for the takedown cross-check.
    return "ok", val, "", lc


FACETS = {
    "fee_capacity": _facet_fee_capacity,
    "lead_bookrunner": _facet_lead_bookrunner,
    "shelf_status": _facet_shelf_status,
}


# --------------------------------------------------------------------------

def run(entries, only_facet=None):
    from edgar import find
    results = []
    for e in entries:
        facet = e["facet"]
        if only_facet and facet != only_facet:
            continue
        fn = FACETS.get(facet)
        if fn is None:
            continue
        ctx = None
        try:
            bucket, value, reason, ctx = fn(find(e["accession"]))
        except Exception as ex:  # noqa: BLE001 — the harness must survive any filing
            bucket, value, reason = "error", None, f"{type(ex).__name__}: {ex}"

        # Anchor ground-truth check (overrides bucket -> bad on mismatch).
        # Frontier entries are known coverage gaps: a None value is the documented
        # gap, not a regression, so it stays in its bucket (null/deferred). A
        # *present* value that disagrees with ground truth is still flagged — that
        # is the regression we want to catch once an extractor closes the gap.
        if "expected" in e and bucket in ("ok", "deferred", "null"):
            exp = e["expected"]
            if exp is None:
                if value is not None:
                    bucket, reason = "bad", f"expected None, got {value}"
            elif value is None:
                if not e.get("frontier"):
                    bucket, reason = "bad", f"expected {exp}, got None"
            elif abs(value - exp) > max(1.0, abs(exp) * 0.01):
                bucket, reason = "bad", f"expected {exp}, got {value}"

        # Tier B oracle: an internal-consistency cross-check on a covered value.
        # passed -> verified; failed -> demote ok to 'suspect'; None -> unjudged.
        verified = None
        oracle = ORACLES.get(facet)
        if oracle and bucket == "ok" and ctx is not None:
            passed, detail = oracle(ctx)
            verified = passed
            if passed is False:
                bucket, reason = "suspect", f"oracle: {detail}"

        results.append({**e, "bucket": bucket, "value": value,
                        "reason": reason, "verified": verified})
    return results


def summarize(results, include_frontier=False):
    """Bucket counts per facet.

    Frontier entries (documented coverage gaps not yet reachable by any
    extractor) are excluded by default so the ratchet measures regressions on the
    *supported* scope only — newly-added gap cases must not drag the floor down.
    Pass include_frontier=True to summarize the frontier set on its own.
    """
    by_facet = defaultdict(lambda: defaultdict(int))
    for r in results:
        if bool(r.get("frontier")) != include_frontier:
            continue
        by_facet[r["facet"]][r["bucket"]] += 1
        by_facet[r["facet"]]["n"] += 1
    return by_facet


def print_dashboard(results):
    by_facet = summarize(results)
    print("\n=== Offerings Extraction Eval — Tier A + B ===\n")
    hdr = (f"{'facet':18}{'n':>4}{'ok':>5}{'susp':>6}{'null':>6}{'defer':>7}"
           f"{'bad':>5}{'err':>5}{'coverage':>11}{'bad_rate':>10}{'verified':>10}")
    print(hdr)
    print("-" * len(hdr))
    for facet, c in sorted(by_facet.items()):
        n = c["n"]
        cov = (c["ok"] + c["deferred"]) / n if n else 0
        badr = (c["bad"] + c["error"] + c["suspect"]) / n if n else 0
        # verified = oracle-confirmed / oracle-judged (pass + fail), for this facet
        judged = [r for r in results if r["facet"] == facet and r.get("verified") is not None]
        passed = [r for r in judged if r["verified"]]
        vrate = f"{len(passed)}/{len(judged)}" if judged else "—"
        print(f"{facet:18}{n:>4}{c['ok']:>5}{c['suspect']:>6}{c['null']:>6}{c['deferred']:>7}"
              f"{c['bad']:>5}{c['error']:>5}{cov:>10.0%}{badr:>10.0%}{vrate:>10}")

    bad = [r for r in results if r["bucket"] in ("bad", "error", "suspect")
           and not r.get("frontier")]
    if bad:
        print("\n--- Failure catalog (bad / error / suspect) ---")
        for r in bad:
            print(f"  [{r['facet']}] {r['accession']} {r.get('note', '')[:24]:24} "
                  f"{r['bucket']}: {r['reason']}")

    nulls = defaultdict(int)
    for r in results:
        if r["bucket"] == "null" and not r.get("frontier"):
            nulls[(r["facet"], r["reason"])] += 1
    if nulls:
        print("\n--- Null clusters (triage targets) ---")
        for (facet, reason), cnt in sorted(nulls.items(), key=lambda x: -x[1]):
            print(f"  {cnt:>3}  [{facet}] {reason}")

    # Frontier: documented coverage gaps. Not ratcheted; tracked so we can watch
    # the gap close. coverage here = how much of the known gap is now reachable.
    frontier = [r for r in results if r.get("frontier")]
    if frontier:
        fb = summarize(frontier, include_frontier=True)
        print("\n--- Frontier (known gaps — NOT ratcheted) ---")
        for facet, c in sorted(fb.items()):
            n = c["n"]
            reached = c["ok"] + c["deferred"]
            print(f"  [{facet}] {reached}/{n} reachable "
                  f"(ok={c['ok']} deferred={c['deferred']} null={c['null']} bad={c['bad']})")
        gaps = defaultdict(int)
        for r in frontier:
            if r["bucket"] in ("null", "bad"):
                gaps[(r["facet"], r["reason"])] += 1
        for (facet, reason), cnt in sorted(gaps.items(), key=lambda x: -x[1]):
            print(f"    {cnt:>3}  [{facet}] {reason}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facet", choices=list(FACETS))
    ap.add_argument("--json", type=Path, help="write machine-readable results")
    args = ap.parse_args()

    entries = json.loads(CORPUS_PATH.read_text())
    results = run(entries, only_facet=args.facet)
    print_dashboard(results)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2, default=str) + "\n")
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
