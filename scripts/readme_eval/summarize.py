"""Summarize a cold-agent eval out dir into a markdown table (condition x task).
Usage: python3 scripts/readme_eval/summarize.py <out_dir>"""
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

out = Path(sys.argv[1])
rows = [json.loads(p.read_text()) for p in out.glob("*/*/rep*/metrics.json")]
by = defaultdict(list)
for r in rows:
    by[(r["condition"], r["task"])].append(r)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None


lines = ["| condition | task | n | score | turns | cost $ | api errors | read README |", "|---|---|---|---|---|---|---|---|"]
totals = defaultdict(list)
for (cond, task), rs in sorted(by.items()):
    if cond == "priors":
        continue
    s = mean([r["result"].get("score") for r in rs])
    totals[cond].extend(rs)
    lines.append(f"| {cond} | {task} | {len(rs)} | {s:.2f} | {mean([r.get('num_turns') for r in rs]):.1f} | "
                 f"{mean([r.get('cost_usd') for r in rs]):.3f} | {mean([r['api_errors'] for r in rs]):.1f} | "
                 f"{sum(r['read_readme'] for r in rs)}/{len(rs)} |")
lines.append("")
lines.append("| condition | runs | mean score | perfect runs | mean turns | total cost $ | mean api errors | read README |")
lines.append("|---|---|---|---|---|---|---|---|")
for cond, rs in sorted(totals.items()):
    scores = [r["result"].get("score") or 0 for r in rs]
    lines.append(f"| {cond} | {len(rs)} | {st.mean(scores):.3f} | {sum(s == 1 for s in scores)}/{len(rs)} | "
                 f"{mean([r.get('num_turns') for r in rs]):.1f} | {sum(r.get('cost_usd') or 0 for r in rs):.2f} | "
                 f"{mean([r['api_errors'] for r in rs]):.2f} | {sum(r['read_readme'] for r in rs)}/{len(rs)} |")
print("\n".join(lines))
