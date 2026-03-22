"""Launch overnight CQS improvement run 004 — SEC facts fallback enabled."""
import logging
import sys

from edgar import set_identity, use_local_storage
set_identity("Dev Gunning developer-gunning@gmail.com")
use_local_storage(True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("overnight_run_004.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

from edgar.xbrl.standardization.tools.auto_eval_loop import run_overnight, make_escalation_propose_fn
from edgar.xbrl.standardization.tools.auto_eval import EXPANSION_COHORT_100
from edgar.xbrl.standardization.tools.auto_eval_dashboard import print_overnight_report

report = run_overnight(
    duration_hours=3.0,
    eval_cohort=EXPANSION_COHORT_100,
    propose_fn=make_escalation_propose_fn(escalation_threshold=3),
    max_workers=2,
    use_sec_facts=True,
)
print_overnight_report(report)
