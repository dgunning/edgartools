"""Execute the scripts the 'priors' condition produced (no tools, model memory only) and grade
whether they run and whether the ground-truth values appear in what they print.
Usage: uv run --no-project --with pyyaml python scripts/readme_eval/exec_priors.py <out_dir>
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent


def truth_numbers(task):
    out = []
    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            out.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(task.get("truth", {}))
    return out


def renderings(n):
    # A script may print 70066000000, 70,066,000,000, 70066.0 (millions), 70.066 (billions) ...
    forms = {str(int(n)), f"{int(n):,}"}
    for div in (1e3, 1e6, 1e9):
        if n >= div * 10:
            v = n / div
            forms |= {f"{v:,.0f}", f"{v:.0f}", f"{v:,.1f}", f"{v:.1f}", f"{v:.2f}", f"{v:,.2f}", f"{v:.3f}"}
    return forms


def work_dir(run_dir, tag):
    # Each version runs in its own directory so files a script writes are graded per version.
    d = run_dir / f"exec_{tag}"
    d.mkdir(exist_ok=True)
    return d


def main():
    out = Path(sys.argv[1])
    spec = sys.argv[2] if len(sys.argv) > 2 else "edgartools==5.62.0"
    tag = sys.argv[3] if len(sys.argv) > 3 else "5.62.0"
    tasks = {t["id"]: t for t in yaml.safe_load(open(HERE / "tasks.yaml"))}
    venv = out / f"priors_venv_{tag}"
    if not venv.exists():
        subprocess.run(["uv", "venv", "-q", "--python", "3.12", str(venv)], check=True)
        subprocess.run(["uv", "pip", "install", "-q", "--python", str(venv / "bin/python"), spec], check=True)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
    env["EDGAR_EVAL_IDENTITY"] = os.environ.get("EDGAR_IDENTITY", "")
    rows = []
    for script in sorted(out.glob("priors/*/rep*/priors_script.py")):
        task = tasks[script.parent.parent.name]
        run_dir = script.parent
        code = script.read_text()
        row = {"task": task["id"], "rep": run_dir.name, "has_code": bool(code.strip())}
        if code.strip():
            try:
                p = subprocess.run([str(venv / "bin/python"), str(script)], cwd=work_dir(run_dir, tag), env=env,
                                   capture_output=True, text=True, timeout=600)
                text = p.stdout + p.stderr
                row["exit"] = p.returncode
                err = re.findall(r"^(\w+(?:Error|Exception))\b.*$", p.stderr, re.M)
                row["error"] = err[-1] if err else None
                row["error_line"] = p.stderr.strip().splitlines()[-1][:200] if p.returncode and p.stderr.strip() else None
            except subprocess.TimeoutExpired:
                text, row["exit"], row["error"] = "", "timeout", "timeout"
            nums = truth_numbers(task)
            if nums:
                hits = sum(any(r in text for r in renderings(n)) for n in nums)
                row["truth_hits"] = f"{hits}/{len(nums)}"
            (run_dir / f"priors_output_{tag}.txt").write_text(text[-20000:])
        imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", code, re.M)
        row["imports"] = sorted({i.split(".")[0] for i in imports})
        rows.append(row)
        print(json.dumps(row), flush=True)
    (out / f"priors_summary_{tag}.json").write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
