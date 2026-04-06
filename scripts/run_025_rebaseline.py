"""
Strict EF-CQS rebaseline against every company in companies.yaml.

Captures both the lenient ``ef_cqs`` (current gate) and the parallel
observation ``ef_cqs_strict``, then writes a JSON report under
``edgar/xbrl/standardization/escalation-reports/`` for the roadmap Run Log.

Usage (from the worktree whose editable install is active)::

    python -m scripts.run_025_rebaseline
    # or
    python scripts/run_025_rebaseline.py
"""

import json
import logging
import sys
import time
from pathlib import Path

from edgar.xbrl.standardization.config_loader import get_config
from edgar.xbrl.standardization.tools.auto_eval import (
    DEFAULT_MAX_WORKERS,
    compute_cqs,
)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("run_025")

    cohort = sorted(get_config().companies.keys())
    log.info(f"Strict rebaseline cohort: {len(cohort)} companies from companies.yaml")

    start = time.time()
    result = compute_cqs(
        eval_cohort=cohort,
        snapshot_mode=True,
        max_workers=DEFAULT_MAX_WORKERS,
    )
    elapsed = time.time() - start

    payload = {
        "run_id": "025",
        "label": "Strict EF-CQS rebaseline",
        "cohort_size": len(cohort),
        "duration_seconds": elapsed,
        "aggregate": {
            "ef_cqs_lenient": result.ef_cqs,
            "ef_cqs_strict": result.ef_cqs_strict,
            "delta": result.ef_cqs - result.ef_cqs_strict,
            "cqs": result.cqs,
            "weighted_ef_cqs": result.weighted_ef_cqs,
            "headline_ef_rate": result.headline_ef_rate,
            "explained_variance_count": result.explained_variance_count,
            "companies_evaluated": result.companies_evaluated,
            "total_metrics": result.total_metrics,
        },
        "per_company": {
            ticker: {
                "ef_cqs": cs.ef_cqs,
                "ef_cqs_strict": cs.ef_cqs_strict,
                "explained_variance_count": cs.explained_variance_count,
                "metrics_total": cs.metrics_total,
            }
            for ticker, cs in result.company_scores.items()
        },
    }

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "edgar" / "xbrl" / "standardization" / "escalation-reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "run_025_strict_rebaseline_2026-04-06.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    log.info(f"Rebaseline complete in {elapsed:.0f}s")
    log.info(f"  ef_cqs (lenient): {result.ef_cqs:.4f}")
    log.info(f"  ef_cqs (strict):  {result.ef_cqs_strict:.4f}")
    log.info(f"  delta:            {result.ef_cqs - result.ef_cqs_strict:+.4f}")
    log.info(f"  explained_variance_count: {result.explained_variance_count}")
    log.info(f"Results written to: {out_path.relative_to(repo_root)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
