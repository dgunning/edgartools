#!/usr/bin/env python3
"""
Standardized Income Statement Extraction (Fixed One-Shot)
Optimized for NVDA and other complex SEC filers.
"""

from __future__ import annotations
import argparse
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Union
import pandas as pd
from edgar import Company, set_identity

Number = Union[int, float]
Facts = Dict[str, Optional[Number]]

# -------------------------
# Evaluator Logic
# -------------------------

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)

def _match_industry(industry: Optional[str], hints: Optional[List[str]]) -> bool:
    if not hints: return True
    if not industry: return False
    ind = industry.strip().lower()
    return any(h and h.strip().lower() in ind for h in hints)

@dataclass
class Evaluator:
    mapping: Dict[str, Any]
    facts: Facts
    industry: Optional[str] = None
    normalize_abs: bool = False

    def __post_init__(self):
        self._field_cache = {}
        self._visiting = set()

    def standardize(self) -> Dict[str, Optional[Number]]:
        out = {}
        for field_name in self.mapping.get("fields", {}).keys():
            out[field_name] = self.eval_field(field_name)
        return out

    def eval_field(self, field_name: str) -> Optional[Number]:
        if field_name in self._field_cache: return self._field_cache[field_name]
        if field_name in self._visiting: raise RuntimeError(f"Loop at {field_name}")
        self._visiting.add(field_name)
        try:
            field_spec = self.mapping["fields"].get(field_name, {})
            rules = sorted(field_spec.get("rules", []), key=lambda r: int(r.get("priority", 0)), reverse=True)
            value = None
            for rule in rules:
                if not _match_industry(self.industry, rule.get("industryHints")): continue
                value = self._select_any(rule.get("selectAny") or [])
                if value is not None: break
                value = self._compute_any(rule.get("computeAny") or [])
                if value is not None: break
            if value is not None and self.normalize_abs: value = abs(float(value))
            self._field_cache[field_name] = value
            return value
        finally: self._visiting.remove(field_name)

    def _select_any(self, concepts: List[str]) -> Optional[Number]:
        for c in concepts:
            v = self.facts.get(c)
            if _is_number(v): return float(v)
        return None

    def _compute_any(self, exprs: List[Dict[str, Any]]) -> Optional[Number]:
        for expr in exprs:
            v = self.eval_expr(expr)
            if v is not None: return float(v)
        return None

    def eval_expr(self, expr: Any) -> Optional[Number]:
        if _is_number(expr): return float(expr)
        if isinstance(expr, dict):
            if "field" in expr: return self.eval_field(expr["field"])
            if "conceptAny" in expr: return self._select_any(expr["conceptAny"] or [])
            if "op" in expr: return self._eval_op((expr.get("op") or "").lower(), expr.get("terms", []) or [])
        return None

    def _eval_op(self, op: str, terms: List[Any]) -> Optional[Number]:
        vals = [self.eval_expr(t) for t in terms]
        if op == "id": return vals[0] if vals else None
        if any(v is None for v in vals): return None
        if op == "add": return float(sum(vals))
        if op == "sub": return float(vals[0] - vals[1])
        if op == "mul":
            res = 1.0
            for v in vals: res *= v
            return res
        if op == "div": return float(vals[0] / vals[1]) if vals[1] != 0 else None
        return None

# -------------------------
# Robust Extraction Logic
# -------------------------

def concept_variants(concept: str) -> List[str]:
    out = [concept]
    if ":" in concept:
        prefix, local = concept.split(":", 1)
        out.append(f"{prefix}_{local}")
    elif "_" in concept and ":" not in concept:
        out.append(concept.replace("_", ":", 1))
    return list(dict.fromkeys(out))

def try_income_statement_df(company: Company, form: str) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetches income statement for the specific form (10-K/10-Q).

    Returns:
        (dataframe, period_end_date) tuple
    """
    filings = company.get_filings(form=form, amendments=False)
    if not filings: return None, None
    latest_filing = filings.latest()

    # Get period end from filing
    period_end = None
    if hasattr(latest_filing, 'period_of_report'):
        period_end = latest_filing.period_of_report

    # CRITICAL: Get XBRL from THIS specific filing (not company-level)
    xbrl = latest_filing.xbrl()
    if xbrl is None: return None, None

    # Use current_period API to get filing-specific data
    if hasattr(xbrl, 'current_period'):
        try:
            stmt_df = xbrl.current_period.income_statement(
                as_statement=False,
                include_dimensions=False
            )
            if stmt_df is not None and not stmt_df.empty:
                return stmt_df, period_end
        except:
            pass

    # Fallback: Try company-level (only for 10-K)
    if form == "10-K":
        try:
            fin = company.get_financials()
            if fin is not None:
                stmt = getattr(fin, "income_statement", None)
                if callable(stmt):
                    df = stmt().to_dataframe(presentation=True, include_dimensions=False)
                    return df, period_end
        except:
            pass

    return None, None

def pick_period_end_from_statement_df(df: pd.DataFrame, forced: Optional[str], form: str) -> str:
    """Detects the correct column label, prioritizing quarterly '3 Month' data."""
    # Check for 'value' column (current_period API format)
    if 'value' in df.columns:
        return 'value'

    # Otherwise look for date-based columns (statement API format)
    date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
    cols_with_dates = [c for c in df.columns if date_pattern.search(str(c))]

    if not cols_with_dates: raise RuntimeError("No date or value columns found.")

    if forced:
        matches = [c for c in df.columns if forced in str(c)]
        if matches: return matches[0]
        raise RuntimeError(f"Date {forced} not found.")

    latest_date_str = sorted([date_pattern.search(str(c)).group() for c in cols_with_dates], reverse=True)[0]

    # For 10-Qs: Find the 3-month specific column for the latest date
    if form == "10-Q":
        q_label = "3 Month" if any("3 Month" in str(c) for c in df.columns) else "Three Month"
        q_cols = [c for c in cols_with_dates if q_label in str(c) and latest_date_str in str(c)]
        if q_cols: return q_cols[0]

    std_cols = [c for c in cols_with_dates if latest_date_str in str(c)]
    return std_cols[0]

def build_facts_from_statement_df(df: pd.DataFrame, period_end: str) -> Facts:
    facts: Facts = {}
    for _, row in df.iterrows():
        concept = str(row.get("concept", "")).strip()
        if not concept: continue
        val = row.get(period_end)
        if pd.isna(val): continue
        try:
            v = float(val)
            for k in concept_variants(concept): facts[k] = v
        except: continue
    return facts

def fallback_xbrl_query_facts(company: Company, needed_concepts: Set[str], forced_period: Optional[str], form: str) -> (Facts, str):
    """Deep XBRL query if the statement dataframe fails."""
    filing = company.get_filings(form=form).latest()
    xb = filing.xbrl()
    q = xb.query()
    
    # Filter for duration facts
    if hasattr(q, "by_period_type"): q = q.by_period_type("duration")
    df = q.to_dataframe()
    if df.empty: raise RuntimeError("Fallback XBRL query returned no data.")
    
    pe = pd.to_datetime(forced_period) if forced_period else pd.to_datetime(df["period_end"]).max()
    df = df[pd.to_datetime(df["period_end"]) == pe]
    
    facts: Facts = {}
    for c in needed_concepts:
        rows = df[df["concept"].isin(concept_variants(c))]
        if not rows.empty:
            best = rows.iloc[(pd.to_numeric(rows["value"], errors="coerce").abs()).argmax()]
            v = float(best["value"]) if not pd.isna(best["value"]) else None
            for k in concept_variants(c): facts[k] = v
        else: facts[c] = None
    return facts, pe.strftime("%Y-%m-%d")

# -------------------------
# Main
# -------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--form", default="10-K", choices=["10-K", "10-Q"])
    ap.add_argument("--mapping", default="../schemas/income-statement.json")
    ap.add_argument("--identity", default="User user@example.com")
    ap.add_argument("--industry", default=None)
    ap.add_argument("--period-end", default=None)
    args = ap.parse_args()

    set_identity(args.identity)
    with open(args.mapping, "r") as f: mapping = json.load(f)
    
    needed_concepts = set()
    for fspec in mapping.get("fields", {}).values():
        for rule in fspec.get("rules", []):
            needed_concepts.update([c for c in (rule.get("selectAny") or []) if ":" in c])

    company = Company(args.symbol)
    df_stmt, filing_period_end = try_income_statement_df(company, form=args.form)

    if df_stmt is not None and not df_stmt.empty:
        header = pick_period_end_from_statement_df(df_stmt, args.period_end, args.form)
        facts = build_facts_from_statement_df(df_stmt, header)

        # Get period end date
        if filing_period_end:
            period_end_str = filing_period_end
        else:
            date_match = re.search(r"\d{4}-\d{2}-\d{2}", str(header))
            period_end_str = date_match.group() if date_match else str(header)
        method = "statement_df"
    else:
        facts, period_end_str = fallback_xbrl_query_facts(company, needed_concepts, args.period_end, args.form)
        method = "xbrl_fallback"

    ev = Evaluator(mapping=mapping, facts=facts, industry=args.industry, normalize_abs=True)
    standardized = ev.standardize()

    out = {
        "symbol": args.symbol.upper(),
        "financials": [{
            **standardized,
            "period": period_end_str,
            "year": int(period_end_str[:4])
        }],
        "meta": {
            "form": args.form,
            "periodEnd": period_end_str,
            "extraction": method,
            "extractionRate": f"{sum(1 for v in standardized.values() if v is not None)/len(standardized):.1%}"
        }
    }
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()