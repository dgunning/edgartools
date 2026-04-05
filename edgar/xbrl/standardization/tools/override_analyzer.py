"""One-time analysis of per-company exclusion overrides for promotion to industry_metrics.yaml.

Reads both company_overrides/*.json and companies.yaml exclude_metrics,
groups by (metric, industry), cross-references with existing industry_metrics.yaml
forbidden_metrics, and outputs a promotion report.

Usage:
    python -m edgar.xbrl.standardization.tools.override_analyzer
"""
import json
import yaml
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


_CONFIG_DIR = Path(__file__).parent.parent / "config"
_OVERRIDES_DIR = _CONFIG_DIR / "company_overrides"
_INDUSTRY_METRICS_PATH = _CONFIG_DIR / "industry_metrics.yaml"
_COMPANIES_YAML_PATH = _CONFIG_DIR / "companies.yaml"
_ONBOARDING_DIR = _CONFIG_DIR / "onboarding_reports"
_REPORT_DIR = Path(__file__).parent.parent / "cohort-reports"

# Map industry_mappings.json keys -> industry_metrics.yaml keys
# Only needed for SIC-based lookup fallback
_INDUSTRY_KEY_NORMALIZATION = {
    "realestate": "reits",
    "investment_companies": "asset_management",
    "finance_services": "financial_services",
    "payment_networks": "financial_services",
}


def _resolve_industry_from_sic(ticker: str) -> Optional[str]:
    """Try to resolve industry from onboarding report SIC code (no network)."""
    report_path = _ONBOARDING_DIR / f"{ticker}_report.json"
    if not report_path.exists():
        return None
    try:
        data = json.loads(report_path.read_text())
        sic = data.get("sic_code")
        if not sic:
            return None
        # Use industry_metrics.yaml SIC ranges directly
        industry_metrics = yaml.safe_load(_INDUSTRY_METRICS_PATH.read_text()) or {}
        sic_int = int(sic)
        for industry_key, config in industry_metrics.items():
            if not isinstance(config, dict):
                continue
            for sic_range in config.get("sic_ranges", []):
                if len(sic_range) == 2 and sic_range[0] <= sic_int <= sic_range[1]:
                    return industry_key
        # Fallback: try industry_mappings.json with normalization
        mappings_path = Path(__file__).parent.parent.parent.parent / "entity" / "data" / "industry_mappings.json"
        if mappings_path.exists():
            mappings = json.loads(mappings_path.read_text())
            for ind_key, ind_info in mappings.get("industries", {}).items():
                for sr in ind_info.get("sic_ranges", []):
                    if len(sr) == 2 and sr[0] <= sic_int <= sr[1]:
                        return _INDUSTRY_KEY_NORMALIZATION.get(ind_key, ind_key)
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return None


def analyze_overrides() -> str:
    """Analyze all override files and return markdown report."""
    # Load industry_metrics.yaml
    with open(_INDUSTRY_METRICS_PATH) as f:
        industry_metrics = yaml.safe_load(f) or {}

    # Build set of existing forbidden metrics per industry
    existing_forbidden: Dict[str, Set[str]] = {}
    for industry, config in industry_metrics.items():
        if isinstance(config, dict) and "forbidden_metrics" in config:
            existing_forbidden[industry] = set(config["forbidden_metrics"])

    # Load companies.yaml
    with open(_COMPANIES_YAML_PATH) as f:
        companies_yaml = yaml.safe_load(f) or {}
    companies_data = companies_yaml.get("companies", {})

    # Build industry map: ticker -> industry (from companies.yaml, fallback to SIC)
    industry_map: Dict[str, str] = {}
    industry_source: Dict[str, str] = {}  # track where we got industry from
    for ticker, cdata in companies_data.items():
        ind = cdata.get("industry", "")
        if ind:
            industry_map[ticker] = ind
            industry_source[ticker] = "companies.yaml"

    # Read all override JSON files
    json_overrides: Dict[str, dict] = {}
    for json_path in sorted(_OVERRIDES_DIR.glob("*.json")):
        ticker = json_path.stem.upper()
        try:
            data = json.loads(json_path.read_text())
            json_overrides[ticker] = data
        except (json.JSONDecodeError, OSError):
            continue

    # All tickers that have any exclusions (from either source)
    all_tickers = set()
    for ticker in json_overrides:
        if json_overrides[ticker].get("exclude_metrics"):
            all_tickers.add(ticker)
    for ticker, cdata in companies_data.items():
        excl = cdata.get("exclude_metrics", {})
        if isinstance(excl, list):
            if excl:
                all_tickers.add(ticker)
        elif isinstance(excl, dict):
            if excl:
                all_tickers.add(ticker)

    # Try SIC-based industry resolution for tickers without industry
    for ticker in all_tickers:
        if ticker not in industry_map:
            ind = _resolve_industry_from_sic(ticker)
            if ind:
                industry_map[ticker] = ind
                industry_source[ticker] = "sic_lookup"

    # Collect ALL exclusions per ticker from both sources
    # Source 1: companies.yaml exclude_metrics
    yaml_exclusions: Dict[str, Set[str]] = {}
    for ticker, cdata in companies_data.items():
        raw = cdata.get("exclude_metrics", {})
        if isinstance(raw, list):
            yaml_exclusions[ticker] = set(raw)
        elif isinstance(raw, dict):
            yaml_exclusions[ticker] = set(raw.keys())
        else:
            yaml_exclusions[ticker] = set()

    # Source 2: company_overrides/*.json exclude_metrics
    json_exclusions: Dict[str, Set[str]] = {}
    for ticker, data in json_overrides.items():
        em = data.get("exclude_metrics", {})
        json_exclusions[ticker] = set(em.keys()) if isinstance(em, dict) else set()

    # Union of all exclusions per ticker
    all_exclusions: Dict[str, Set[str]] = {}
    for ticker in all_tickers:
        all_exclusions[ticker] = (yaml_exclusions.get(ticker, set()) |
                                  json_exclusions.get(ticker, set()))

    # Group exclusions by (metric, industry) — count how many companies in same industry
    exclusion_groups: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    no_industry: List[Tuple[str, str]] = []
    redundant: List[Tuple[str, str, str, str]] = []  # (ticker, metric, industry, source)

    for ticker in sorted(all_tickers):
        industry = industry_map.get(ticker)
        for metric in sorted(all_exclusions.get(ticker, set())):
            # Determine which source(s) this exclusion comes from
            in_yaml = metric in yaml_exclusions.get(ticker, set())
            in_json = metric in json_exclusions.get(ticker, set())
            source = "both" if (in_yaml and in_json) else ("yaml" if in_yaml else "json")

            if industry:
                # Check if already covered by industry forbidden_metrics
                if industry in existing_forbidden and metric in existing_forbidden[industry]:
                    redundant.append((ticker, metric, industry, source))
                else:
                    exclusion_groups[(metric, industry)].append(ticker)
            else:
                no_industry.append((ticker, metric))

    # Categorize groups
    promotable = []  # (metric, industry, tickers) where count >= 3
    borderline = []  # count == 2
    company_specific = []  # count == 1

    for (metric, industry), tickers in sorted(exclusion_groups.items()):
        if len(tickers) >= 3:
            promotable.append((metric, industry, tickers))
        elif len(tickers) == 2:
            borderline.append((metric, industry, tickers))
        else:
            company_specific.append((metric, industry, tickers))

    # Count stats
    total_json_files = len(json_overrides)
    json_with_excludes = sum(1 for d in json_overrides.values() if d.get("exclude_metrics"))
    yaml_with_excludes = sum(1 for t, c in companies_data.items()
                             if (isinstance(c.get("exclude_metrics"), dict) and c["exclude_metrics"])
                             or (isinstance(c.get("exclude_metrics"), list) and c["exclude_metrics"]))
    total_yaml_exclusions = sum(len(yaml_exclusions.get(t, set())) for t in companies_data)
    total_json_exclusions = sum(len(json_exclusions.get(t, set())) for t in json_overrides)
    total_unique_exclusions = sum(len(excl) for excl in all_exclusions.values())

    # Build report
    lines = ["# Override Exclusion Analysis", ""]
    lines.append(f"**Date**: 2026-04-05")
    lines.append("")
    lines.append("## Data Sources")
    lines.append("")
    lines.append(f"- **company_overrides/*.json**: {total_json_files} files, "
                 f"{json_with_excludes} with exclude_metrics, "
                 f"{total_json_exclusions} total exclusions")
    lines.append(f"- **companies.yaml**: {len(companies_data)} companies, "
                 f"{yaml_with_excludes} with exclude_metrics, "
                 f"{total_yaml_exclusions} total exclusions")
    lines.append(f"- **Combined unique**: {len(all_tickers)} companies with exclusions, "
                 f"{total_unique_exclusions} total exclusion entries")
    lines.append(f"- **Industry resolved**: {sum(1 for t in all_tickers if t in industry_map)} "
                 f"({sum(1 for t in all_tickers if industry_source.get(t) == 'companies.yaml')} from companies.yaml, "
                 f"{sum(1 for t in all_tickers if industry_source.get(t) == 'sic_lookup')} from SIC lookup)")
    lines.append(f"- **No industry**: {len([t for t in all_tickers if t not in industry_map])}")
    lines.append("")

    # Summary
    lines.append("## Classification Summary")
    lines.append("")
    lines.append(f"| Category | Count | Action |")
    lines.append(f"|----------|-------|--------|")
    lines.append(f"| Redundant (already in industry forbidden_metrics) | {len(redundant)} | Remove from per-company config |")
    lines.append(f"| Promotable (3+ companies, same industry+metric) | {len(promotable)} groups | Add to industry_metrics.yaml |")
    lines.append(f"| Borderline (2 companies) | {len(borderline)} groups | Review manually |")
    lines.append(f"| Company-specific (1 company) | {len(company_specific)} | Keep in per-company override |")
    lines.append(f"| No industry assigned | {len(no_industry)} | Assign industry first |")
    lines.append("")

    # Redundant
    if redundant:
        lines.append("## Redundant Exclusions (safe to remove)")
        lines.append("")
        lines.append("These are already covered by `industry_metrics.yaml` forbidden_metrics.")
        lines.append("Removing them will reduce config noise without changing behavior.")
        lines.append("")
        lines.append("| Ticker | Metric | Industry | Source |")
        lines.append("|--------|--------|----------|--------|")
        for ticker, metric, industry, source in sorted(redundant):
            lines.append(f"| {ticker} | {metric} | {industry} | {source} |")
        lines.append("")

    # Promotable
    if promotable:
        lines.append("## Promotable Exclusions (add to industry_metrics.yaml)")
        lines.append("")
        lines.append("These metrics are excluded by 3+ companies in the same industry,")
        lines.append("suggesting they are industry-level patterns, not company-specific.")
        lines.append("")
        lines.append("| Metric | Industry | Count | Tickers |")
        lines.append("|--------|----------|-------|---------|")
        for metric, industry, tickers in sorted(promotable, key=lambda x: (-len(x[2]), x[0])):
            lines.append(f"| {metric} | {industry} | {len(tickers)} | {', '.join(sorted(tickers))} |")
        lines.append("")

    # Borderline
    if borderline:
        lines.append("## Borderline (2 companies - review manually)")
        lines.append("")
        lines.append("| Metric | Industry | Tickers |")
        lines.append("|--------|----------|---------|")
        for metric, industry, tickers in sorted(borderline):
            lines.append(f"| {metric} | {industry} | {', '.join(sorted(tickers))} |")
        lines.append("")

    # Company-specific
    if company_specific:
        lines.append("## Company-Specific (keep in per-company override)")
        lines.append("")
        lines.append("| Metric | Industry | Ticker |")
        lines.append("|--------|----------|--------|")
        for metric, industry, tickers in sorted(company_specific):
            lines.append(f"| {metric} | {industry} | {tickers[0]} |")
        lines.append("")

    # No industry
    if no_industry:
        lines.append("## No Industry Assigned (need industry before categorizing)")
        lines.append("")
        lines.append("These companies have exclusions but no industry classification.")
        lines.append("Assign industry in companies.yaml to enable proper categorization.")
        lines.append("")
        lines.append("| Ticker | Metric |")
        lines.append("|--------|--------|")
        for ticker, metric in sorted(no_industry):
            lines.append(f"| {ticker} | {metric} |")
        lines.append("")

    # Top excluded metrics overall
    metric_counts: Dict[str, int] = defaultdict(int)
    for excl in all_exclusions.values():
        for m in excl:
            metric_counts[m] += 1

    lines.append("## Most Frequently Excluded Metrics (all companies)")
    lines.append("")
    lines.append("| Metric | Companies Excluding | % of Companies with Exclusions |")
    lines.append("|--------|--------------------|---------------------------------|")
    for metric, count in sorted(metric_counts.items(), key=lambda x: -x[1]):
        pct = count / len(all_tickers) * 100 if all_tickers else 0
        lines.append(f"| {metric} | {count} | {pct:.0f}% |")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    report = analyze_overrides()
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _REPORT_DIR / "override-analysis.md"
    report_path.write_text(report)
    print(f"Report written to {report_path}")
    print()
    print(report)
