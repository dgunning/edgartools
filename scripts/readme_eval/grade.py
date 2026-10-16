"""Grade one cold-agent run directory against its task's ground truth."""
import json
import re
from pathlib import Path


def _norm(s):
    return re.sub(r"\s+", " ", s).replace("’", "'").replace("“", '"').replace("”", '"')


def _num(x):
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x.replace(",", "").replace("$", ""))
        except ValueError:
            return None
    return None


def _close(got, want, tol):
    g = _num(got)
    return g is not None and (abs(g - want) <= tol * abs(want) if tol else g == want)


def grade(task, run_dir):
    run_dir = Path(run_dir)
    g = task["grade"]
    kind = g["kind"]
    answer = None
    ans_file = run_dir / "answer.json"
    if ans_file.exists():
        try:
            answer = json.loads(ans_file.read_text())
        except json.JSONDecodeError:
            return {"score": 0.0, "reason": "answer.json is not valid JSON"}
    if kind in ("section_file", "markdown_file"):
        f = run_dir / g["file"]
        if not f.exists():
            return {"score": 0.0, "reason": f"{g['file']} missing"}
        text = f.read_text(errors="ignore")
        n = _norm(text)
        checks = {}
        if kind == "section_file":
            for p in g["must_contain"]:
                checks[f"has:{p[:30]}"] = _norm(p) in n
            for p in g["must_not_contain"]:
                checks[f"lacks:{p[:30]}"] = _norm(p) not in n
            checks["length"] = g["min_chars"] <= len(n) <= g["max_chars"]
        else:
            rows = sum(1 for line in text.splitlines() if line.strip().startswith("|"))
            checks["min_chars"] = len(text) >= g["min_chars"]
            checks["table_rows"] = rows >= g["min_table_rows"]
            checks["has_item7"] = any(p in text for p in g["must_contain_any"])
        return {"score": sum(checks.values()) / len(checks), "checks": checks, "chars": len(n)}
    if kind == "composite":
        parts = [grade({"grade": p["grade"], "truth": p.get("truth", {})}, run_dir) for p in g["parts"]]
        return {"score": sum(p["score"] for p in parts) / len(parts), "parts": parts}
    if answer is None:
        return {"score": 0.0, "reason": "answer.json missing"}
    truth = task["truth"]
    if kind == "numbers":
        checks = {k: _close(answer.get(k), v, g["tolerance"]) for k, v in truth.items()}
    elif kind == "set":
        got = set(answer.get(g["key"]) or [])
        want = set(truth[g["key"]])
        checks = {a: a in got for a in want}
        checks["no_extras"] = got <= want
        if g.get("also_count"):
            checks["count"] = _num(answer.get("count")) == truth["count"]
    elif kind == "ranked_values":
        got = answer.get(g["key"]) or []
        checks = {}
        for i, w in enumerate(truth[g["key"]]):
            item = got[i] if i < len(got) and isinstance(got[i], dict) else {}
            checks[f"{i}:name"] = w["issuer"].lower() in str(item.get("issuer", "")).lower()
            checks[f"{i}:value"] = _close(item.get("value"), w["value"], g["tolerance"])
    elif kind == "changes":
        checks = {}
        for side in ("new", "exited"):
            got = answer.get(side) or []
            got_by = {str(x.get("cusip", "")).upper(): x for x in got if isinstance(x, dict)}
            for w in truth[side]:
                item = got_by.get(w["cusip"])
                checks[f"{side}:{w['cusip']}"] = item is not None
                if "shares" in w:
                    checks[f"{side}:{w['cusip']}:shares"] = item is not None and _close(item.get("shares"), w["shares"], 0)
            checks[f"{side}:no_extras"] = set(got_by) <= {w["cusip"] for w in truth[side]}
    else:
        raise ValueError(kind)
    return {"score": sum(checks.values()) / len(checks), "checks": checks}
