#!/usr/bin/env python
"""
Review Known Divergences Script

Generates a report of all known divergences in companies.yaml,
organized by remediation status and review date.

Usage:
    python scripts/review_divergences.py
    python scripts/review_divergences.py --output report.md
    python scripts/review_divergences.py --overdue-only
"""

import yaml
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


def load_companies_config():
    """Load companies.yaml configuration."""
    config_path = Path(__file__).parent.parent / "edgar/xbrl/standardization/config/companies.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def extract_divergences(config):
    """Extract all known_divergences from companies.yaml."""
    divergences = []

    for ticker, company_data in config.get("companies", {}).items():
        known_divs = company_data.get("known_divergences", {})

        for metric, div_data in known_divs.items():
            divergences.append({
                "ticker": ticker,
                "company": company_data.get("name", ticker),
                "metric": metric,
                "form_types": div_data.get("form_types", []),
                "fiscal_years": div_data.get("fiscal_years", "all"),
                "variance_pct": div_data.get("variance_pct"),
                "reason": div_data.get("reason", "").strip(),
                "skip_validation": div_data.get("skip_validation", False),
                "added_date": div_data.get("added_date"),
                "remediation_status": div_data.get("remediation_status", "none"),
                "remediation_notes": div_data.get("remediation_notes", "").strip() if div_data.get("remediation_notes") else None,
                "review_date": div_data.get("review_date"),
                "github_issue": div_data.get("github_issue"),
            })

    return divergences


def generate_report(divergences, overdue_only=False):
    """Generate a markdown report of divergences."""
    today = datetime.now().date()

    # Group by status
    by_status = defaultdict(list)
    for div in divergences:
        status = div["remediation_status"]
        by_status[status].append(div)

    # Find overdue items
    overdue = []
    for div in divergences:
        review_date = div.get("review_date")
        if review_date:
            try:
                rd = datetime.strptime(review_date, "%Y-%m-%d").date()
                if rd <= today:
                    overdue.append(div)
            except ValueError:
                pass

    if overdue_only:
        divergences = overdue

    # Generate report
    lines = []
    lines.append("# Known Divergences Review Report")
    lines.append(f"\n**Generated:** {today.isoformat()}")
    lines.append(f"**Total Divergences:** {len(divergences)}")
    lines.append(f"**Overdue for Review:** {len(overdue)}")

    # Summary by status
    lines.append("\n## Summary by Status\n")
    lines.append("| Status | Count | Description |")
    lines.append("|--------|-------|-------------|")
    status_desc = {
        "none": "No remediation planned",
        "investigating": "Actively investigating",
        "deferred": "Known fix, deprioritized",
        "wont_fix": "Structural limitation",
        "resolved": "Fixed, ready to remove",
    }
    for status in ["investigating", "deferred", "wont_fix", "none", "resolved"]:
        count = len(by_status.get(status, []))
        desc = status_desc.get(status, "Unknown")
        lines.append(f"| {status} | {count} | {desc} |")

    # Overdue items
    if overdue:
        lines.append("\n## Overdue for Review\n")
        lines.append("These items have passed their review_date and should be reassessed:\n")
        lines.append("| Ticker | Metric | Review Date | Status | Reason |")
        lines.append("|--------|--------|-------------|--------|--------|")
        for div in sorted(overdue, key=lambda x: x.get("review_date", "")):
            reason_short = div["reason"][:50] + "..." if len(div["reason"]) > 50 else div["reason"]
            lines.append(f"| {div['ticker']} | {div['metric']} | {div['review_date']} | {div['remediation_status']} | {reason_short} |")

    # Items without tracking
    no_tracking = [d for d in divergences if not d.get("added_date")]
    if no_tracking:
        lines.append("\n## Missing Tracking Fields\n")
        lines.append("These divergences lack added_date and should be updated:\n")
        lines.append("| Ticker | Metric | Status |")
        lines.append("|--------|--------|--------|")
        for div in no_tracking:
            lines.append(f"| {div['ticker']} | {div['metric']} | {div['remediation_status']} |")

    # Detailed listing by status
    for status in ["investigating", "deferred", "wont_fix", "none"]:
        items = by_status.get(status, [])
        if not items:
            continue

        lines.append(f"\n## Status: {status.upper()}\n")

        for div in sorted(items, key=lambda x: (x["ticker"], x["metric"])):
            lines.append(f"### {div['ticker']} - {div['metric']}")
            lines.append(f"- **Forms:** {', '.join(div['form_types'])}")
            if div['fiscal_years'] != "all":
                lines.append(f"- **Fiscal Years:** {div['fiscal_years']}")
            if div['variance_pct']:
                lines.append(f"- **Expected Variance:** {div['variance_pct']}%")
            lines.append(f"- **Reason:** {div['reason']}")
            if div['added_date']:
                lines.append(f"- **Added:** {div['added_date']}")
            if div['remediation_notes']:
                lines.append(f"- **Remediation Notes:** {div['remediation_notes']}")
            if div['review_date']:
                lines.append(f"- **Review Date:** {div['review_date']}")
            if div['github_issue']:
                lines.append(f"- **GitHub Issue:** {div['github_issue']}")
            lines.append("")

    # Resolved items
    resolved = by_status.get("resolved", [])
    if resolved:
        lines.append("\n## Resolved (Ready to Remove)\n")
        lines.append("These divergences have been marked as resolved and can be removed:\n")
        for div in resolved:
            lines.append(f"- **{div['ticker']} {div['metric']}**: {div['reason']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Review known divergences")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--overdue-only", action="store_true", help="Only show overdue items")
    args = parser.parse_args()

    config = load_companies_config()
    divergences = extract_divergences(config)
    report = generate_report(divergences, overdue_only=args.overdue_only)

    if args.output:
        Path(args.output).write_text(report)
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
