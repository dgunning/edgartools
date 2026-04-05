"""
Benchmark: Time validate_winners() with the 19 proposals from Phase D.

Usage:
    hatch run python bench_validate_winners.py
"""
import logging
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from edgar import set_identity, use_local_storage
set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

from edgar.xbrl.standardization.tools.auto_eval_loop import TeamSession
from edgar.xbrl.standardization.tools.auto_eval import EXPANSION_COHORT_100


def mem_gb():
    """Current process RSS in GB (Linux only)."""
    try:
        with open(f"/proc/{os.getpid()}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024 / 1024
    except Exception:
        return 0.0


# Disk-backed XBRL cache keeps memory safe with 4 workers
# (in-memory cache OOM'd at 7.3 GB RSS; disk cache ~2.2 GB total)
MAX_WORKERS = 4

print("=" * 70)
print("BENCHMARK: validate_winners() with Phase D proposals")
print(f"  System RAM: 16 GB, using {MAX_WORKERS} workers")
print("=" * 70)

# Create session with the 100-company cohort
session = TeamSession(eval_cohort=EXPANSION_COHORT_100, num_workers=4)

# Step 1: Establish baseline
print(f"\n[1/3] Computing baseline CQS on 100-company cohort... (mem: {mem_gb():.1f} GB)")
t0 = time.time()
baseline = session.establish_baseline(max_workers=MAX_WORKERS)
t_baseline = time.time() - t0
print(f"  Baseline: {baseline.summary()}")
print(f"  Baseline time: {t_baseline:.1f}s (mem: {mem_gb():.1f} GB)")

# Step 2: Collect proposals from the Phase D worker outputs
print("\n[2/3] Loading proposals from worker output files...")
proposals = session.collect_results()
print(f"  Loaded {len(proposals)} proposals")
for p in proposals:
    scoped = "company" if p.proposal.change_type.value in ("add_exclusion", "add_known_variance", "add_company_override", "set_industry") else "global"
    print(f"    {p.proposal.target_metric} ({p.proposal.target_companies}) [{p.proposal.change_type.value}] -> {scoped}")

# Step 3: Validate winners (THE THING WE OPTIMIZED)
print(f"\n[3/3] Running validate_winners() on {len(proposals)} proposals... (mem: {mem_gb():.1f} GB)")
t1 = time.time()
report = session.validate_winners(proposals, max_workers=MAX_WORKERS)
t_validate = time.time() - t1

print(f"\n{'=' * 70}")
print(f"RESULTS")
print(f"{'=' * 70}")
print(f"  Proposals evaluated: {report.experiments_total}")
print(f"  Kept:     {report.experiments_kept}")
print(f"  Discarded: {report.experiments_discarded}")
print(f"  Vetoed:   {report.experiments_vetoed}")
print(f"  CQS:      {report.cqs_start:.4f} -> {report.cqs_end:.4f}")
print(f"")
print(f"  Baseline time:     {t_baseline:.1f}s ({t_baseline/60:.1f} min)")
print(f"  Validation time:   {t_validate:.1f}s ({t_validate/60:.1f} min)")
print(f"  Total time:        {t_baseline + t_validate:.1f}s ({(t_baseline + t_validate)/60:.1f} min)")
print(f"  Peak mem:          {mem_gb():.1f} GB")
print(f"")
print(f"  Previous validation time: ~2.28 hours (8208s)")
print(f"  Speedup:           {8208 / max(t_validate, 1):.1f}x")

# Cleanup
session.shutdown()
