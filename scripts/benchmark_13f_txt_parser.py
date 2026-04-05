#!/usr/bin/env python3
"""
Benchmark for the 13F-HR TXT parser across the pre-XML era (2005-2013 Q2).

Validates parsed infotable against the filing's self-reported summary page totals:
  - Entry Total (expected number of holdings rows)
  - Value Total (expected total value in thousands)

Usage:
    python scripts/benchmark_13f_txt_parser.py [--per-quarter N] [--output FILE]

Example:
    python scripts/benchmark_13f_txt_parser.py --per-quarter 20 --output benchmark_results.csv
"""

import argparse
import csv
import random
import re
import time
from dataclasses import dataclass

import requests

# ── Benchmark configuration ─────────────────────────────────────────────────

BENCHMARK_QUARTERS = [
    (2005, 4, "Early era"),
    (2008, 4, "Mid era / financial crisis"),
    (2010, 4, "Late era (original bug report period)"),
    (2012, 4, "Last full TXT quarter"),
    (2013, 1, "Final TXT quarter before XML mandate"),
]

SEED = 42  # Fixed seed for reproducible sampling


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class FilingResult:
    quarter: str
    cik: int
    company: str
    accession_no: str
    filing_date: str

    # Ground truth from summary page
    expected_entries: int | None = None
    expected_value: int | None = None  # always normalized to dollars

    # Parsed results
    parsed_entries: int | None = None
    parsed_value: int | None = None  # always in dollars (post 1000x normalization)
    cusip_count: int = 0
    invalid_cusip_count: int = 0

    # Outcome
    status: str = "PENDING"  # PASS, PARTIAL, FAIL, ERROR
    error: str = ""
    notes: str = ""


# ── Summary page extraction ──────────────────────────────────────────────────

def extract_summary_totals(full_text: str) -> tuple[int | None, int | None]:
    """
    Extract Entry Total and Value Total from the Form 13F SUMMARY PAGE.

    The Value Total may be in thousands or dollars depending on the filer.
    We return the raw value and let the comparison logic handle the unit.

    Returns (entry_total, value_total_raw) or (None, None) if not found.
    """
    entry_total = None
    value_total = None

    entry_match = re.search(
        r'(?:Entry|Entries)\s+Total[:\s]*([\d,]+)',
        full_text, re.IGNORECASE
    )
    if entry_match:
        entry_total = int(entry_match.group(1).replace(',', ''))

    value_match = re.search(
        r'Value\s+Total[:\s]*[\$]?([\d,]+)',
        full_text, re.IGNORECASE
    )
    if value_match:
        raw_value = int(value_match.group(1).replace(',', ''))

        # Detect if value is reported in thousands
        context_after = full_text[value_match.end():value_match.end() + 200].lower()
        if 'thousand' in context_after or 'x$1000' in context_after:
            value_total = raw_value * 1000  # Convert to dollars
        else:
            value_total = raw_value  # Could be dollars or thousands — unknown

    return entry_total, value_total


# ── CUSIP validation ─────────────────────────────────────────────────────────

_CUSIP_RE = re.compile(r'^[A-Za-z0-9]{9}$')


def count_invalid_cusips(infotable) -> int:
    """Count CUSIPs that don't match the standard 9-char alphanumeric format."""
    if 'Cusip' not in infotable.columns:
        return len(infotable)
    count = 0
    for cusip in infotable['Cusip']:
        cusip_str = str(cusip).strip()
        if not _CUSIP_RE.match(cusip_str) or not any(c.isdigit() for c in cusip_str):
            count += 1
    return count


# ── Scoring ──────────────────────────────────────────────────────────────────

def _values_match(parsed: int, expected: int, tolerance: float = 0.01) -> bool:
    """
    Check if parsed value matches expected, allowing for unit ambiguity.

    The summary page value might be in thousands or dollars, and the parsed
    infotable value might or might not have the 1000x normalization applied.
    Accept a match at any of: 1:1, 1000:1, or 1:1000 ratio.
    """
    if expected == 0:
        return parsed == 0
    if parsed == 0:
        return False

    # Try all three unit relationships
    for ratio in [1, 1000, 0.001]:
        adjusted = expected * ratio
        if adjusted > 0:
            pct_diff = abs(parsed - adjusted) / adjusted
            if pct_diff <= tolerance:
                return True

    return False


def score_result(result: FilingResult) -> str:
    """
    Score a filing result:
      PASS    - parse success, count matches, value matches
      PARTIAL - parse success, but count or value mismatch
      FAIL    - parse returned empty or raised exception
    """
    if result.parsed_entries is None or result.parsed_entries == 0:
        return "FAIL"

    count_ok = (
        result.expected_entries is not None
        and result.parsed_entries == result.expected_entries
    )

    value_ok = False
    if result.expected_value is not None and result.parsed_value is not None:
        value_ok = _values_match(result.parsed_value, result.expected_value)

    if count_ok and value_ok:
        return "PASS"
    elif result.expected_entries is None and result.expected_value is None:
        return "PARTIAL"
    else:
        return "PARTIAL"


# ── Benchmark runner ─────────────────────────────────────────────────────────

def run_benchmark(per_quarter: int = 20, output_path: str | None = None):
    from edgar import set_identity, get_filings, Filing
    set_identity("EdgarTools Benchmark benchmark@edgartools.io")

    rng = random.Random(SEED)
    all_results: list[FilingResult] = []

    for year, quarter, description in BENCHMARK_QUARTERS:
        quarter_label = f"{year}Q{quarter}"
        print(f"\n{'=' * 70}")
        print(f"  {quarter_label} — {description}")
        print(f"{'=' * 70}")

        # Get filing index for this quarter
        try:
            filings = get_filings(year, quarter, form="13F-HR")
            total_available = len(filings)
            print(f"  Available filings: {total_available}")
        except Exception as e:
            print(f"  ERROR fetching filing index: {e}")
            continue

        # Convert to list and sort by accession number for deterministic ordering
        filing_list = sorted(list(filings), key=lambda x: x.accession_no)

        # Random sample from first 500
        pool_size = min(len(filing_list), 500)
        indices = list(range(pool_size))
        rng.shuffle(indices)
        sample_indices = sorted(indices[:per_quarter])

        sample_filings = [filing_list[idx] for idx in sample_indices]

        print(f"  Sampled: {len(sample_filings)} filings\n")

        for i, f in enumerate(sample_filings):
            result = FilingResult(
                quarter=quarter_label,
                cik=f.cik,
                company=str(f.company)[:40],
                accession_no=f.accession_no,
                filing_date=str(f.filing_date),
            )

            try:
                # Step 1: Get full submission text for summary page
                r = requests.get(
                    f.text_url,
                    headers={"User-Agent": "EdgarTools Benchmark benchmark@edgartools.io"},
                    timeout=30,
                )
                r.raise_for_status()
                full_text = r.text

                # Step 2: Extract ground truth
                result.expected_entries, result.expected_value = extract_summary_totals(full_text)

                # Step 3: Parse the infotable
                thirteenf = f.obj()
                infotable = thirteenf.infotable

                if infotable is not None and len(infotable) > 0 and 'Value' in infotable.columns:
                    result.parsed_entries = len(infotable)

                    # Value column is already in dollars (multiplied by 1000 for
                    # pre-2022 filings by the ThirteenF model).
                    raw_value_sum = infotable['Value'].sum()
                    result.parsed_value = int(raw_value_sum)

                    result.cusip_count = len(infotable)
                    result.invalid_cusip_count = count_invalid_cusips(infotable)
                else:
                    result.parsed_entries = 0
                    result.parsed_value = 0

                # Step 4: Score
                result.status = score_result(result)

                # Build notes
                notes = []
                if result.expected_entries and result.parsed_entries != result.expected_entries:
                    notes.append(f"count: {result.parsed_entries} vs {result.expected_entries}")
                if result.expected_value and result.parsed_value:
                    if not _values_match(result.parsed_value, result.expected_value):
                        notes.append(f"value mismatch: parsed={result.parsed_value:,} expected={result.expected_value:,}")
                if result.invalid_cusip_count > 0:
                    notes.append(f"{result.invalid_cusip_count} invalid CUSIPs")
                result.notes = "; ".join(notes)

            except Exception as e:
                result.status = "ERROR"
                result.error = str(e)[:100]

            # Print progress
            status_icon = {"PASS": "+", "PARTIAL": "~", "FAIL": "X", "ERROR": "!"}[result.status]
            count_info = f"entries={result.parsed_entries}/{result.expected_entries}" if result.expected_entries else f"entries={result.parsed_entries}"
            print(f"  [{status_icon}] {result.company[:30]:30s}  {count_info:25s}  {result.status:8s}  {result.notes}")

            all_results.append(result)

            # Rate limiting
            time.sleep(0.3)

    # ── Print summary ────────────────────────────────────────────────────

    print(f"\n{'=' * 70}")
    print(f"  BENCHMARK RESULTS")
    print(f"{'=' * 70}\n")

    print(f"{'Quarter':10s} {'Total':>6s} {'Pass':>6s} {'Partial':>8s} {'Fail':>6s} {'Error':>6s} {'Pass%':>7s}")
    print("-" * 56)

    quarters = sorted(set(r.quarter for r in all_results))
    for q in quarters:
        q_results = [r for r in all_results if r.quarter == q]
        total = len(q_results)
        pass_count = sum(1 for r in q_results if r.status == "PASS")
        partial_count = sum(1 for r in q_results if r.status == "PARTIAL")
        fail_count = sum(1 for r in q_results if r.status == "FAIL")
        error_count = sum(1 for r in q_results if r.status == "ERROR")
        pass_pct = pass_count / total * 100 if total > 0 else 0
        print(f"{q:10s} {total:6d} {pass_count:6d} {partial_count:8d} {fail_count:6d} {error_count:6d} {pass_pct:6.1f}%")

    total = len(all_results)
    pass_count = sum(1 for r in all_results if r.status == "PASS")
    partial_count = sum(1 for r in all_results if r.status == "PARTIAL")
    fail_count = sum(1 for r in all_results if r.status == "FAIL")
    error_count = sum(1 for r in all_results if r.status == "ERROR")
    pass_pct = pass_count / total * 100 if total > 0 else 0
    parse_success_pct = (pass_count + partial_count) / total * 100 if total > 0 else 0

    print("-" * 56)
    print(f"{'Overall':10s} {total:6d} {pass_count:6d} {partial_count:8d} {fail_count:6d} {error_count:6d} {pass_pct:6.1f}%")
    print(f"\nParse success rate (PASS + PARTIAL): {parse_success_pct:.1f}%")
    print(f"Exact match rate (PASS only):        {pass_pct:.1f}%")

    # ── Write CSV ────────────────────────────────────────────────────────

    if output_path:
        with open(output_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'quarter', 'cik', 'company', 'accession_no', 'filing_date',
                'expected_entries', 'expected_value', 'parsed_entries', 'parsed_value',
                'cusip_count', 'invalid_cusip_count', 'status', 'error', 'notes',
            ])
            for r in all_results:
                writer.writerow([
                    r.quarter, r.cik, r.company, r.accession_no, r.filing_date,
                    r.expected_entries, r.expected_value, r.parsed_entries, r.parsed_value,
                    r.cusip_count, r.invalid_cusip_count, r.status, r.error, r.notes,
                ])
        print(f"\nResults written to {output_path}")

    return all_results


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Benchmark 13F-HR TXT parser across pre-XML era")
    parser.add_argument('--per-quarter', type=int, default=20, help="Filings to sample per quarter (default: 20)")
    parser.add_argument('--output', type=str, default=None, help="Output CSV path")
    args = parser.parse_args()

    if args.output is None:
        args.output = f"benchmark_13f_txt_{args.per_quarter * len(BENCHMARK_QUARTERS)}.csv"

    run_benchmark(per_quarter=args.per_quarter, output_path=args.output)
