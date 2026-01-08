"""
E2E Test: 10 S&P 500 Companies with AI Agent Resolution

Tests the complete concept mapping workflow:
1. Static layers (Tree Parser + Facts Search)
2. AI agent resolution of gaps
3. Coverage comparison and reporting
"""

from edgar import set_identity, use_local_storage
from edgar.xbrl.standardization.orchestrator import Orchestrator
from edgar.xbrl.standardization.tools.resolve_gaps import (
    resolve_all_gaps,
    calculate_coverage,
    generate_report,
    learn_patterns,
    update_config
)
from edgar.xbrl.standardization.models import MappingSource

def run_sp500_test():
    print("="*60)
    print("E2E TEST: 10 S&P 500 COMPANIES")
    print("="*60)

    # Setup
    set_identity("Dev Gunning developer-gunning@gmail.com")
    use_local_storage(True)

    tickers = ['JPM', 'WMT', 'JNJ', 'XOM', 'BAC', 'PG', 'CVX', 'UNH', 'HD', 'DIS']

    # Phase 1: Static Workflow
    print("\nPHASE 1: STATIC WORKFLOW (Tree Parser + Facts Search)")
    print("-"*60)
    orchestrator = Orchestrator()
    results = orchestrator.map_companies(
        tickers=tickers,
        use_ai=False,  # Static only
        validate=True
    )

    before = calculate_coverage(results)
    print(f"Coverage: {before}")

    # Phase 2: Analyze Gaps
    print("\nPHASE 2: ANALYZE GAPS")
    print("-"*60)
    gaps = []
    for ticker, metrics in results.items():
        for metric, result in metrics.items():
            if result.source == MappingSource.CONFIG:
                continue

            if not result.is_mapped or result.validation_status == "invalid":
                gaps.append({
                    'ticker': ticker,
                    'metric': metric,
                    'status': 'unmapped' if not result.is_mapped else 'invalid'
                })

    print(f"Total gaps: {len(gaps)}")
    print(f"Sample gaps:")
    for gap in gaps[:10]:
        print(f"  {gap['ticker']} {gap['metric']}: {gap['status']}")

    # Phase 3: AI Resolution
    print("\nPHASE 3: AI AGENT RESOLUTION")
    print("-"*60)
    resolutions, updated_results = resolve_all_gaps(results)

    after = calculate_coverage(updated_results)
    print(f"Coverage: {after}")

    improvement = after.coverage_pct - before.coverage_pct
    resolved_count = sum(1 for r in resolutions if r.resolved)
    print(f"Improvement: +{improvement:.1f}% (+{resolved_count} metrics resolved)")

    # Phase 4: Pattern Learning
    print("\nPHASE 4: PATTERN LEARNING")
    print("-"*60)
    patterns = learn_patterns(resolutions)
    if patterns:
        print("Patterns discovered:")
        for metric, concepts in patterns.items():
            print(f"  {metric}: {concepts}")
    else:
        print("No patterns discovered")

    # Phase 5: Config Update
    print("\nPHASE 5: CONFIG UPDATE")
    print("-"*60)
    config_changes = update_config(resolutions)
    if config_changes:
        print(f"Config updated: {len(config_changes)} changes")
        for change in config_changes[:10]:
            print(f"  {change}")
    else:
        print("No config changes needed")

    # Phase 6: Generate Report
    print("\n")
    print("="*60)
    print("FINAL REPORT")
    print("="*60)
    report = generate_report(before, after, resolutions, patterns, config_changes)
    print(report)

    return {
        'before': before,
        'after': after,
        'resolutions': resolutions,
        'patterns': patterns,
        'config_changes': config_changes
    }

if __name__ == "__main__":
    results = run_sp500_test()
