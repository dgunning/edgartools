#!/usr/bin/env python3
"""
Pipeline Orchestrator — drives companies through the expansion state machine.

State machine per company:
    PENDING → ONBOARDING → ANALYZING → RESOLVING → VALIDATING → PROMOTING → POPULATING → COMPLETE
                                ↑            |
                                └────────────┘  (retry, max 3)
                                             ↓
                                          FAILED

Usage:
    # Add companies to pipeline
    python -m edgar.xbrl.standardization.tools.pipeline_orchestrator add --tickers HD,LOW,MCD

    # Advance companies through the state machine
    python -m edgar.xbrl.standardization.tools.pipeline_orchestrator run --batch HD,LOW,MCD

    # Check status
    python -m edgar.xbrl.standardization.tools.pipeline_orchestrator status

    # Show dashboard
    python -m edgar.xbrl.standardization.tools.pipeline_orchestrator dashboard

    # Reset a failed company
    python -m edgar.xbrl.standardization.tools.pipeline_orchestrator reset --ticker HD

    # Populate all COMPLETE companies into FinancialDatabase
    python -m edgar.xbrl.standardization.tools.pipeline_orchestrator populate-all
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from edgar.xbrl.standardization.ledger.schema import ExperimentLedger, PipelineRun

logger = logging.getLogger(__name__)


# =============================================================================
# PIPELINE ORCHESTRATOR
# =============================================================================

class PipelineOrchestrator:
    """
    Drives companies through the expansion pipeline state machine.

    Reuses existing tools:
    - onboard_company() from tools/onboard_company.py
    - resolve_all_gaps() from tools/resolve_gaps.py
    - ExperimentLedger.promote_golden_masters()
    - FinancialDatabase.populate()
    """

    def __init__(self, ledger: Optional[ExperimentLedger] = None, use_ai: bool = True):
        self.ledger = ledger or ExperimentLedger()
        self.use_ai = use_ai

    # =====================================================================
    # ADD / RESET
    # =====================================================================

    def add_companies(self, tickers: List[str]) -> Dict[str, str]:
        """Add tickers to the pipeline in PENDING state.

        Returns:
            Dict mapping ticker to status ('added' or 'already_exists').
        """
        results = {}
        for ticker in tickers:
            ticker = ticker.upper()
            existing = self.ledger.get_pipeline_state(ticker)
            if existing:
                results[ticker] = 'already_exists'
            else:
                self.ledger.add_pipeline_company(ticker)
                results[ticker] = 'added'
        return results

    def reset_company(self, ticker: str) -> str:
        """Reset a FAILED or COMPLETE company back to PENDING.

        Returns:
            Status message.
        """
        ticker = ticker.upper()
        state = self.ledger.get_pipeline_state(ticker)
        if state is None:
            return f'{ticker} not in pipeline'
        self.ledger.reset_pipeline(ticker)
        return f'{ticker} reset from {state["state"]} to PENDING'

    # =====================================================================
    # STATE HANDLERS
    # =====================================================================

    def _handle_pending(self, ticker: str, dry_run: bool = False) -> Dict[str, Any]:
        """PENDING → ONBOARDING: run onboard_company()."""
        if dry_run:
            return {'ticker': ticker, 'action': 'would_onboard', 'dry_run': True}

        self.ledger.advance_pipeline(ticker, 'ONBOARDING')

        from edgar.xbrl.standardization.tools.onboard_company import (
            onboard_company,
            save_report,
        )

        try:
            result = onboard_company(ticker, use_ai=self.use_ai, snapshot_mode=True)
        except Exception as e:
            self.ledger.advance_pipeline(
                ticker, 'FAILED', last_error=f'Onboarding error: {e}'
            )
            return {'ticker': ticker, 'state': 'FAILED', 'error': str(e)}

        if result.error:
            self.ledger.advance_pipeline(
                ticker, 'FAILED', last_error=result.error
            )
            return {'ticker': ticker, 'state': 'FAILED', 'error': result.error}

        # Save report and advance to ANALYZING
        report_path = str(save_report(result))
        self.ledger.advance_pipeline(
            ticker, 'ANALYZING',
            pass_rate=result.pass_rate,
            gaps_count=len(result.metrics_failed),
            onboarding_report_path=report_path,
            company_name=result.company_name,
        )
        return {
            'ticker': ticker,
            'state': 'ANALYZING',
            'pass_rate': result.pass_rate,
            'gaps': len(result.metrics_failed),
        }

    def _handle_analyzing(self, ticker: str, dry_run: bool = False) -> Dict[str, Any]:
        """ANALYZING: classify and route based on pass_rate and gaps."""
        state = self.ledger.get_pipeline_state(ticker)
        pass_rate = state.get('pass_rate') or 0.0
        gaps = state.get('gaps_count') or 0

        if dry_run:
            return {'ticker': ticker, 'action': 'would_analyze', 'pass_rate': pass_rate, 'gaps': gaps}

        if pass_rate >= 90.0 and gaps == 0:
            # Clean — skip straight to VALIDATING
            self.ledger.advance_pipeline(ticker, 'VALIDATING')
            return {'ticker': ticker, 'state': 'VALIDATING', 'pass_rate': pass_rate}

        if pass_rate >= 50.0 and gaps > 0:
            # Needs gap resolution
            self.ledger.advance_pipeline(ticker, 'RESOLVING')
            return {'ticker': ticker, 'state': 'RESOLVING', 'pass_rate': pass_rate, 'gaps': gaps}

        # Too many structural issues
        self.ledger.advance_pipeline(
            ticker, 'FAILED',
            last_error=f'Pass rate too low ({pass_rate:.1f}%)',
        )
        return {'ticker': ticker, 'state': 'FAILED', 'pass_rate': pass_rate, 'error': 'Pass rate below 50%'}

    def _handle_resolving(self, ticker: str, dry_run: bool = False) -> Dict[str, Any]:
        """RESOLVING: run resolve_all_gaps() for the ticker."""
        if dry_run:
            return {'ticker': ticker, 'action': 'would_resolve', 'dry_run': True}

        state = self.ledger.get_pipeline_state(ticker)
        old_pass_rate = state.get('pass_rate') or 0.0

        from edgar.xbrl.standardization.tools.resolve_gaps import (
            resolve_all_gaps,
            calculate_coverage,
        )
        from edgar.xbrl.standardization.orchestrator import Orchestrator

        try:
            orchestrator = Orchestrator()
            results = orchestrator.map_companies(
                tickers=[ticker], use_ai=self.use_ai, validate=True
            )
            before = calculate_coverage(results)
            resolutions, updated_results = resolve_all_gaps(results)
            after = calculate_coverage(updated_results)
        except Exception as e:
            self.ledger.advance_pipeline(
                ticker, 'FAILED', last_error=f'Resolution error: {e}'
            )
            return {'ticker': ticker, 'state': 'FAILED', 'error': str(e)}

        improvement = after.coverage_pct - before.coverage_pct
        new_gaps = after.total_metrics - after.mapped_metrics

        if improvement > 5.0 or after.coverage_pct >= 90.0:
            self.ledger.advance_pipeline(
                ticker, 'VALIDATING',
                pass_rate=after.coverage_pct,
                gaps_count=new_gaps,
            )
            return {
                'ticker': ticker,
                'state': 'VALIDATING',
                'pass_rate': after.coverage_pct,
                'improvement': improvement,
            }

        # No meaningful improvement — retry or fail
        # advance_pipeline handles retry_count and max_retries enforcement
        try:
            self.ledger.advance_pipeline(
                ticker, 'ANALYZING',
                pass_rate=after.coverage_pct,
                gaps_count=new_gaps,
            )
            new_state = self.ledger.get_pipeline_state(ticker)
            return {
                'ticker': ticker,
                'state': new_state['state'],
                'pass_rate': after.coverage_pct,
                'retry_count': new_state['retry_count'],
            }
        except ValueError:
            # Transition was rejected (shouldn't happen, but be safe)
            return {'ticker': ticker, 'state': 'ANALYZING', 'pass_rate': after.coverage_pct}

    def _handle_validating(self, ticker: str, dry_run: bool = False) -> Dict[str, Any]:
        """VALIDATING: run E2E validation with snapshot_mode."""
        if dry_run:
            return {'ticker': ticker, 'action': 'would_validate', 'dry_run': True}

        from edgar.xbrl.standardization.tools.onboard_company import onboard_company

        try:
            result = onboard_company(ticker, use_ai=self.use_ai, snapshot_mode=True)
        except Exception as e:
            self.ledger.advance_pipeline(
                ticker, 'FAILED', last_error=f'Validation error: {e}'
            )
            return {'ticker': ticker, 'state': 'FAILED', 'error': str(e)}

        if result.error:
            self.ledger.advance_pipeline(
                ticker, 'FAILED', last_error=result.error
            )
            return {'ticker': ticker, 'state': 'FAILED', 'error': result.error}

        if result.pass_rate >= 90.0:
            self.ledger.advance_pipeline(
                ticker, 'PROMOTING',
                pass_rate=result.pass_rate,
                gaps_count=len(result.metrics_failed),
            )
            return {'ticker': ticker, 'state': 'PROMOTING', 'pass_rate': result.pass_rate}

        # Regression detected — loop back
        try:
            self.ledger.advance_pipeline(
                ticker, 'ANALYZING',
                pass_rate=result.pass_rate,
                gaps_count=len(result.metrics_failed),
            )
            new_state = self.ledger.get_pipeline_state(ticker)
            return {
                'ticker': ticker,
                'state': new_state['state'],
                'pass_rate': result.pass_rate,
                'retry_count': new_state['retry_count'],
            }
        except ValueError:
            return {'ticker': ticker, 'state': 'VALIDATING', 'pass_rate': result.pass_rate}

    def _handle_promoting(self, ticker: str, dry_run: bool = False) -> Dict[str, Any]:
        """PROMOTING: call ExperimentLedger.promote_golden_masters()."""
        if dry_run:
            return {'ticker': ticker, 'action': 'would_promote', 'dry_run': True}

        try:
            promoted = self.ledger.promote_golden_masters()
            # Count golden masters for this ticker
            ticker_gm = [gm for gm in promoted if gm.ticker == ticker.upper()]
            count = len(ticker_gm)
        except Exception as e:
            self.ledger.advance_pipeline(
                ticker, 'FAILED', last_error=f'Promotion error: {e}'
            )
            return {'ticker': ticker, 'state': 'FAILED', 'error': str(e)}

        self.ledger.advance_pipeline(
            ticker, 'POPULATING',
            golden_masters_count=count,
        )
        return {'ticker': ticker, 'state': 'POPULATING', 'golden_masters': count}

    def _handle_populating(self, ticker: str, dry_run: bool = False) -> Dict[str, Any]:
        """POPULATING: call FinancialDatabase.populate()."""
        if dry_run:
            return {'ticker': ticker, 'action': 'would_populate', 'dry_run': True}

        from edgar.financial_database import FinancialDatabase

        try:
            db = FinancialDatabase()
            pop_result = db.populate(
                tickers=[ticker.upper()],
                n_annual=10,
                n_quarterly=4,
                show_progress=False,
            )
            filings = pop_result.filings_extracted
        except Exception as e:
            self.ledger.advance_pipeline(
                ticker, 'FAILED', last_error=f'Population error: {e}'
            )
            return {'ticker': ticker, 'state': 'FAILED', 'error': str(e)}

        self.ledger.advance_pipeline(
            ticker, 'COMPLETE',
            filings_populated=filings,
        )
        return {'ticker': ticker, 'state': 'COMPLETE', 'filings_populated': filings}

    # =====================================================================
    # MAIN RUN LOOP
    # =====================================================================

    STATE_HANDLERS = {
        'PENDING': '_handle_pending',
        'ONBOARDING': None,  # Transient — handled by _handle_pending
        'ANALYZING': '_handle_analyzing',
        'RESOLVING': '_handle_resolving',
        'VALIDATING': '_handle_validating',
        'PROMOTING': '_handle_promoting',
        'POPULATING': '_handle_populating',
        'COMPLETE': None,
        'FAILED': None,
    }

    def run_batch(
        self,
        tickers: List[str],
        dry_run: bool = False,
        target_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Advance each ticker through one step of the state machine.

        Args:
            tickers: List of tickers to process.
            dry_run: If True, don't actually run anything.
            target_state: If set, only process tickers in this state.

        Returns:
            Batch result dict with per-ticker outcomes.
        """
        batch_id = datetime.now().strftime('%Y-%m-%d_%H%M')
        started_at = datetime.now().isoformat()
        t0 = time.monotonic()
        results = {}

        # Snapshot states before processing
        states_before = {}
        for ticker in tickers:
            ticker = ticker.upper()
            state = self.ledger.get_pipeline_state(ticker)
            if state:
                states_before[ticker] = state['state']

        for ticker in tickers:
            ticker = ticker.upper()
            state = self.ledger.get_pipeline_state(ticker)
            if state is None:
                results[ticker] = {'error': 'Not in pipeline — use add first'}
                continue

            current = state['state']

            if target_state and current != target_state:
                results[ticker] = {'skipped': True, 'state': current}
                continue

            handler_name = self.STATE_HANDLERS.get(current)
            if handler_name is None:
                results[ticker] = {'state': current, 'skipped': True, 'reason': 'terminal_state'}
                continue

            handler = getattr(self, handler_name)
            try:
                result = handler(ticker, dry_run=dry_run)
            except Exception as e:
                result = {'ticker': ticker, 'state': 'FAILED', 'error': str(e)}

            results[ticker] = result

        elapsed = time.monotonic() - t0

        # Snapshot states after processing and classify outcomes
        states_after = {}
        errors = {}
        advanced = 0
        failed = 0
        skipped = 0

        for ticker in [t.upper() for t in tickers]:
            r = results.get(ticker, {})
            if r.get('skipped'):
                skipped += 1
                states_after[ticker] = states_before.get(ticker, 'UNKNOWN')
            elif r.get('error') and r.get('state') == 'FAILED':
                failed += 1
                states_after[ticker] = 'FAILED'
                errors[ticker] = r['error']
            elif r.get('error') and 'Not in pipeline' in r.get('error', ''):
                skipped += 1
            else:
                advanced += 1
                after_state = self.ledger.get_pipeline_state(ticker)
                states_after[ticker] = after_state['state'] if after_state else 'UNKNOWN'

        # Record the batch run (skip for dry_run)
        if not dry_run:
            pipeline_run = PipelineRun(
                run_id=batch_id,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
                tickers=[t.upper() for t in tickers],
                tickers_count=len(tickers),
                tickers_advanced=advanced,
                tickers_failed=failed,
                tickers_skipped=skipped,
                states_before=states_before,
                states_after=states_after,
                errors=errors,
                total_elapsed_seconds=round(elapsed, 1),
            )
            try:
                self.ledger.record_pipeline_run(pipeline_run)
            except Exception as e:
                logger.warning(f"Failed to record pipeline run: {e}")

            # Auto-snapshot KPI metrics
            try:
                from edgar.xbrl.standardization.tools.kpi_tracker import snapshot_pipeline_kpis
                snapshot_pipeline_kpis(self.ledger, batch_id, [t.upper() for t in tickers])
            except Exception as e:
                logger.warning(f"Failed to snapshot KPI metrics: {e}")

        return {
            'batch_id': batch_id,
            'tickers_processed': len(results),
            'results': results,
        }

    # =====================================================================
    # STATUS / DASHBOARD
    # =====================================================================

    def get_status(
        self,
        ticker: Optional[str] = None,
        state: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get pipeline status, optionally filtered.

        Args:
            ticker: Filter to a single ticker.
            state: Filter to a specific state.

        Returns:
            List of pipeline state dicts.
        """
        if ticker:
            s = self.ledger.get_pipeline_state(ticker)
            return [s] if s else []

        if state:
            return self.ledger.get_pipeline_batch(state)

        # All companies across all states
        all_states = []
        for st in self.ledger.VALID_PIPELINE_STATES:
            all_states.extend(self.ledger.get_pipeline_batch(st, limit=500))
        return all_states

    def get_summary(self) -> Dict[str, Any]:
        """
        Get full dashboard data aggregated from multiple sources.

        Returns dict with keys:
            pipeline_summary: state -> count mapping
            total_companies: int
            recent_activity: last 10 transitions
            failed_companies: list of failed ticker dicts
        """
        summary = self.ledger.get_pipeline_summary()
        total = sum(summary.values())
        complete = summary.get('COMPLETE', 0)
        failed = summary.get('FAILED', 0)

        recent = self.ledger.get_pipeline_recent_activity(limit=10)
        failed_companies = self.ledger.get_pipeline_batch('FAILED', limit=50)

        # Try to get golden masters count
        try:
            gm = self.ledger.get_all_golden_masters(active_only=True)
            golden_count = len(gm)
        except Exception:
            golden_count = 0

        return {
            'pipeline_summary': summary,
            'total_companies': total,
            'complete': complete,
            'failed': failed,
            'golden_masters': golden_count,
            'recent_activity': recent,
            'failed_companies': failed_companies,
        }

    def populate_all_complete(self, n_annual: int = 10, n_quarterly: int = 4) -> Dict[str, Any]:
        """
        Populate FinancialDatabase for all COMPLETE companies.

        Returns:
            Population results summary.
        """
        complete = self.ledger.get_pipeline_batch('COMPLETE', limit=500)
        tickers = [c['ticker'] for c in complete]

        if not tickers:
            return {'tickers': 0, 'filings': 0, 'message': 'No COMPLETE companies to populate'}

        from edgar.financial_database import FinancialDatabase

        db = FinancialDatabase()
        result = db.populate(
            tickers=tickers,
            n_annual=n_annual,
            n_quarterly=n_quarterly,
        )
        return {
            'tickers': len(tickers),
            'filings_extracted': result.filings_extracted,
            'filings_skipped': result.filings_skipped,
            'filings_failed': result.filings_failed,
            'elapsed_seconds': result.elapsed_seconds,
        }


# =============================================================================
# CLI FORMATTING
# =============================================================================

def _format_status(companies: List[Dict[str, Any]]) -> str:
    """Format pipeline status as a table."""
    if not companies:
        return 'No companies in pipeline.'

    lines = []
    lines.append(f"{'Ticker':<8} {'State':<12} {'Pass%':>7} {'Gaps':>5} {'GM':>4} {'Filings':>8} {'Retry':>6} {'Error'}")
    lines.append('-' * 80)

    for c in sorted(companies, key=lambda x: x.get('ticker', '')):
        pr = f"{c.get('pass_rate', 0) or 0:.1f}%" if c.get('pass_rate') else '—'
        gaps = str(c.get('gaps_count') or '—')
        gm = str(c.get('golden_masters_count') or '—')
        filings = str(c.get('filings_populated') or '—')
        retry = f"{c.get('retry_count', 0)}/{c.get('max_retries', 3)}"
        error = (c.get('last_error') or '')[:40]
        lines.append(
            f"{c['ticker']:<8} {c['state']:<12} {pr:>7} {gaps:>5} {gm:>4} {filings:>8} {retry:>6} {error}"
        )

    return '\n'.join(lines)


def _format_summary(summary: Dict[str, Any]) -> str:
    """Format dashboard summary."""
    ps = summary['pipeline_summary']
    total = summary['total_companies']

    lines = []
    lines.append('PIPELINE STATUS')
    lines.append(f'  Total companies: {total}')

    # State bar chart
    for state in ExperimentLedger.VALID_PIPELINE_STATES:
        count = ps.get(state, 0)
        if count == 0 and state not in ('COMPLETE', 'FAILED', 'PENDING'):
            continue
        pct = count / total * 100 if total > 0 else 0
        bar_len = int(pct / 4)
        bar = '\u2588' * bar_len
        lines.append(f'  {state:<12} {count:>4}  {bar:<25} {pct:.0f}%')

    lines.append('')
    lines.append(f'  Golden Masters: {summary["golden_masters"]}')

    # Recent activity
    recent = summary.get('recent_activity', [])
    if recent:
        lines.append('')
        lines.append('RECENT ACTIVITY')
        for r in recent[:5]:
            ts = (r.get('last_state_change') or '')[:19]
            lines.append(f'  {ts}  {r["ticker"]:<8} → {r["state"]}')

    # Failed companies
    failed = summary.get('failed_companies', [])
    if failed:
        lines.append('')
        lines.append('FAILED COMPANIES')
        for f in failed:
            err = (f.get('last_error') or 'unknown')[:60]
            lines.append(f'  {f["ticker"]:<8} {err}')

    return '\n'.join(lines)


# =============================================================================
# REPORT FORMATTING
# =============================================================================

def _run_report(report_type: Optional[str] = None):
    """Generate analytical reports from pipeline tracking data."""
    ledger = ExperimentLedger()
    sections = report_type.split(',') if report_type else ['failures', 'trend', 'stuck', 'runs']

    for section in sections:
        section = section.strip()

        if section == 'failures':
            print('\nTOP FAILING METRICS')
            print(f'{"Metric":<30} {"Failures":>8}  {"Companies":>10}  {"FailRate":>8}  {"Pattern"}')
            print('-' * 80)
            metrics = ledger.get_failing_metrics_ranked()
            if metrics:
                for m in metrics:
                    print(
                        f'{m["metric"]:<30} {m["failures"]:>8}  '
                        f'{m["companies"]:>10}  {m["fail_rate"]:>7}%  '
                        f'{m["pattern"]}'
                    )
            else:
                print('  No failure data yet.')

        elif section == 'trend':
            print('\nCOVERAGE TREND')
            from edgar.xbrl.standardization.tools.kpi_tracker import get_progression
            runs = get_progression()
            if runs:
                print(f'{"Run ID":<40} {"Coverage":>8}  {"Companies":>10}')
                print('-' * 62)
                for r in runs[-10:]:
                    print(
                        f'{r["run_id"]:<40} '
                        f'{r["adjusted_coverage_pct"]:>7.1f}%  '
                        f'{r["company_count"]:>10}'
                    )
            else:
                print('  No KPI snapshots yet.')

        elif section == 'stuck':
            print('\nSTUCK COMPANIES')
            stuck = ledger.get_stuck_companies()
            if stuck:
                print(f'{"Ticker":<10} {"State":<25} {"Retry":>5}  {"Pass%":>6}  {"Error"}')
                print('-' * 80)
                for s in stuck:
                    pr = f'{s["pass_rate"]:.1f}%' if s.get('pass_rate') else '---'
                    retry = str(s.get('retry_count', 0))
                    print(
                        f'{s["ticker"]:<10} {s["state"]:<25} {retry:>5}  '
                        f'{pr:>6}  {s["error"]}'
                    )
            else:
                print('  No stuck companies.')

        elif section == 'runs':
            print('\nRECENT BATCH RUNS')
            runs = ledger.get_pipeline_runs(limit=10)
            if runs:
                print(f'{"Run ID":<25} {"Tickers":>8}  {"Adv":>4}  {"Fail":>4}  {"Skip":>4}  {"Elapsed":>8}')
                print('-' * 62)
                for r in runs:
                    elapsed = f'{r.total_elapsed_seconds:.1f}s'
                    print(
                        f'{r.run_id:<25} {r.tickers_count:>8}  '
                        f'{r.tickers_advanced:>4}  {r.tickers_failed:>4}  '
                        f'{r.tickers_skipped:>4}  {elapsed:>8}'
                    )
            else:
                print('  No batch runs recorded yet.')

        print()


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Pipeline Orchestrator — expand the financial database'
    )
    subparsers = parser.add_subparsers(dest='command', help='Sub-commands')

    # --- add ---
    add_parser = subparsers.add_parser('add', help='Add tickers to the pipeline')
    add_parser.add_argument('--tickers', required=True, help='Comma-separated tickers')

    # --- run ---
    run_parser = subparsers.add_parser('run', help='Advance companies through the pipeline')
    run_parser.add_argument('--batch', required=True, help='Comma-separated tickers')
    run_parser.add_argument('--state', default=None, help='Only process tickers in this state')
    run_parser.add_argument('--dry-run', action='store_true', help='Show what would happen')
    run_parser.add_argument('--no-ai', action='store_true', help='Skip AI/API calls (Layers 1+2 only)')

    # --- status ---
    status_parser = subparsers.add_parser('status', help='Show pipeline status')
    status_parser.add_argument('--ticker', default=None, help='Filter to one ticker')
    status_parser.add_argument('--state', default=None, help='Filter to a state')

    # --- dashboard ---
    subparsers.add_parser('dashboard', help='Show pipeline dashboard')

    # --- reset ---
    reset_parser = subparsers.add_parser('reset', help='Reset a ticker to PENDING')
    reset_parser.add_argument('--ticker', required=True, help='Ticker to reset')

    # --- populate-all ---
    pop_parser = subparsers.add_parser(
        'populate-all', help='Populate FinancialDatabase for all COMPLETE companies'
    )
    pop_parser.add_argument('--n-annual', type=int, default=10)
    pop_parser.add_argument('--n-quarterly', type=int, default=4)

    # --- report ---
    report_parser = subparsers.add_parser('report', help='Show analytical reports')
    report_parser.add_argument(
        '--type', default=None,
        help='Report sections: failures,trend,stuck,runs (comma-separated or single)'
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    use_ai = not getattr(args, 'no_ai', False)
    pipeline = PipelineOrchestrator(use_ai=use_ai)

    if args.command == 'add':
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
        results = pipeline.add_companies(tickers)
        for t, status in results.items():
            print(f'  {t}: {status}')

    elif args.command == 'run':
        tickers = [t.strip().upper() for t in args.batch.split(',')]
        batch = pipeline.run_batch(tickers, dry_run=args.dry_run, target_state=args.state)
        print(json.dumps(batch, indent=2, default=str))

    elif args.command == 'status':
        companies = pipeline.get_status(ticker=args.ticker, state=args.state)
        print(_format_status(companies))

    elif args.command == 'dashboard':
        summary = pipeline.get_summary()
        print(_format_summary(summary))

    elif args.command == 'reset':
        msg = pipeline.reset_company(args.ticker)
        print(msg)

    elif args.command == 'populate-all':
        result = pipeline.populate_all_complete(
            n_annual=args.n_annual,
            n_quarterly=args.n_quarterly,
        )
        print(json.dumps(result, indent=2, default=str))

    elif args.command == 'report':
        _run_report(report_type=args.type)


if __name__ == '__main__':
    main()
