"""
Diagnostic script: Trace HD:InterestExpense through the full CQS pipeline.

Tests hypothesis: Why do semantically-correct AI proposals produce 0 KEEP results?
Three suspects:
  A) Strategy 0 silently fails (concept not in calc trees)
  B) CONFIG source auto-passes, masking the change
  C) Pre-screen gate math is wrong

Usage:
    python scripts/diagnose_pipeline.py
"""
import logging
import sys
from pathlib import Path

# Enable DEBUG logging for key modules
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(levelname)s | %(message)s",
)
# Bump standardization modules to DEBUG
for mod in [
    "edgar.xbrl.standardization.layers.tree_parser",
    "edgar.xbrl.standardization.reference_validator",
    "edgar.xbrl.standardization.orchestrator",
]:
    logging.getLogger(mod).setLevel(logging.DEBUG)

from edgar.xbrl.standardization.config_loader import get_config
from edgar.xbrl.standardization.orchestrator import Orchestrator
from edgar.xbrl.standardization.tools.auto_eval import compute_cqs
from edgar.xbrl.standardization.tools.auto_eval_loop import (
    apply_change_to_config,
    ConfigChange,
    ChangeType,
)

TICKER = "HD"
METRIC = "InterestExpense"
PROPOSED_CONCEPT = "InterestExpense"  # From Run 010 AI proposal

DIVIDER = "=" * 70


def print_mapping_result(label: str, result):
    """Print key fields from a MappingResult."""
    print(f"\n--- {label} ---")
    print(f"  metric:            {result.metric}")
    print(f"  company:           {result.company}")
    print(f"  concept:           {result.concept}")
    print(f"  source:            {result.source}")
    print(f"  confidence:        {result.confidence}")
    print(f"  confidence_level:  {result.confidence_level}")
    print(f"  is_mapped:         {result.is_mapped}")
    print(f"  validation_status: {result.validation_status}")
    print(f"  reasoning:         {result.reasoning}")


def print_validation_result(label: str, val):
    """Print key fields from a ValidationResult."""
    print(f"\n--- {label} ---")
    if val is None:
        print("  (no validation result)")
        return
    print(f"  is_valid:        {val.is_valid}")
    print(f"  status:          {val.status}")
    print(f"  xbrl_value:      {val.xbrl_value}")
    print(f"  reference_value: {val.reference_value}")
    print(f"  variance_pct:    {val.variance_pct}")
    print(f"  variance_type:   {val.variance_type}")
    print(f"  ef_pass:         {val.ef_pass}")
    print(f"  sa_pass:         {val.sa_pass}")
    print(f"  notes:           {val.notes}")


def print_cqs_summary(label: str, cqs_result):
    """Print key CQS fields."""
    print(f"\n--- {label} ---")
    print(f"  CQS:           {cqs_result.cqs:.4f}")
    print(f"  EF-CQS:        {cqs_result.ef_cqs:.4f}")
    print(f"  SA-CQS:        {cqs_result.sa_cqs:.4f}")
    print(f"  pass_rate:     {cqs_result.pass_rate:.4f}")
    print(f"  coverage_rate: {cqs_result.coverage_rate:.4f}")
    print(f"  mean_variance: {cqs_result.mean_variance:.1f}%")
    print(f"  total_metrics: {cqs_result.total_metrics}")
    print(f"  total_mapped:  {cqs_result.total_mapped}")
    print(f"  total_valid:   {cqs_result.total_valid}")

    # Per-company detail
    for ticker, cs in cqs_result.company_scores.items():
        print(f"\n  [{ticker}] CQS={cs.cqs:.4f}  pass_rate={cs.pass_rate:.4f}  "
              f"ef_cqs={cs.ef_cqs:.4f}  sa_cqs={cs.sa_cqs:.4f}  "
              f"valid={cs.metrics_valid}/{cs.metrics_total}  "
              f"excluded={cs.metrics_excluded}  unverified={cs.unverified_count}")
        if cs.failed_metrics:
            print(f"    failed: {cs.failed_metrics}")


def main():
    print(DIVIDER)
    print("DIAGNOSTIC: Tracing HD:InterestExpense through CQS pipeline")
    print(DIVIDER)

    # =========================================================================
    # STEP 1: Load baseline config
    # =========================================================================
    print("\n[STEP 1] Loading baseline config...")
    config = get_config(reload=True)

    # Check if HD has any existing metric_overrides for InterestExpense
    hd_config = config.get_company(TICKER)
    if hd_config:
        existing_override = hd_config.metric_overrides.get(METRIC)
        print(f"  HD metric_overrides[{METRIC}]: {existing_override}")
        print(f"  HD exclude_metrics: {hd_config.exclude_metrics}")
        print(f"  HD known_divergences keys: {list(hd_config.known_divergences.keys())}")
    else:
        print(f"  HD not found in companies config!")

    # Check InterestExpense metric config
    metric_config = config.get_metric(METRIC)
    if metric_config:
        print(f"  InterestExpense known_concepts: {metric_config.known_concepts[:5]}...")
        print(f"  InterestExpense composite: {metric_config.composite}")
        print(f"  InterestExpense validation_tolerance: {metric_config.validation_tolerance}")
    else:
        print(f"  InterestExpense metric not found!")

    # =========================================================================
    # STEP 2: Baseline extraction
    # =========================================================================
    print(f"\n{DIVIDER}")
    print("[STEP 2] Baseline extraction (no change)...")
    orch_baseline = Orchestrator(config=config, snapshot_mode=True, use_sec_facts=True)
    baseline_results = orch_baseline.map_company(TICKER, use_ai=False, use_facts=True)

    baseline_mr = baseline_results.get(METRIC)
    if baseline_mr:
        print_mapping_result("Baseline MappingResult", baseline_mr)
    else:
        print(f"  {METRIC} not in extraction results!")
        print(f"  Available metrics: {list(baseline_results.keys())}")

    # =========================================================================
    # STEP 3: Baseline validation
    # =========================================================================
    print(f"\n{DIVIDER}")
    print("[STEP 3] Baseline validation...")
    baseline_val = None
    if hasattr(orch_baseline, 'validation_results'):
        hd_validations = orch_baseline.validation_results.get(TICKER, {})
        baseline_val = hd_validations.get(METRIC)
        print_validation_result("Baseline ValidationResult", baseline_val)
    else:
        print("  No validation_results attribute on orchestrator")

    # =========================================================================
    # STEP 4: Baseline CQS
    # =========================================================================
    print(f"\n{DIVIDER}")
    print("[STEP 4] Baseline CQS (single company)...")
    baseline_cqs = compute_cqs(
        eval_cohort=[TICKER],
        snapshot_mode=True,
        use_ai=False,
        config=config,
        use_sec_facts=True,
    )
    print_cqs_summary("Baseline CQS", baseline_cqs)

    # =========================================================================
    # STEP 5: Apply change in-memory
    # =========================================================================
    print(f"\n{DIVIDER}")
    print(f"[STEP 5] Applying ADD_COMPANY_OVERRIDE: {TICKER}:{METRIC} "
          f"preferred_concept={PROPOSED_CONCEPT}")

    change = ConfigChange(
        file="companies.yaml",
        change_type=ChangeType.ADD_COMPANY_OVERRIDE,
        yaml_path=f"companies.{TICKER}.metric_overrides.{METRIC}",
        new_value={"preferred_concept": PROPOSED_CONCEPT},
        rationale="[DIAGNOSTIC] Testing pipeline end-to-end",
        target_metric=METRIC,
        target_companies=TICKER,
        source="diagnostic",
    )

    modified_config = apply_change_to_config(change, config)

    # Verify the mutation
    hd_mod = modified_config.get_company(TICKER)
    if hd_mod:
        mod_override = hd_mod.metric_overrides.get(METRIC)
        print(f"  Modified HD metric_overrides[{METRIC}]: {mod_override}")
    else:
        print("  ERROR: HD not in modified config!")

    # Verify original unchanged
    hd_orig = config.get_company(TICKER)
    orig_override = hd_orig.metric_overrides.get(METRIC) if hd_orig else None
    print(f"  Original HD metric_overrides[{METRIC}]: {orig_override} (should be None)")

    # =========================================================================
    # STEP 6: Post-change extraction
    # =========================================================================
    print(f"\n{DIVIDER}")
    print("[STEP 6] Post-change extraction...")
    orch_modified = Orchestrator(config=modified_config, snapshot_mode=True, use_sec_facts=True)
    modified_results = orch_modified.map_company(TICKER, use_ai=False, use_facts=True)

    modified_mr = modified_results.get(METRIC)
    if modified_mr:
        print_mapping_result("Post-change MappingResult", modified_mr)
    else:
        print(f"  {METRIC} not in extraction results!")

    # =========================================================================
    # STEP 7: Post-change validation
    # =========================================================================
    print(f"\n{DIVIDER}")
    print("[STEP 7] Post-change validation...")
    modified_val = None
    if hasattr(orch_modified, 'validation_results'):
        hd_mod_validations = orch_modified.validation_results.get(TICKER, {})
        modified_val = hd_mod_validations.get(METRIC)
        print_validation_result("Post-change ValidationResult", modified_val)
    else:
        print("  No validation_results attribute on orchestrator")

    # =========================================================================
    # STEP 8: Post-change CQS
    # =========================================================================
    print(f"\n{DIVIDER}")
    print("[STEP 8] Post-change CQS (single company)...")
    modified_cqs = compute_cqs(
        eval_cohort=[TICKER],
        snapshot_mode=True,
        use_ai=False,
        config=modified_config,
        use_sec_facts=True,
    )
    print_cqs_summary("Post-change CQS", modified_cqs)

    # =========================================================================
    # STEP 9: Delta summary
    # =========================================================================
    print(f"\n{DIVIDER}")
    print("[STEP 9] DELTA SUMMARY")
    print(DIVIDER)

    if baseline_mr and modified_mr:
        fields = [
            ("source", baseline_mr.source, modified_mr.source),
            ("concept", baseline_mr.concept, modified_mr.concept),
            ("confidence", baseline_mr.confidence, modified_mr.confidence),
            ("is_mapped", baseline_mr.is_mapped, modified_mr.is_mapped),
            ("validation_status", baseline_mr.validation_status, modified_mr.validation_status),
        ]
        print("\n  MappingResult changes:")
        for name, old, new in fields:
            changed = " <-- CHANGED" if old != new else ""
            print(f"    {name:25s}: {old!s:40s} → {new!s:40s}{changed}")

    if baseline_val and modified_val:
        fields = [
            ("is_valid", baseline_val.is_valid, modified_val.is_valid),
            ("status", baseline_val.status, modified_val.status),
            ("xbrl_value", baseline_val.xbrl_value, modified_val.xbrl_value),
            ("reference_value", baseline_val.reference_value, modified_val.reference_value),
            ("variance_pct", baseline_val.variance_pct, modified_val.variance_pct),
            ("variance_type", baseline_val.variance_type, modified_val.variance_type),
            ("ef_pass", baseline_val.ef_pass, modified_val.ef_pass),
            ("sa_pass", baseline_val.sa_pass, modified_val.sa_pass),
        ]
        print("\n  ValidationResult changes:")
        for name, old, new in fields:
            changed = " <-- CHANGED" if old != new else ""
            print(f"    {name:25s}: {old!s:40s} → {new!s:40s}{changed}")

    print("\n  CQS changes:")
    print(f"    {'CQS':25s}: {baseline_cqs.cqs:.4f} → {modified_cqs.cqs:.4f}  "
          f"(delta: {modified_cqs.cqs - baseline_cqs.cqs:+.4f})")
    print(f"    {'EF-CQS':25s}: {baseline_cqs.ef_cqs:.4f} → {modified_cqs.ef_cqs:.4f}  "
          f"(delta: {modified_cqs.ef_cqs - baseline_cqs.ef_cqs:+.4f})")
    print(f"    {'SA-CQS':25s}: {baseline_cqs.sa_cqs:.4f} → {modified_cqs.sa_cqs:.4f}  "
          f"(delta: {modified_cqs.sa_cqs - baseline_cqs.sa_cqs:+.4f})")
    print(f"    {'pass_rate':25s}: {baseline_cqs.pass_rate:.4f} → {modified_cqs.pass_rate:.4f}  "
          f"(delta: {modified_cqs.pass_rate - baseline_cqs.pass_rate:+.4f})")

    # =========================================================================
    # VERDICT
    # =========================================================================
    print(f"\n{DIVIDER}")
    print("VERDICT")
    print(DIVIDER)

    source_changed = baseline_mr and modified_mr and baseline_mr.source != modified_mr.source
    concept_changed = baseline_mr and modified_mr and baseline_mr.concept != modified_mr.concept
    cqs_changed = abs(modified_cqs.cqs - baseline_cqs.cqs) > 0.0001

    if not concept_changed and not source_changed:
        print("\n  >>> HYPOTHESIS A CONFIRMED: Strategy 0 silently failed.")
        print("      The preferred_concept was not found in calc trees or facts.")
        print("      TreeParser fell through to Strategy 1 and produced the same result.")
        print("      FIX: Add logging to Strategy 0, verify concept exists in filing.")
    elif source_changed and not cqs_changed:
        post_source = modified_mr.source if modified_mr else "?"
        print(f"\n  >>> Source changed to {post_source} but CQS didn't move.")
        if str(post_source) == "MappingSource.CONFIG":
            print("      HYPOTHESIS B: CONFIG auto-pass masks the change.")
            print("      FIX: Separate MappingSource.OVERRIDE from CONFIG.")
        elif str(post_source) == "MappingSource.OVERRIDE":
            print("      OVERRIDE source detected — validator should process normally.")
            print("      If CQS is still 0, check validator/scoring logic.")
        else:
            print(f"      Unexpected source: {post_source}")
    elif cqs_changed:
        ef_delta = modified_cqs.ef_cqs - baseline_cqs.ef_cqs
        print(f"\n  >>> CQS DID CHANGE (CQS: {modified_cqs.cqs - baseline_cqs.cqs:+.4f}, "
              f"EF-CQS: {ef_delta:+.4f}).")
        print("      The pipeline works end-to-end for this case.")
        if modified_mr:
            print(f"      Post-change source: {modified_mr.source}")
            print(f"      Post-change concept: {modified_mr.concept}")
        print("      OVERRIDE→validator→CQS path is functioning correctly.")
    else:
        print("\n  >>> UNEXPECTED STATE — manual investigation needed.")
        print(f"      source_changed={source_changed}, concept_changed={concept_changed}, "
              f"cqs_changed={cqs_changed}")


if __name__ == "__main__":
    main()
