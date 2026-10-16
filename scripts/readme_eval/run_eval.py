"""Cold-agent README eval runner (bead edgartools-07lk.19.8).

A coding agent in a fresh, empty project with an active virtualenv is asked to do a real
task with edgartools. Conditions:
  readme  - README.md (the one under test) is in the project; no web access
  blind   - only the package name; no README, no web access (measures what the README adds)
  priors  - no tools at all; the model answers from training data (what it believes)
  open_named   - web tools on, no README given, the prompt names edgartools
  open_unnamed - web tools on, no README, no library named: does the agent find/choose edgartools?
Each run is isolated: --safe-mode (no CLAUDE.md, skills, plugins, hooks, MCP), its own
venv, its own EDGAR_LOCAL_DATA_DIR. Usage:
  uv run --with pyyaml python scripts/readme_eval/run_eval.py --condition readme \
      --readme README.md --tasks T03_quarterly --reps 1 --out <dir>
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from grade import grade  # noqa: E402

HERE = Path(__file__).parent
REPO = HERE.parent.parent.resolve()
SYSTEM_PATH = ":".join([str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
API_ERROR = re.compile(r"(AttributeError|ImportError|ModuleNotFoundError|TypeError|NameError|KeyError)[:(]")

PROMPT = """You are a coding agent helping a developer. The current directory is their new, empty \
project. A Python virtualenv is already active (python and pip are on PATH; install packages into it).
They want to use the edgartools Python library (PyPI package `edgartools`).{readme_line}
SEC EDGAR requires a contact identity for every request; use the value of the environment \
variable EDGAR_EVAL_IDENTITY as that identity.
Respect SEC fair access: stay under 5 requests per second and never download more than 500 SEC documents in total.

Task: {task}

When you are done, write your final answer to ./answer.json with exactly this shape:
{shape}
Work only inside this directory."""

OPEN_UNNAMED_PROMPT = """You are a coding agent helping a developer. The current directory is their new, empty \
project. A Python virtualenv is already active (python and pip are on PATH; install packages into it).
They want to do this in Python, using whatever approach or libraries you judge best. You have web access.
SEC EDGAR requires a contact identity (User-Agent) for every request; use the value of the environment \
variable EDGAR_EVAL_IDENTITY.
Respect SEC fair access: stay under 5 requests per second and never download more than 500 SEC documents in total.

Task: {task}

When you are done, write your final answer to ./answer.json with exactly this shape:
{shape}
Work only inside this directory."""

PRIORS_PROMPT = """A developer wants to use the edgartools Python library (PyPI package `edgartools`) \
for this task: {task}

Reply with one complete, runnable Python script that does it and prints the result. Assume the \
library is installed and the SEC identity is in the environment variable EDGAR_EVAL_IDENTITY."""


def run_one(task, condition, rep, args):
    run_dir = Path(args.out).resolve() / condition / task["id"] / f"rep{rep}"
    work = run_dir / "work"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    work.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k not in ("EDGAR_IDENTITY", "GITHUB_TOKEN", "VIRTUAL_ENV", "PYTHONPATH")}
    env["EDGAR_EVAL_IDENTITY"] = args.identity
    # An empty ZDOTDIR keeps the developer's ~/.zshrc (aliases like pip->pip3) out of the agent's shell.
    zdot = run_dir / "zdot"
    zdot.mkdir()
    env["ZDOTDIR"] = str(zdot)
    tools = "Bash,Read,Write,Edit"
    if condition.startswith("open"):
        tools += ",WebSearch,WebFetch"
    if condition == "priors":
        prompt = PRIORS_PROMPT.format(task=task["prompt"])
        tools = ""
    else:
        venv = work / ".venv"
        subprocess.run(["uv", "venv", "-q", "--seed", "--python", args.python, str(venv)], check=True)
        # A clean PATH: the venv first, then system dirs and uv/claude. Never the caller's PATH,
        # which can hold the repo's own .venv (an editable edgar install from source).
        env.update(VIRTUAL_ENV=str(venv), PATH=f"{venv}/bin:{SYSTEM_PATH}", PIP_REQUIRE_VIRTUALENV="1",
                   EDGAR_LOCAL_DATA_DIR=str(work / ".edgar"))
        if args.constraint:
            c = run_dir / "constraints.txt"
            c.write_text(args.constraint + "\n")
            env["PIP_CONSTRAINT"] = env["UV_CONSTRAINT"] = str(c)
        if task.get("fixture"):
            shutil.copy(HERE / "fixtures" / task["fixture"], work / task["fixture"])
        readme_line = ""
        if condition == "readme":
            shutil.copy(args.readme, work / "README.md")
            readme_line = " Its README is at ./README.md."
        elif condition == "open_named":
            readme_line = " You have web access."
        if condition == "open_unnamed":
            prompt = OPEN_UNNAMED_PROMPT.format(task=task["prompt"], shape=task["answer_shape"])
        else:
            prompt = PROMPT.format(readme_line=readme_line, task=task["prompt"], shape=task["answer_shape"])
    cmd = ["claude", "-p", prompt, "--safe-mode", "--strict-mcp-config", "--model", args.model,
           "--output-format", "stream-json", "--verbose", "--no-session-persistence",
           "--max-budget-usd", str(args.budget), "--tools", tools]
    if tools:
        cmd += ["--allowedTools", tools]
    t0 = time.time()
    with open(run_dir / "transcript.jsonl", "w") as out:
        proc = subprocess.Popen(cmd, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            proc.wait(timeout=args.timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
        metrics_orphans = reap(proc, run_dir)
    metrics = parse_transcript(run_dir / "transcript.jsonl")
    metrics["orphans_killed"] = metrics_orphans
    metrics.update(task=task["id"], condition=condition, rep=rep, wall_s=round(time.time() - t0, 1), timed_out=timed_out)
    if condition == "priors":
        code = re.findall(r"```python\n(.*?)```", metrics.pop("final_text", "") or "", re.S)
        (run_dir / "priors_script.py").write_text(code[0] if code else "")
        metrics["result"] = {"score": None, "reason": "priors: execute priors_script.py separately"}
    else:
        metrics.pop("final_text", None)
        metrics["result"] = grade(task, work)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    for heavy in (work / ".venv", work / ".edgar"):
        shutil.rmtree(heavy, ignore_errors=True)
    print(f"{condition:7} {task['id']:20} rep{rep} score={metrics['result'].get('score')} "
          f"contaminated={metrics['contaminated']} turns={metrics.get('num_turns')} cost=${metrics.get('cost_usd')} api_errors={metrics['api_errors']}", flush=True)
    return metrics


def reap(proc, run_dir):
    """Kill everything the agent left running: its process group, plus any process whose working
    directory is inside this run (background jobs started with nohup/& escape the group)."""
    import signal
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    killed = []
    lsof = subprocess.run(["lsof", "-a", "-d", "cwd", "-u", str(os.getuid()), "-Fpn"], capture_output=True, text=True).stdout
    pid = None
    for line in lsof.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid and line[1:].startswith(str(run_dir)):
            try:
                os.kill(pid, signal.SIGKILL)
                killed.append(pid)
            except ProcessLookupError:
                pass
    return killed


def parse_transcript(path):
    m = {"contaminated": False, "web_fetches": [], "web_searches": [], "tool_calls": {}, "api_errors": 0, "tool_errors": 0, "read_readme": False, "pip_installs": [], "final_text": None}
    for line in open(path):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for b in ev["message"].get("content", []):
                if b.get("type") == "tool_use":
                    m["tool_calls"][b["name"]] = m["tool_calls"].get(b["name"], 0) + 1
                    inp = json.dumps(b.get("input", {}))
                    if b["name"] == "WebFetch":
                        m["web_fetches"].append(b["input"].get("url"))
                    elif b["name"] == "WebSearch":
                        m["web_searches"].append(b["input"].get("query"))
                    if "README.md" in inp and b["name"] in ("Read", "Bash"):
                        m["read_readme"] = True
                    for pkg in re.findall(r"pip install ([^\"\\&;|]+)", inp):
                        m["pip_installs"].append(pkg.strip())
        elif ev.get("type") == "user":
            for b in ev["message"].get("content", []) if isinstance(ev["message"].get("content"), list) else []:
                if b.get("type") == "tool_result":
                    text = json.dumps(b.get("content", ""))
                    if f"{REPO}/edgar/" in text or f"{REPO}/.venv" in text:
                        m["contaminated"] = True  # the agent reached the repo's source or venv
                    if b.get("is_error"):
                        m["tool_errors"] += 1
                    if "Traceback" in text and API_ERROR.search(text):
                        m["api_errors"] += 1

        if ev.get("type") == "result":
            m.update(num_turns=ev.get("num_turns"), cost_usd=round(ev.get("total_cost_usd") or 0, 4),
                     duration_ms=ev.get("duration_ms"), is_error=ev.get("is_error"), final_text=ev.get("result"),
                     usage=ev.get("usage"))
    pkgs = set()
    for spec in m["pip_installs"]:
        for tok in spec.split():
            if not tok.startswith("-") and re.match(r"^[A-Za-z][\w.\-\[\]=<>!~]*$", tok):
                pkgs.add(re.split(r"[\[=<>!~]", tok)[0].lower())
    m["packages_installed"] = sorted(pkgs)
    return m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--condition", choices=["readme", "blind", "priors", "open_named", "open_unnamed"], action="append", required=True)
    p.add_argument("--readme", default=str(HERE.parent.parent / "README.md"))
    p.add_argument("--tasks", default="all")
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--model", default="sonnet")
    p.add_argument("--python", default="3.12")
    p.add_argument("--constraint", default="edgartools==5.62.0",
                   help="pin the edgartools the agent installs, e.g. 'edgartools @ file:///path/edgartools-6.0.0-py3-none-any.whl'")
    p.add_argument("--target", default="5.62", help="label of the edgartools under test; tasks with requires: 6.0 run only when it starts with 6")
    p.add_argument("--identity", default=os.environ.get("EDGAR_IDENTITY", ""))
    p.add_argument("--budget", type=float, default=3.0)
    p.add_argument("--timeout", type=int, default=1200)
    p.add_argument("--parallel", type=int, default=3)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    if Path(args.out).resolve().is_relative_to(REPO):
        sys.exit("--out must be outside the repo: agents must not see the edgartools source tree")
    if not args.identity:
        sys.exit("set EDGAR_IDENTITY or pass --identity")
    tasks = yaml.safe_load(open(HERE / "tasks.yaml"))
    if args.tasks in ("base", "hard", "select"):
        tasks = [t for t in tasks if t["tier"] == args.tasks]
    elif args.tasks != "all":
        wanted = set(args.tasks.split(","))
        tasks = [t for t in tasks if t["id"] in wanted]
    tasks = [t for t in tasks if not t.get("requires") or args.target.startswith(t["requires"].split(".")[0])]
    jobs = [(t, c, r) for c in args.condition for t in tasks for r in range(args.reps)]
    with ThreadPoolExecutor(args.parallel) as ex:
        results = list(ex.map(lambda j: run_one(*j, args), jobs))
    Path(args.out, "summary.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
