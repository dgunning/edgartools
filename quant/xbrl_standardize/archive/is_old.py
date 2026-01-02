#!/usr/bin/env python3
"""
Use YOUR core mapping JSON to standardize an Income Statement for any SEC filer.

Key idea:
- Let EdgarTools handle statement discovery / correct context (preferred),
  then apply your mapping (us-gaap + ifrs-full) on top.
- Falls back to raw XBRL query() if Financials/Statement APIs are not available.

Requires:
  pip install edgartools pandas

Usage:
  python is_coremap.py --symbol BAC --mapping map_updated.json --identity "Your Name your@email.com"
  python is_coremap.py --symbol AAPL --mapping map_updated.json --identity "Your Name your@email.com" --period-end 2025-09-27

Notes:
- This script does NOT use EdgarTools' own standardization/mapping.
- For non-USD filers, we do not filter by unit by default (the statement DF is already in reported currency).
- Concept name normalization:
    EdgarTools statements often use 'us-gaap_Revenues' (underscore) while XBRL query may use 'us-gaap:Revenues' (colon).
    We store BOTH forms in the facts dict so your mapping can match reliably.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import pandas as pd
from edgar import Company, set_identity  # EdgarTools

Number = Union[int, float]
Facts = Dict[str, Optional[Number]]


# -------------------------
# Evaluator (your schema)
# -------------------------

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _match_industry(industry: Optional[str], hints: Optional[List[str]]) -> bool:
    if not hints:
        return True
    if not industry:
        return False
    ind = industry.strip().lower()
    return any(h and h.strip().lower() in ind for h in hints)


class CircularDependencyError(RuntimeError):
    pass


@dataclass
class Evaluator:
    mapping: Dict[str, Any]
    facts: Facts
    industry: Optional[str] = None
    normalize_abs: bool = True  # set False to preserve negatives

    _field_cache: Dict[str, Optional[Number]] = None
    _visiting: Set[str] = None

    def __post_init__(self):
        self._field_cache = {}
        self._visiting = set()

    def standardize(self) -> Dict[str, Optional[Number]]:
        out: Dict[str, Optional[Number]] = {}
        for field_name in self.mapping.get("fields", {}).keys():
            out[field_name] = self.eval_field(field_name)
        return out

    def eval_field(self, field_name: str) -> Optional[Number]:
        if field_name in self._field_cache:
            return self._field_cache[field_name]

        if field_name in self._visiting:
            raise CircularDependencyError(f"Circular dependency detected at field '{field_name}'")

        self._visiting.add(field_name)
        try:
            field_spec = self.mapping["fields"].get(field_name, {})
            rules = sorted(field_spec.get("rules", []), key=lambda r: int(r.get("priority", 0)), reverse=True)

            value: Optional[Number] = None
            for rule in rules:
                if not _match_industry(self.industry, rule.get("industryHints")):
                    continue

                value = self._select_any(rule.get("selectAny") or [])
                if value is not None:
                    break

                value = self._compute_any(rule.get("computeAny") or [])
                if value is not None:
                    break

            if value is not None and self.normalize_abs:
                value = abs(float(value))

            self._field_cache[field_name] = value
            return value
        finally:
            self._visiting.remove(field_name)

    def _select_any(self, concepts: List[str]) -> Optional[Number]:
        for c in concepts:
            if not c:
                continue
            v = self.facts.get(c)
            if v is None:
                continue
            if _is_number(v):
                return float(v)
        return None

    def _compute_any(self, exprs: List[Dict[str, Any]]) -> Optional[Number]:
        for expr in exprs:
            v = self.eval_expr(expr)
            if v is not None:
                return float(v)
        return None

    def eval_expr(self, expr: Any) -> Optional[Number]:
        if expr is None:
            return None
        if _is_number(expr):
            return float(expr)
        if isinstance(expr, dict):
            if "field" in expr:
                return self.eval_field(expr["field"])
            if "conceptAny" in expr:
                return self._select_any(expr["conceptAny"] or [])
            if "op" in expr:
                return self._eval_op((expr.get("op") or "").lower(), expr.get("terms", []) or [])
        return None

    def _eval_op(self, op: str, terms: List[Any]) -> Optional[Number]:
        if op == "id":
            return self.eval_expr(terms[0]) if terms else None

        vals = [self.eval_expr(t) for t in terms]

        if op == "add":
            if any(v is None for v in vals):
                return None
            return float(sum(vals))  # type: ignore[arg-type]

        if op == "sub":
            if len(vals) != 2 or any(v is None for v in vals):
                return None
            return float(vals[0] - vals[1])  # type: ignore[operator]

        if op == "mul":
            if any(v is None for v in vals):
                return None
            out = 1.0
            for v in vals:
                out *= float(v)  # type: ignore[arg-type]
            return out

        if op == "div":
            if len(vals) != 2 or any(v is None for v in vals):
                return None
            denom = float(vals[1])
            if denom == 0:
                return None
            return float(vals[0]) / denom

        return None


# -------------------------
# Mapping helpers
# -------------------------

def load_mapping(path: str) -> Dict[str, Any]:
    p = Path(path)

    # If user passed a directory, pick a json inside
    if p.is_dir():
        preferred = [p / "map_updated.json", p / "income_mapping.json", p / "map.json"]
        for c in preferred:
            if c.exists() and c.is_file():
                p = c
                break
        else:
            jsons = sorted(p.glob("*.json"))
            if not jsons:
                raise FileNotFoundError(f"No .json mapping file found in directory: {p}")
            p = jsons[0]

    if not p.exists():
        raise FileNotFoundError(f"Mapping file not found: {p}")

    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_concepts_from_mapping(mapping: Dict[str, Any]) -> Set[str]:
    """Collect every concept mentioned in selectAny / conceptAny (us-gaap:, ifrs-full:)."""
    concepts: Set[str] = set()
    for field_spec in mapping.get("fields", {}).values():
        for rule in field_spec.get("rules", []):
            for c in (rule.get("selectAny") or []):
                if isinstance(c, str) and ":" in c:
                    concepts.add(c)
            for expr in (rule.get("computeAny") or []):
                concepts |= collect_concepts_from_expr(expr)
    return concepts


def collect_concepts_from_expr(expr: Any) -> Set[str]:
    concepts: Set[str] = set()
    if isinstance(expr, dict):
        if "conceptAny" in expr:
            for c in (expr.get("conceptAny") or []):
                if isinstance(c, str) and ":" in c:
                    concepts.add(c)
        if "terms" in expr:
            for t in (expr.get("terms") or []):
                concepts |= collect_concepts_from_expr(t)
    elif isinstance(expr, list):
        for t in expr:
            concepts |= collect_concepts_from_expr(t)
    return concepts


# -------------------------
# Concept normalization
# -------------------------

def concept_variants(concept: str) -> List[str]:
    """
    Return possible keys for a concept across EdgarTools outputs:
    - 'us-gaap:Revenues'  (colon QName)
    - 'us-gaap_Revenues'  (underscore variant used in some statement dataframes)
    """
    out = [concept]
    if ":" in concept:
        prefix, local = concept.split(":", 1)
        out.append(f"{prefix}_{local}")
    if "_" in concept and ":" not in concept:
        out.append(concept.replace("_", ":", 1))
    # unique
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            uniq.append(x); seen.add(x)
    return uniq


# -------------------------
# EdgarTools extraction
# -------------------------

def try_income_statement_df(company: Company) -> Optional[pd.DataFrame]:
    """
    Preferred: use Financials -> income_statement().to_dataframe(presentation=True)
    because it is already the correct statement role/context.
    """
    # This API exists in many EdgarTools versions, but not all. We try and gracefully fallback.
    get_financials = getattr(company, "get_financials", None)
    if not callable(get_financials):
        return None

    fin = company.get_financials()
    if fin is None:
        return None

    income_stmt = getattr(fin, "income_statement", None)
    if not callable(income_stmt):
        return None

    stmt = fin.income_statement()
    to_df = getattr(stmt, "to_dataframe", None)
    if not callable(to_df):
        return None

    df = stmt.to_dataframe(presentation=True, include_dimensions=False)
    # Expect columns: label, concept, YYYY-MM-DD ...
    return df


def pick_period_end_from_statement_df(df: pd.DataFrame, forced: Optional[str]) -> str:
    date_cols = [c for c in df.columns if isinstance(c, str) and len(c) == 10 and c[4] == "-" and c[7] == "-"]
    if not date_cols:
        raise RuntimeError("Statement dataframe has no YYYY-MM-DD columns to choose a period from.")
    if forced:
        if forced not in date_cols:
            raise RuntimeError(f"Requested --period-end {forced} not found in statement columns: {date_cols[:5]} ...")
        return forced
    # choose latest date column
    return max(date_cols)


def build_facts_from_statement_df(df: pd.DataFrame, period_end: str) -> Facts:
    facts: Facts = {}
    # normalize numeric
    for _, row in df.iterrows():
        concept = str(row.get("concept", "")).strip()
        if not concept:
            continue
        val = row.get(period_end)
        if pd.isna(val):
            continue
        try:
            v = float(val)
        except Exception:
            continue

        # store both colon and underscore forms
        for k in concept_variants(concept):
            facts[k] = v
    return facts


def fallback_xbrl_query_facts(company: Company, needed_concepts: Set[str], forced_period_end: Optional[str]) -> (Facts, str):
    """
    Fallback path using Filing.xbrl().query() like your original script.
    Still stores both colon/underscore variants.
    """
    filing = company.latest("10-K")
    xb = filing.xbrl()

    q = xb.query()
    # statement filter (varies by version)
    for meth, arg in [("by_statement_type", "IncomeStatement"), ("by_statement", "IncomeStatement")]:
        fn = getattr(q, meth, None)
        if callable(fn):
            q = fn(arg)

    fn = getattr(q, "by_period_type", None)
    if callable(fn):
        q = fn("duration")

    fn = getattr(q, "by_dimension", None)
    if callable(fn):
        q = fn(None)

    df = q.to_dataframe()
    if df.empty:
        raise RuntimeError("No facts returned from XBRL query fallback.")

    # normalize dates
    if "period_end" not in df.columns:
        raise RuntimeError(f"Fact dataframe missing period_end. Columns: {list(df.columns)}")
    df = df.copy()
    df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce")

    if forced_period_end:
        pe = pd.to_datetime(forced_period_end)
    else:
        pe = df["period_end"].max()
    if pd.isna(pe):
        raise RuntimeError("Could not determine period_end from XBRL facts.")

    df = df[df["period_end"] == pe]

    # Keep only needed concepts (exact match, but we'll accept underscore variants too)
    concept_set = set()
    for c in needed_concepts:
        concept_set.update(concept_variants(c))
    df = df[df["concept"].isin(concept_set)]

    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    facts: Facts = {}
    for c in needed_concepts:
        rows = df[df["concept"].isin(concept_variants(c))]
        if rows.empty:
            facts[c] = None
            continue
        # pick row with largest abs (still not perfect, but better after statement filters)
        best = rows.iloc[(rows["value"].abs()).argmax()]
        v = None if pd.isna(best["value"]) else float(best["value"])
        for k in concept_variants(c):
            facts[k] = v
    period_end_str = pd.to_datetime(pe).strftime("%Y-%m-%d")
    return facts, period_end_str


# -------------------------
# Main
# -------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True, help="Ticker symbol, e.g. BAC")
    ap.add_argument("--mapping",  default=r"C:\edgartools_git\quant\test\map\map.json")
    ap.add_argument("--identity", default='SEC identity, e.g. "Your Name your@email.com"')
    ap.add_argument("--industry", default=None, help="Optional industry hint string (e.g., 'Banks')")
    ap.add_argument("--period-end", default=None, help="Force fiscal period_end YYYY-MM-DD")
    ap.add_argument("--preserve-signs", action="store_true", help="Keep negatives (losses/expenses) instead of abs()")
    args = ap.parse_args()

    set_identity(args.identity)

    mapping = load_mapping(args.mapping)
    needed_concepts = collect_concepts_from_mapping(mapping)

    company = Company(args.symbol)

    df_stmt = try_income_statement_df(company)
    facts: Facts
    period_end_str: str

    if df_stmt is not None and not df_stmt.empty:
        period_end_str = pick_period_end_from_statement_df(df_stmt, forced=args.period_end)
        facts = build_facts_from_statement_df(df_stmt, period_end=period_end_str)
    else:
        # fallback to xbrl.query approach
        facts, period_end_str = fallback_xbrl_query_facts(company, needed_concepts, forced_period_end=args.period_end)

    # Make sure our facts dict includes the concepts referenced by mapping (fill missing with None)
    for c in needed_concepts:
        present = any((k in facts and facts[k] is not None) for k in concept_variants(c))
        if not present:
            # store canonical key as None (evaluator reads canonical)
            facts[c] = None

    ev = Evaluator(
        mapping=mapping,
        facts=facts,
        industry=args.industry,
        normalize_abs=(not args.preserve_signs),
    )
    standardized = ev.standardize()

    out = {
        "symbol": args.symbol.lower(),
        "financials": [
            {
                **standardized,
                "period": period_end_str,
                "year": int(period_end_str[:4]),
            }
        ],
        "meta": {
            "form": "10-K",
            "periodEnd": period_end_str,
            "neededConceptsCount": len(needed_concepts),
            "extraction": "statement_df" if (df_stmt is not None and not df_stmt.empty) else "xbrl_query_fallback",
        },
    }

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
