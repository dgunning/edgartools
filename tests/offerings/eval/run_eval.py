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

Metrics:  coverage = ok / applicable     bad_rate = bad / applicable

Tier B (self-check oracles: fee cross-check, lifecycle consistency) plugs into
each facet's `classify` via the `oracle` hook — not yet implemented here.
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


ORACLES = {
    "fee_capacity": _oracle_fee_crosscheck,
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
    return "ok", val, "", None


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
        if "expected" in e and bucket in ("ok", "deferred", "null"):
            exp = e["expected"]
            if exp is None:
                if value is not None:
                    bucket, reason = "bad", f"expected None, got {value}"
            elif value is None or abs(value - exp) > max(1.0, abs(exp) * 0.01):
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


def summarize(results):
    by_facet = defaultdict(lambda: defaultdict(int))
    for r in results:
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
        cov = c["ok"] / n if n else 0
        badr = (c["bad"] + c["error"] + c["suspect"]) / n if n else 0
        # verified = oracle-confirmed / oracle-judged (pass + fail), for this facet
        judged = [r for r in results if r["facet"] == facet and r.get("verified") is not None]
        passed = [r for r in judged if r["verified"]]
        vrate = f"{len(passed)}/{len(judged)}" if judged else "—"
        print(f"{facet:18}{n:>4}{c['ok']:>5}{c['suspect']:>6}{c['null']:>6}{c['deferred']:>7}"
              f"{c['bad']:>5}{c['error']:>5}{cov:>10.0%}{badr:>10.0%}{vrate:>10}")

    bad = [r for r in results if r["bucket"] in ("bad", "error", "suspect")]
    if bad:
        print("\n--- Failure catalog (bad / error / suspect) ---")
        for r in bad:
            print(f"  [{r['facet']}] {r['accession']} {r.get('note', '')[:24]:24} "
                  f"{r['bucket']}: {r['reason']}")

    nulls = defaultdict(int)
    for r in results:
        if r["bucket"] == "null":
            nulls[(r["facet"], r["reason"])] += 1
    if nulls:
        print("\n--- Null clusters (triage targets) ---")
        for (facet, reason), cnt in sorted(nulls.items(), key=lambda x: -x[1]):
            print(f"  {cnt:>3}  [{facet}] {reason}")


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
