"""Capture and diff the *shape* of a DataFrame, not its values.

This exists because of a downstream incident reported on GH #929: an upgrade
changed the null sentinel of the `decimals` column from None to NaN, which
silently disabled a consumer's `x in (None, "<NA>")` filter. The output was
value-correct and neither slower nor larger, so a timing-and-memory harness
would have recorded a clean pass.

Three things are captured per column, and the distinction between them is the
whole point:

  columns       asserted as a SET — a column appearing or vanishing is breaking.
  dtype family  asserted COARSELY — int64 vs Int64 vs float64 differ legitimately
                across corpus files (one file has a null in that column, another
                does not), so asserting the exact dtype produces failures that
                reviewers learn to mute. Family is int/float/bool/str/datetime/...
  null token    asserted EXACTLY — None, NaN, pd.NA and NaT are not
                interchangeable to a downstream filter. This is the incident.

Nothing here looks at values. Two runs over different data are expected to
produce the same snapshot; that is what makes a diff meaningful.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api import types as pdt


def dtype_family(dtype) -> str:
    """Coarse dtype bucket. Deliberately blind to width and to nullability."""
    if pdt.is_bool_dtype(dtype):
        return "bool"
    if pdt.is_integer_dtype(dtype):
        return "integer"
    if pdt.is_float_dtype(dtype):
        return "float"
    if pdt.is_datetime64_any_dtype(dtype):
        return "datetime"
    if pdt.is_timedelta64_dtype(dtype):
        return "timedelta"
    if isinstance(dtype, pd.CategoricalDtype):
        return "categorical"
    if pdt.is_string_dtype(dtype) and dtype != object:
        return "string"
    if dtype == object:
        return "object"
    return str(dtype)


def _token_for(value: Any) -> str:
    """Name the specific null sentinel. Identity checks, not truthiness."""
    if value is None:
        return "None"
    if value is pd.NaT:
        return "NaT"
    if value is pd.NA:
        return "pd.NA"
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    return f"other:{type(value).__name__}"


def null_tokens(series: pd.Series) -> list[str]:
    """Which null sentinels actually occur in this column.

    An object column can hold None and NaN simultaneously, and a consumer
    filtering for one will silently miss the other — so this returns every
    distinct token found, sorted, rather than a single answer.
    """
    mask = series.isna()
    if not mask.any():
        return []

    dtype = series.dtype
    # Non-object dtypes have exactly one possible sentinel; skip the scan.
    if pdt.is_datetime64_any_dtype(dtype) or pdt.is_timedelta64_dtype(dtype):
        return ["NaT"]
    if dtype != object and not isinstance(dtype, pd.CategoricalDtype):
        # Numpy floats carry NaN; pandas extension dtypes carry pd.NA.
        return ["NaN"] if pdt.is_float_dtype(dtype) else ["pd.NA"]

    tokens: set[str] = set()
    for value in series[mask]:
        tokens.add(_token_for(value))
        if len(tokens) > 1:  # mixed sentinels: the interesting case, stop early
            break
    return sorted(tokens)


def snapshot(df: pd.DataFrame, *, label: str | None = None) -> dict:
    """Structural fingerprint of a DataFrame."""
    columns = {}
    for name in df.columns:
        series = df[name]
        columns[str(name)] = {
            "dtype_family": dtype_family(series.dtype),
            "dtype_exact": str(series.dtype),  # recorded, not asserted
            "null_tokens": null_tokens(series),
            "all_null": bool(series.isna().all()) if len(series) else None,
        }
    snap = {
        "column_order": [str(c) for c in df.columns],
        "columns": columns,
        "row_count": int(len(df)),          # informational
        "index_dtype_family": dtype_family(df.index.dtype),
    }
    if label:
        snap["label"] = label
    return snap


# --- diffing ---------------------------------------------------------------

def diff(before: dict, after: dict) -> dict:
    """Compare two snapshots. Separates breaking changes from advisory ones."""
    b_cols, a_cols = before.get("columns", {}), after.get("columns", {})
    b_names, a_names = set(b_cols), set(a_cols)

    breaking, advisory = [], []

    for name in sorted(b_names - a_names):
        breaking.append(f"column removed: {name}")
    for name in sorted(a_names - b_names):
        breaking.append(f"column added: {name}")

    for name in sorted(b_names & a_names):
        b, a = b_cols[name], a_cols[name]
        if b["dtype_family"] != a["dtype_family"]:
            breaking.append(
                f"{name}: dtype family {b['dtype_family']} -> {a['dtype_family']}")
        elif b["dtype_exact"] != a["dtype_exact"]:
            advisory.append(
                f"{name}: dtype {b['dtype_exact']} -> {a['dtype_exact']} (same family)")
        if b["null_tokens"] != a["null_tokens"]:
            # The incident. A column that had nulls and now has none is advisory
            # (the data differed); a change of sentinel is breaking.
            if b["null_tokens"] and a["null_tokens"]:
                breaking.append(
                    f"{name}: null sentinel {b['null_tokens']} -> {a['null_tokens']}")
            else:
                advisory.append(
                    f"{name}: null sentinel {b['null_tokens'] or 'none present'} -> "
                    f"{a['null_tokens'] or 'none present'}")

    if before.get("column_order") != after.get("column_order") and not (b_names ^ a_names):
        advisory.append("column order changed (same set)")
    if before.get("index_dtype_family") != after.get("index_dtype_family"):
        breaking.append(
            f"index: dtype family {before.get('index_dtype_family')} -> "
            f"{after.get('index_dtype_family')}")

    return {"breaking": breaking, "advisory": advisory}


def render_diff(name: str, result: dict) -> str:
    """Human-readable diff for a PR comment."""
    if not result["breaking"] and not result["advisory"]:
        return f"  {name}: no schema change"
    lines = [f"  {name}:"]
    for item in result["breaking"]:
        lines.append(f"    BREAKING  {item}")
    for item in result["advisory"]:
        lines.append(f"    advisory  {item}")
    return "\n".join(lines)


def compare_files(before_path: str | Path, after_path: str | Path) -> int:
    """Diff two schema JSON files. Returns the number of breaking changes."""
    before = json.loads(Path(before_path).read_text())
    after = json.loads(Path(after_path).read_text())

    total_breaking = 0
    for name in sorted(set(before) | set(after)):
        if name not in before:
            print(f"  {name}: new surface (no baseline)")
            continue
        if name not in after:
            print(f"  {name}: MISSING from this run")
            total_breaking += 1
            continue
        result = diff(before[name], after[name])
        total_breaking += len(result["breaking"])
        print(render_diff(name, result))
    return total_breaking


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 3:
        n = compare_files(sys.argv[1], sys.argv[2])
        print(f"\n{n} breaking schema change(s)")
        raise SystemExit(1 if n else 0)

    # Self-check: reproduce the reported incident and confirm it is caught.
    before = snapshot(pd.DataFrame({"decimals": [None, None], "value": [1.0, 2.0]}))
    after = snapshot(pd.DataFrame({"decimals": [float("nan")] * 2, "value": [1.0, 2.0]}))
    result = diff(before, after)
    print(render_diff("facts.to_dataframe()", result))
    assert any("null sentinel" in b for b in result["breaking"]), result
    print("\nself-check passed: the GH #929 None -> NaN incident is caught as BREAKING")
