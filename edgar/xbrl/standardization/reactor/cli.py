"""
Cohort Reactor CLI

Command-line interface for running cohort tests.

Usage:
    python -m edgar.xbrl.standardization.reactor.cli --cohort GSIB_Banks --strategy hybrid_debt
    python -m edgar.xbrl.standardization.reactor.cli --list-cohorts
"""

import argparse
import json
import sys
from typing import Optional

from .cohort_reactor import CohortReactor


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Cohort Reactor - Test strategy changes against company cohorts'
    )

    # Commands
    parser.add_argument(
        '--list-cohorts',
        action='store_true',
        help='List all available cohorts'
    )

    parser.add_argument(
        '--show-cohort',
        type=str,
        metavar='NAME',
        help='Show details of a specific cohort'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Run a cohort test'
    )

    # Test options
    parser.add_argument(
        '--cohort',
        type=str,
        help='Cohort name to test'
    )

    parser.add_argument(
        '--strategy',
        type=str,
        help='Strategy name to test'
    )

    parser.add_argument(
        '--params',
        type=str,
        help='Strategy parameters as JSON string'
    )

    parser.add_argument(
        '--metric',
        type=str,
        default='ShortTermDebt',
        help='Metric to test (default: ShortTermDebt)'
    )

    # Output options
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Quiet mode - only output pass/fail'
    )

    args = parser.parse_args()

    # Create reactor
    reactor = CohortReactor()

    # Handle commands
    if args.list_cohorts:
        list_cohorts(reactor)
        return 0

    if args.show_cohort:
        show_cohort(reactor, args.show_cohort)
        return 0

    if args.test:
        if not args.cohort or not args.strategy:
            print("Error: --cohort and --strategy are required for --test")
            return 1

        params = {}
        if args.params:
            try:
                params = json.loads(args.params)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON params: {e}")
                return 1

        return run_test(
            reactor,
            cohort_name=args.cohort,
            strategy_name=args.strategy,
            strategy_params=params,
            metric=args.metric,
            output_json=args.json,
            quiet=args.quiet,
        )

    # Default: show help
    parser.print_help()
    return 0


def list_cohorts(reactor: CohortReactor):
    """List all available cohorts."""
    print("\nAvailable Cohorts:")
    print("-" * 60)

    for name in sorted(reactor.list_cohorts()):
        cohort = reactor.get_cohort(name)
        if cohort:
            print(f"\n{name}:")
            print(f"  Description: {cohort.description or 'N/A'}")
            print(f"  Members: {', '.join(cohort.members)}")
            print(f"  Archetype: {cohort.archetype}")
            if cohort.sub_archetype:
                print(f"  Sub-archetype: {cohort.sub_archetype}")
            print(f"  Metrics: {', '.join(cohort.metrics)}")


def show_cohort(reactor: CohortReactor, name: str):
    """Show details of a specific cohort."""
    cohort = reactor.get_cohort(name)
    if not cohort:
        print(f"Error: Unknown cohort '{name}'")
        print(f"Available cohorts: {', '.join(reactor.list_cohorts())}")
        return

    print(f"\nCohort: {cohort.name}")
    print("=" * 40)
    print(f"Description: {cohort.description or 'N/A'}")
    print(f"Archetype: {cohort.archetype}")
    if cohort.sub_archetype:
        print(f"Sub-archetype: {cohort.sub_archetype}")
    print(f"\nMembers ({len(cohort.members)}):")
    for ticker in cohort.members:
        print(f"  - {ticker}")
    print(f"\nMetrics to test:")
    for metric in cohort.metrics:
        print(f"  - {metric}")


def run_test(
    reactor: CohortReactor,
    cohort_name: str,
    strategy_name: str,
    strategy_params: dict,
    metric: str,
    output_json: bool = False,
    quiet: bool = False,
) -> int:
    """Run a cohort test."""
    try:
        # Note: In a real implementation, extractor_fn would use the actual
        # extraction logic. For now, we just run the test framework.
        summary = reactor.test_strategy_change(
            cohort_name=cohort_name,
            strategy_name=strategy_name,
            strategy_params=strategy_params,
            metric=metric,
        )

        if output_json:
            output = {
                'test_id': summary.test_id,
                'cohort_name': summary.cohort_name,
                'strategy_name': summary.strategy_name,
                'strategy_fingerprint': summary.strategy_fingerprint,
                'is_passing': summary.is_passing,
                'improved_count': summary.improved_count,
                'neutral_count': summary.neutral_count,
                'regressed_count': summary.regressed_count,
                'total_variance_before': summary.total_variance_before,
                'total_variance_after': summary.total_variance_after,
                'variance_delta': summary.variance_delta,
                'results': [
                    {
                        'ticker': r.ticker,
                        'impact': r.impact,
                        'baseline_variance': r.baseline_variance,
                        'new_variance': r.new_variance,
                    }
                    for r in summary.company_results
                ],
            }
            print(json.dumps(output, indent=2))
        elif quiet:
            print("PASS" if summary.is_passing else "FAIL")
        else:
            reactor.print_summary(summary)

        return 0 if summary.is_passing else 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
