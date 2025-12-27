"""
Collect income statement concept coverage for sector samples.

Outputs:
  - docs-internal/research/sec-filings/data-structures/income-statement-sector-samples.json
  - docs-internal/research/sec-filings/data-structures/income-statement-sector-samples.md
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from edgar.entity import get_company_facts, get_ticker_to_cik_lookup


SAMPLES: Dict[str, List[str]] = {
    "aerospace": ["ACHR", "AIR", "AIRI", "ATRO", "ATROB"],
    "automotive": ["ADNT", "AEAE", "AEAEU", "AEAEW", "AEVA"],
    "banking": ["ABCB", "ACNB", "ADZCF", "ALLY", "ALRS"],
    "consumergoods": ["ABEV", "ABVE", "ABVEW", "ADM", "AFRI"],
    "energy": ["ACDC", "AESI", "ALTX", "AMPY", "ANNA"],
    "healthcare": ["AAPG", "AARD", "AAVXF", "AAWH", "ABBV"],
    "hospitality": ["ATAT", "BALY", "BYD", "CHH", "CNTY"],
    "insurance": ["AAME", "ACGL", "ACGLN", "ACGLO", "ACIC"],
    "mining": ["AAUAF", "ABAT", "ACRG", "ACRL", "ADMG"],
    "realestate": ["AAT", "ABCP", "ABR", "ACR", "ACRE"],
    "retail": ["AAP", "AASP", "ABG", "ABLV", "ABLVW"],
    "tech": ["ACIW", "ADBE", "ADP", "ADSK", "AEYE"],
    "telecom": ["AD", "ADEA", "AEHL", "AMCX", "AMX"],
    "transportation": ["AAL", "AIRT", "AIRTP", "ALGT", "ALK"],
    "utilities": ["AEE", "AEP", "AILIH", "AILIM", "AILIN"],
}

KNOWN_PREFIXES = {
    "us-gaap",
    "us_gaap",
    "ifrs-full",
    "ifrs_full",
    "dei",
    "srt",
}
COMPANY_PREFIX_RE = re.compile(r"^[a-z]{2,10}$")


def normalize_concept(concept: str) -> str:
    normalized = concept.replace(":", "_")
    normalized = normalized.replace("us_gaap", "us-gaap")
    normalized = normalized.replace("ifrs_full", "ifrs-full")
    return normalized


def looks_like_concept(value: str) -> bool:
    if ":" in value:
        prefix = value.split(":", 1)[0]
    elif "_" in value:
        prefix = value.split("_", 1)[0]
    else:
        return False
    if prefix in KNOWN_PREFIXES:
        return True
    return bool(COMPANY_PREFIX_RE.match(prefix))


def collect_mapping_concepts(obj: Any, concepts: Set[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and key.startswith("_comment_"):
                continue
            collect_mapping_concepts(value, concepts)
        return
    if isinstance(obj, list):
        for item in obj:
            collect_mapping_concepts(item, concepts)
        return
    if isinstance(obj, str) and looks_like_concept(obj):
        concepts.add(normalize_concept(obj))


def load_mapping_concepts() -> Set[str]:
    mapping_paths = [
        Path("edgar/xbrl/standardization/concept_mappings.json"),
    ]
    mapping_paths.extend(
        Path("edgar/xbrl/standardization/company_mappings").glob("*.json")
    )

    concepts: Set[str] = set()
    for path in mapping_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        collect_mapping_concepts(data, concepts)
    return concepts


def sector_sample_items() -> Iterable[tuple[str, str]]:
    for sector, tickers in SAMPLES.items():
        for ticker in tickers:
            yield sector, ticker


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_report(path: Path, payload: Dict[str, Any]) -> None:
    lines: List[str] = []
    metadata = payload["metadata"]
    lines.append("# Income Statement Sector Sample Scan")
    lines.append("")
    lines.append("## Scope")
    lines.append(
        "- 15 sectors, 5 tickers per sector (income statement concepts only)."
    )
    lines.append(
        "- Concepts derived from SEC company facts using statement-type mapping."
    )
    lines.append(
        "- Coverage compared against core + company standardization mappings."
    )
    lines.append("")
    lines.append("## Coverage summary")
    lines.append(
        f"- Tickers processed: {metadata['processed_tickers']} of {metadata['total_tickers']}."
    )
    lines.append(f"- Tickers with errors: {metadata['error_tickers']}.")
    lines.append(
        f"- Unique income statement concepts: {metadata['unique_income_concepts']}."
    )
    lines.append(
        f"- Unique concepts missing mappings: {metadata['unique_missing_concepts']}."
    )
    lines.append("")
    lines.append("## Global top missing concepts (by ticker count)")
    for concept, count in payload["global_top_missing"][:20]:
        lines.append(f"- {concept}: {count}")
    lines.append("")
    lines.append("## Sector highlights (top missing concepts)")
    for sector, info in payload["sectors"].items():
        lines.append(f"- {sector}: concepts={info['concept_count']}, missing={info['missing_count']}")
        for concept, count in info["top_missing"][:5]:
            lines.append(f"  - {concept}: {count}")
    lines.append("")
    lines.append("## Sources")
    lines.append("- edgar/xbrl/standardization/concept_mappings.json")
    lines.append("- edgar/xbrl/standardization/company_mappings/*.json")
    lines.append("- edgar/reference/data/company_tickers.pq")
    lines.append("- SEC company facts API (cached in local edgar cache)")
    lines.append("")
    lines.append("## Related")
    lines.append("- docs-internal/research/sec-filings/data-structures/xbrl-concept-mappings-report.md")
    lines.append("")
    lines.append("## Outputs")
    lines.append(f"- {payload['metadata']['output_json']}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ticker_to_cik = get_ticker_to_cik_lookup()
    mapping_concepts = load_mapping_concepts()

    sector_concepts: Dict[str, Set[str]] = defaultdict(set)
    sector_missing: Dict[str, Counter] = defaultdict(Counter)
    sector_ticker_counts: Dict[str, int] = defaultdict(int)
    per_ticker: Dict[str, Dict[str, Any]] = {}
    errors: List[Dict[str, str]] = []
    global_missing = Counter()

    for sector, ticker in sector_sample_items():
        sector_ticker_counts[sector] += 1
        cik = ticker_to_cik.get(ticker)
        if not cik:
            errors.append({"ticker": ticker, "sector": sector, "error": "CIK not found"})
            continue

        try:
            facts = get_company_facts(int(cik))
        except Exception as exc:
            error_text = str(exc) or exc.__class__.__name__
            errors.append(
                {"ticker": ticker, "sector": sector, "error": error_text}
            )
            continue

        income_facts = (
            facts.query()
            .by_statement_type("IncomeStatement")
            .execute()
        )
        concepts = {normalize_concept(fact.concept) for fact in income_facts}
        missing = sorted(concepts - mapping_concepts)

        sector_concepts[sector].update(concepts)
        sector_missing[sector].update(missing)
        global_missing.update(missing)

        per_ticker[ticker] = {
            "sector": sector,
            "concept_count": len(concepts),
            "missing_count": len(missing),
            "concepts": sorted(concepts),
            "missing_concepts": missing,
        }

    sectors_payload = {}
    for sector, concepts in sector_concepts.items():
        missing_counter = sector_missing[sector]
        sectors_payload[sector] = {
            "tickers": SAMPLES[sector],
            "concept_count": len(concepts),
            "missing_count": len(missing_counter),
            "top_missing": missing_counter.most_common(20),
        }

    output_json = Path(
        "docs-internal/research/sec-filings/data-structures/income-statement-sector-samples.json"
    )
    payload = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_tickers": sum(len(v) for v in SAMPLES.values()),
            "processed_tickers": len(per_ticker),
            "error_tickers": len(errors),
            "unique_income_concepts": len(
                set().union(*sector_concepts.values()) if sector_concepts else set()
            ),
            "unique_missing_concepts": len(global_missing),
            "output_json": str(output_json),
        },
        "samples": SAMPLES,
        "sectors": sectors_payload,
        "global_top_missing": global_missing.most_common(50),
        "tickers": per_ticker,
        "errors": errors,
    }

    write_json(output_json, payload)
    write_report(
        Path(
            "docs-internal/research/sec-filings/data-structures/income-statement-sector-samples.md"
        ),
        payload,
    )


if __name__ == "__main__":
    main()
