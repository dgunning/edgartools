"""Reporting and analytics for test harness results."""

import json
import statistics
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .storage import HarnessStorage
from .models import TestResult, TestRun


class ResultReporter:
    """Generate reports from test results.

    Supports multiple output formats:
    - Summary statistics
    - CSV export
    - JSON export
    - Markdown reports
    """

    def __init__(self, storage: HarnessStorage):
        """Initialize reporter.

        Args:
            storage: HarnessStorage instance
        """
        self.storage = storage

    def generate_summary(self, run_id: int) -> Dict[str, Any]:
        """Generate summary statistics for a test run.

        Args:
            run_id: Test run ID

        Returns:
            Dictionary with summary metrics
        """
        results = self.storage.get_results(run_id)

        if not results:
            return {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'errors': 0,
                'skipped': 0,
                'success_rate': 0.0,
                'avg_duration_ms': 0.0
            }

        total = len(results)
        passed = sum(1 for r in results if r.status == 'pass')
        failed = sum(1 for r in results if r.status == 'fail')
        errors = sum(1 for r in results if r.status == 'error')
        skipped = sum(1 for r in results if r.status == 'skip')

        # Calculate average duration for completed tests
        durations = [r.duration_ms for r in results if r.duration_ms is not None]
        avg_duration = statistics.mean(durations) if durations else 0.0

        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'errors': errors,
            'skipped': skipped,
            'success_rate': passed / total if total > 0 else 0.0,
            'avg_duration_ms': avg_duration,
            'min_duration_ms': min(durations) if durations else 0.0,
            'max_duration_ms': max(durations) if durations else 0.0
        }

    def export_csv(self, run_id: int, output_path: Path) -> None:
        """Export test results to CSV.

        Args:
            run_id: Test run ID
            output_path: Path to output CSV file
        """
        import csv

        results = self.storage.get_results(run_id)

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow([
                'accession',
                'company',
                'form',
                'filing_date',
                'test_name',
                'status',
                'duration_ms',
                'error_message',
                'created_at'
            ])

            # Write results
            for result in results:
                writer.writerow([
                    result.filing_accession,
                    result.filing_company,
                    result.filing_form,
                    result.filing_date,
                    result.test_name,
                    result.status,
                    result.duration_ms if result.duration_ms else '',
                    result.error_message if result.error_message else '',
                    result.created_at.isoformat() if result.created_at else ''
                ])

    def export_json(self, run_id: int, output_path: Path, include_details: bool = False) -> None:
        """Export test results to JSON.

        Args:
            run_id: Test run ID
            output_path: Path to output JSON file
            include_details: Whether to include detailed test data
        """
        run = self.storage.get_run(run_id)
        results = self.storage.get_results(run_id)
        summary = self.generate_summary(run_id)

        data = {
            'run': {
                'id': run.id,
                'name': run.name,
                'test_type': run.test_type,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'status': run.status,
                'config': run.config
            },
            'summary': summary,
            'generated_at': datetime.now().isoformat(),
            'results': []
        }

        # Add results
        for result in results:
            result_data = {
                'accession': result.filing_accession,
                'company': result.filing_company,
                'form': result.filing_form,
                'filing_date': result.filing_date,
                'test_name': result.test_name,
                'status': result.status,
                'duration_ms': result.duration_ms,
                'error_message': result.error_message,
                'created_at': result.created_at.isoformat() if result.created_at else None
            }

            if include_details:
                result_data['details'] = result.details

            data['results'].append(result_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

    def generate_markdown_report(self, run_id: int, output_path: Path) -> None:
        """Generate markdown report.

        Args:
            run_id: Test run ID
            output_path: Path to output markdown file
        """
        run = self.storage.get_run(run_id)
        summary = self.generate_summary(run_id)
        results = self.storage.get_results(run_id)

        # Build markdown report
        lines = [
            f"# Test Report: {run.name}",
            "",
            f"**Run ID**: {run_id}",
            f"**Test Type**: {run.test_type}",
            f"**Started**: {run.started_at}",
            f"**Completed**: {run.completed_at}",
            f"**Status**: {run.status}",
            "",
            "## Summary",
            "",
            f"- **Total Tests**: {summary['total']}",
            f"- **Passed**: {summary['passed']} ({summary['success_rate']*100:.1f}%)",
            f"- **Failed**: {summary['failed']}",
            f"- **Errors**: {summary['errors']}",
            f"- **Skipped**: {summary['skipped']}",
            f"- **Average Duration**: {summary['avg_duration_ms']:.2f}ms",
            "",
            "## Configuration",
            "",
            "```json",
            json.dumps(run.config, indent=2),
            "```",
            "",
            "## Results by Status",
            ""
        ]

        # Group results by status
        by_status = {}
        for result in results:
            if result.status not in by_status:
                by_status[result.status] = []
            by_status[result.status].append(result)

        for status in ['pass', 'fail', 'error', 'skip']:
            if status in by_status:
                lines.append(f"### {status.upper()} ({len(by_status[status])})")
                lines.append("")

                if by_status[status]:
                    lines.append("| Company | Form | Date | Duration (ms) |")
                    lines.append("|---------|------|------|---------------|")

                    for result in by_status[status][:20]:  # Limit to 20 per status
                        duration = f"{result.duration_ms:.1f}" if result.duration_ms else "N/A"
                        lines.append(
                            f"| {result.filing_company[:40]} | {result.filing_form} | "
                            f"{result.filing_date} | {duration} |"
                        )

                    if len(by_status[status]) > 20:
                        lines.append(f"\n*...and {len(by_status[status]) - 20} more*")

                lines.append("")

        # Add failures with error messages
        failures = [r for r in results if r.status in ('fail', 'error') and r.error_message]
        if failures:
            lines.append("## Errors and Failures")
            lines.append("")

            for i, result in enumerate(failures[:10], 1):  # Show first 10
                lines.append(f"### {i}. {result.filing_company} ({result.filing_accession})")
                lines.append("")
                lines.append(f"**Status**: {result.status}")
                lines.append(f"**Error**: {result.error_message}")
                lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append(f"*Generated at {datetime.now():%Y-%m-%d %H:%M:%S}*")

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    def generate_form_breakdown(self, run_id: int) -> Dict[str, Dict[str, Any]]:
        """Generate breakdown of results by form type.

        Args:
            run_id: Test run ID

        Returns:
            Dictionary mapping form type to statistics
        """
        results = self.storage.get_results(run_id)
        breakdown = {}

        for result in results:
            form = result.filing_form
            if form not in breakdown:
                breakdown[form] = {
                    'total': 0,
                    'passed': 0,
                    'failed': 0,
                    'errors': 0,
                    'durations': []
                }

            breakdown[form]['total'] += 1

            if result.status == 'pass':
                breakdown[form]['passed'] += 1
            elif result.status == 'fail':
                breakdown[form]['failed'] += 1
            elif result.status == 'error':
                breakdown[form]['errors'] += 1

            if result.duration_ms:
                breakdown[form]['durations'].append(result.duration_ms)

        # Calculate averages
        for form, stats in breakdown.items():
            if stats['durations']:
                stats['avg_duration_ms'] = statistics.mean(stats['durations'])
            else:
                stats['avg_duration_ms'] = 0.0

            stats['success_rate'] = (
                stats['passed'] / stats['total'] if stats['total'] > 0 else 0.0
            )

            # Remove raw durations from output
            del stats['durations']

        return breakdown


class TrendAnalyzer:
    """Analyze trends over multiple test runs.

    Detects regressions, improvements, and patterns in test results
    over time.
    """

    def __init__(self, storage: HarnessStorage):
        """Initialize trend analyzer.

        Args:
            storage: HarnessStorage instance
        """
        self.storage = storage

    def detect_regressions(
        self,
        test_name: str,
        threshold: float = 0.05,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Detect performance regressions.

        Args:
            test_name: Test name to analyze
            threshold: Success rate drop threshold (default: 5%)
            limit: Number of runs to analyze

        Returns:
            List of detected regressions with details
        """
        trends = self.storage.get_trends(test_name, limit)
        regressions = []

        for i in range(1, len(trends)):
            prev = trends[i-1]  # More recent (newer)
            curr = trends[i]     # Older

            # Check for success rate drop (newer is worse than older = regression)
            rate_drop = curr['success_rate'] - prev['success_rate']
            if rate_drop > threshold:
                regressions.append({
                    'run_id': prev['run_id'],  # The newer run that regressed
                    'date': prev['date'],
                    'success_rate': prev['success_rate'],  # Current (worse) rate
                    'previous_rate': curr['success_rate'],  # Previous (better) rate
                    'drop': rate_drop,
                    'severity': self._classify_severity(rate_drop)
                })

        return regressions

    def _classify_severity(self, drop: float) -> str:
        """Classify regression severity.

        Args:
            drop: Success rate drop

        Returns:
            Severity level: 'critical', 'high', 'medium', 'low'
        """
        if drop >= 0.20:
            return 'critical'
        elif drop >= 0.10:
            return 'high'
        elif drop >= 0.05:
            return 'medium'
        else:
            return 'low'

    def detect_improvements(
        self,
        test_name: str,
        threshold: float = 0.05,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Detect performance improvements.

        Args:
            test_name: Test name to analyze
            threshold: Success rate increase threshold (default: 5%)
            limit: Number of runs to analyze

        Returns:
            List of detected improvements with details
        """
        trends = self.storage.get_trends(test_name, limit)
        improvements = []

        for i in range(1, len(trends)):
            prev = trends[i-1]  # More recent (newer)
            curr = trends[i]     # Older

            # Check for success rate increase (newer is better than older = improvement)
            rate_increase = prev['success_rate'] - curr['success_rate']
            if rate_increase > threshold:
                improvements.append({
                    'run_id': prev['run_id'],  # The newer run that improved
                    'date': prev['date'],
                    'success_rate': prev['success_rate'],  # Current (better) rate
                    'previous_rate': curr['success_rate'],  # Previous (worse) rate
                    'improvement': rate_increase
                })

        return improvements

    def analyze_stability(
        self,
        test_name: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Analyze test stability over time.

        Args:
            test_name: Test name to analyze
            limit: Number of runs to analyze

        Returns:
            Stability metrics
        """
        trends = self.storage.get_trends(test_name, limit)

        if len(trends) < 2:
            return {
                'stable': True,
                'variance': 0.0,
                'mean_success_rate': 0.0,
                'trend': 'insufficient_data',
                'data_points': len(trends)
            }

        # Calculate variance in success rates
        success_rates = [t['success_rate'] for t in trends]
        mean_rate = statistics.mean(success_rates)
        variance = statistics.variance(success_rates) if len(success_rates) > 1 else 0.0

        # Determine trend direction
        recent_half = success_rates[:len(success_rates)//2]
        older_half = success_rates[len(success_rates)//2:]

        recent_avg = statistics.mean(recent_half) if recent_half else 0.0
        older_avg = statistics.mean(older_half) if older_half else 0.0

        if recent_avg > older_avg + 0.05:
            trend = 'improving'
        elif recent_avg < older_avg - 0.05:
            trend = 'degrading'
        else:
            trend = 'stable'

        # Consider stable if variance is low
        stable = variance < 0.01  # Less than 1% variance

        return {
            'stable': stable,
            'variance': variance,
            'mean_success_rate': mean_rate,
            'trend': trend,
            'recent_avg': recent_avg,
            'older_avg': older_avg,
            'data_points': len(trends)
        }

    def compare_periods(
        self,
        test_name: str,
        period1_runs: int = 10,
        period2_runs: int = 10
    ) -> Dict[str, Any]:
        """Compare two time periods.

        Args:
            test_name: Test name to analyze
            period1_runs: Number of recent runs (period 1)
            period2_runs: Number of older runs (period 2)

        Returns:
            Comparison metrics
        """
        trends = self.storage.get_trends(test_name, period1_runs + period2_runs)

        if len(trends) < period1_runs + period2_runs:
            return {
                'comparison': 'insufficient_data',
                'period1_avg': 0.0,
                'period2_avg': 0.0,
                'change': 0.0
            }

        # Split into periods
        period1 = trends[:period1_runs]
        period2 = trends[period1_runs:period1_runs + period2_runs]

        period1_rates = [t['success_rate'] for t in period1]
        period2_rates = [t['success_rate'] for t in period2]

        period1_avg = statistics.mean(period1_rates) if period1_rates else 0.0
        period2_avg = statistics.mean(period2_rates) if period2_rates else 0.0

        change = period1_avg - period2_avg

        return {
            'period1_avg': period1_avg,
            'period2_avg': period2_avg,
            'change': change,
            'change_percent': change * 100,
            'comparison': 'improved' if change > 0.05 else 'degraded' if change < -0.05 else 'stable',
            'period1_runs': len(period1),
            'period2_runs': len(period2)
        }
