"""CLI surface for warehouse operations."""

from __future__ import annotations

import argparse

from edgar.warehouse.runtime import run_command


def _parse_cik_list(value: str) -> list[int]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("expected at least one CIK")
    try:
        return [int(item) for item in items]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("CIKs must be comma-separated integers") from exc


def _add_common_bootstrap_args(parser: argparse.ArgumentParser, include_recent_limit: bool) -> None:
    parser.add_argument("--cik-list", type=_parse_cik_list, help="Comma-separated CIK list")
    parser.add_argument(
        "--tracking-status-filter",
        default="active",
        help="Tracked universe status filter",
    )
    parser.add_argument(
        "--include-reference-refresh",
        dest="include_reference_refresh",
        action="store_true",
        default=True,
        help="Refresh SEC reference files before loading",
    )
    parser.add_argument(
        "--no-include-reference-refresh",
        dest="include_reference_refresh",
        action="store_false",
        help="Skip SEC reference refresh",
    )
    if include_recent_limit:
        parser.add_argument(
            "--recent-limit",
            type=int,
            default=10,
            help="Maximum number of recent filings to include per company",
        )
    parser.add_argument(
        "--artifact-policy",
        default="all_attachments",
        help="Artifact fetch policy",
    )
    parser.add_argument(
        "--parser-policy",
        default="configured_forms",
        help="Parser execution policy",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force re-fetch and rebuild of the selected scope",
    )
def _handle_bootstrap_full(args: argparse.Namespace) -> int:
    return run_command("bootstrap-full", args)


def _handle_bootstrap_recent_10(args: argparse.Namespace) -> int:
    return run_command("bootstrap-recent-10", args)


def _handle_daily_incremental(args: argparse.Namespace) -> int:
    return run_command("daily-incremental", args)


def _handle_load_daily_form_index_for_date(args: argparse.Namespace) -> int:
    return run_command("load-daily-form-index-for-date", args)


def _handle_catch_up_daily_form_index(args: argparse.Namespace) -> int:
    return run_command("catch-up-daily-form-index", args)


def _handle_targeted_resync(args: argparse.Namespace) -> int:
    return run_command("targeted-resync", args)


def _handle_full_reconcile(args: argparse.Namespace) -> int:
    return run_command("full-reconcile", args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edgar-warehouse",
        description="Warehouse operations for SEC EDGAR bronze, silver, and gold layers.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_full = subparsers.add_parser(
        "bootstrap-full",
        help="Load full filing history for tracked companies.",
    )
    _add_common_bootstrap_args(bootstrap_full, include_recent_limit=False)
    bootstrap_full.set_defaults(handler=_handle_bootstrap_full)

    bootstrap_recent_10 = subparsers.add_parser(
        "bootstrap-recent-10",
        help="Load only the most recent filings for tracked companies.",
    )
    _add_common_bootstrap_args(bootstrap_recent_10, include_recent_limit=True)
    bootstrap_recent_10.set_defaults(handler=_handle_bootstrap_recent_10)

    daily_incremental = subparsers.add_parser(
        "daily-incremental",
        help="Load impacted company scope from SEC daily form indexes.",
    )
    daily_incremental.add_argument("--start-date", help="Inclusive start business date in YYYY-MM-DD format")
    daily_incremental.add_argument("--end-date", help="Inclusive end business date in YYYY-MM-DD format")
    daily_incremental.add_argument(
        "--include-reference-refresh",
        dest="include_reference_refresh",
        action="store_true",
        default=False,
        help="Refresh SEC reference files before loading",
    )
    daily_incremental.add_argument(
        "--tracking-status-filter",
        default="active",
        help="Tracked universe status filter",
    )
    daily_incremental.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force re-fetch and rebuild of the selected date range",
    )
    daily_incremental.set_defaults(handler=_handle_daily_incremental)

    daily_index_for_date = subparsers.add_parser(
        "load-daily-form-index-for-date",
        help="Load one SEC daily form index by business date.",
    )
    daily_index_for_date.add_argument("target_date", help="Business date in YYYY-MM-DD format")
    daily_index_for_date.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force a refetch even if the checkpoint already exists",
    )
    daily_index_for_date.set_defaults(handler=_handle_load_daily_form_index_for_date)

    catch_up_daily = subparsers.add_parser(
        "catch-up-daily-form-index",
        help="Load missing SEC daily form indexes up to an optional end date.",
    )
    catch_up_daily.add_argument("--end-date", help="Inclusive end business date in YYYY-MM-DD format")
    catch_up_daily.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force refetch for already-loaded business dates",
    )
    catch_up_daily.set_defaults(handler=_handle_catch_up_daily_form_index)

    targeted_resync = subparsers.add_parser(
        "targeted-resync",
        help="Force-refresh one reference, CIK, or accession scope.",
    )
    targeted_resync.add_argument(
        "--scope-type",
        choices=["reference", "cik", "accession"],
        required=True,
        help="Scope type to refresh",
    )
    targeted_resync.add_argument("--scope-key", required=True, help="Reference name, CIK, or accession number")
    targeted_resync.add_argument(
        "--include-artifacts",
        dest="include_artifacts",
        action="store_true",
        default=True,
        help="Refresh filing artifacts",
    )
    targeted_resync.add_argument(
        "--no-include-artifacts",
        dest="include_artifacts",
        action="store_false",
        help="Skip artifact refresh",
    )
    targeted_resync.add_argument(
        "--include-text",
        dest="include_text",
        action="store_true",
        default=True,
        help="Refresh extracted text artifacts",
    )
    targeted_resync.add_argument(
        "--no-include-text",
        dest="include_text",
        action="store_false",
        help="Skip text refresh",
    )
    targeted_resync.add_argument(
        "--include-parsers",
        dest="include_parsers",
        action="store_true",
        default=True,
        help="Re-run configured parsers",
    )
    targeted_resync.add_argument(
        "--no-include-parsers",
        dest="include_parsers",
        action="store_false",
        help="Skip parser execution",
    )
    targeted_resync.add_argument(
        "--no-force",
        dest="force",
        action="store_false",
        default=True,
        help="Disable the default force-refresh behavior",
    )
    targeted_resync.set_defaults(handler=_handle_targeted_resync)

    full_reconcile = subparsers.add_parser(
        "full-reconcile",
        help="Compare live SEC truth to warehouse state and optionally auto-heal drift.",
    )
    full_reconcile.add_argument("--cik-list", type=_parse_cik_list, help="Comma-separated CIK list")
    full_reconcile.add_argument("--sample-limit", type=int, help="Limit the number of tracked companies")
    full_reconcile.add_argument(
        "--include-reference-refresh",
        dest="include_reference_refresh",
        action="store_true",
        default=True,
        help="Refresh SEC reference files before reconciliation",
    )
    full_reconcile.add_argument(
        "--no-include-reference-refresh",
        dest="include_reference_refresh",
        action="store_false",
        help="Skip SEC reference refresh",
    )
    full_reconcile.add_argument(
        "--no-auto-heal",
        dest="auto_heal",
        action="store_false",
        default=True,
        help="Detect drift without launching targeted resync",
    )
    full_reconcile.set_defaults(handler=_handle_full_reconcile)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
