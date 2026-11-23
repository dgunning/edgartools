"""
GitHub issue bookkeeping shared by the scheduled bug-finding jobs.

A sweep finds failures; this module turns them into issues a person can act on,
without flooding the tracker. It follows the contract of
``scripts/scan_successor_registrants.py``:

- **The issues hold the state.** Each failure issue carries a hidden
  ``<!-- sweep-signature: <job>:<digest> -->`` marker. A signature that has an
  issue, open or closed, is never filed again: closing the issue is the decision
  (fixed, or not worth fixing). A closed signature that shows up again is listed
  in the run's scorecard, so a regression is visible without reopening anything.
- **One rolling scorecard issue per job**, marked
  ``<!-- sweep-scorecard: <job> -->``. Each run comments on it with that run's
  scorecard, so the history of a job is one thread.
- **Signatures survive edits.** An exception is keyed by its type and the
  innermost frame inside ``edgar/`` (module and function, not line number), so
  moving code does not re-file a known failure, and two different bugs that raise
  the same type from different places are filed apart.

Nothing here talks to the SEC. ``gh`` is shelled out to, as in the successor scan.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

SIGNATURE_RE = re.compile(r"<!-- sweep-signature: ([\w.-]+):([0-9a-f]{12}) -->")
SCORECARD_RE = re.compile(r"<!-- sweep-scorecard: ([\w.-]+) -->")

# GitHub rejects issue bodies and comments over 65,536 characters.
MAX_BODY = 60_000
MAX_EXAMPLES = 5

# A frame line in a formatted traceback: '  File ".../edgar/xbrl/xbrl.py", line 42, in parse'
_FRAME_RE = re.compile(r'File "(?P<path>[^"]+)", line \d+, in (?P<func>[\w<>.]+)')
# Exceptions that mean SEC or the network misbehaved, not the library.
TRANSIENT_ERRORS = frozenset({
    "TransportError", "ConnectError", "ConnectTimeout", "ReadTimeout", "ReadError", "WriteTimeout",
    "PoolTimeout", "RemoteProtocolError", "TimeoutException", "TooManyRequestsError",
    "HTTPStatusError", "SSLError", "_FilingTimeoutError", "TimeoutError",
})


def edgar_frame(traceback_text: str) -> str:
    """The innermost frame inside the ``edgar`` package, as ``module.path:function``.

    Returns '' when no frame is inside ``edgar/`` (the failure is in a dependency
    called from the script itself, or the traceback was truncated).
    """
    found = ''
    for m in _FRAME_RE.finditer(traceback_text or ''):
        path = m.group('path').replace('\\', '/')
        if '/edgar/' not in path:   # the checkout dir 'edgartools/' does not match
            continue
        module = path.rsplit('/edgar/', 1)[-1]
        if module.endswith('.py'):
            module = module[:-3]
        found = f"edgar/{module}:{m.group('func')}"
    return found


def signature(job: str, error_type: str, traceback_text: str, stage: str = '') -> str:
    """A 12-hex-digit key for one kind of failure in one job.

    The key is the exception type, the stage that raised (which entry point), and
    the innermost ``edgar/`` frame. Messages and line numbers are left out because
    they vary between filings and commits for the same bug.
    """
    key = '|'.join((job, error_type or '', stage or '', edgar_frame(traceback_text)))
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def is_transient(error_type: str) -> bool:
    return (error_type or '') in TRANSIENT_ERRORS


@dataclass
class Failure:
    """One failing filing in one stage."""
    accession: str
    form: str
    company: str
    stage: str
    error_type: str
    error_message: str
    traceback: str = ''


@dataclass
class Signature:
    """Every failure in a run that shares one signature."""
    job: str
    digest: str
    error_type: str
    stage: str
    frame: str
    failures: List[Failure] = field(default_factory=list)

    @property
    def title(self) -> str:
        where = self.frame or 'outside edgar/'
        return f"[{self.job} sweep] {self.error_type} in {self.stage}: {where}"


def group_failures(job: str, failures: Iterable[Failure]) -> List[Signature]:
    """Group library failures by signature, most frequent first.

    Left out: transient network/SEC errors, and failures with no frame inside
    ``edgar/``, which were raised by the sweep's own code rather than the library.
    """
    groups: Dict[str, Signature] = {}
    for f in failures:
        if is_transient(f.error_type) or not edgar_frame(f.traceback):
            continue
        digest = signature(job, f.error_type, f.traceback, f.stage)
        if digest not in groups:
            groups[digest] = Signature(job, digest, f.error_type, f.stage, edgar_frame(f.traceback))
        groups[digest].failures.append(f)
    return sorted(groups.values(), key=lambda s: (-len(s.failures), s.digest))


@dataclass
class Plan:
    to_file: List[Signature]
    known_open: List[tuple]        # (Signature, issue number)
    seen_again_closed: List[tuple]  # (Signature, issue number)


def known_signatures(issues: Iterable[dict], job: str) -> Dict[str, dict]:
    """Map digest -> issue for every issue (open or closed) carrying this job's signature marker."""
    known = {}
    for issue in issues:
        for j, digest in SIGNATURE_RE.findall(issue.get('body') or ''):
            if j == job:
                known.setdefault(digest, issue)
    return known


def plan(signatures: Sequence[Signature], issues: Iterable[dict], job: str) -> Plan:
    """Decide which signatures get a new issue. Pure, so it can be tested offline."""
    known = known_signatures(issues, job)
    to_file, known_open, closed = [], [], []
    for s in signatures:
        issue = known.get(s.digest)
        if issue is None:
            to_file.append(s)
        elif str(issue.get('state', '')).upper() == 'OPEN':
            known_open.append((s, issue['number']))
        else:
            closed.append((s, issue['number']))
    return Plan(to_file, known_open, closed)


def _md(text: str) -> str:
    return (text or '').replace('|', '\\|').replace('\n', ' ')


def failure_issue_body(s: Signature, run_label: str) -> str:
    lines = [
        f"The scheduled **{s.job} sweep** ({run_label}) raised `{s.error_type}` in `{s.stage}` "
        f"on {len(s.failures)} filing(s).",
        '',
        f"- **Innermost edgar frame:** `{s.frame or 'none (raised outside edgar/)'}`",
        '',
        '| Filing | Form | Company | Message |',
        '|---|---|---|---|',
    ]
    for f in s.failures[:MAX_EXAMPLES]:
        lines.append(f"| {f.accession} | {_md(f.form)} | {_md(f.company)[:60]} | {_md(f.error_message)[:160]} |")
    if len(s.failures) > MAX_EXAMPLES:
        lines.append(f"\n{len(s.failures) - MAX_EXAMPLES} more filing(s) in the run's artifacts.")
    tb = s.failures[0].traceback
    if tb:
        lines += ['', '<details><summary>Traceback (first filing)</summary>', '', '```',
                  tb.replace(' || ', '\n')[:4000], '```', '</details>']
    lines += ['', 'Reproduce with `find("<accession>")` and the stage named above. '
              'This issue is never re-filed: close it once fixed, or with the reason it will not be.',
              '', f"<!-- sweep-signature: {s.job}:{s.digest} -->"]
    return '\n'.join(lines)[:MAX_BODY]


def plan_summary(p: Plan) -> str:
    """Markdown lines for the scorecard comment: what this run filed, saw again, or found regressed."""
    lines = []
    if p.to_file:
        lines.append(f"- New failure signatures: {len(p.to_file)}")
    if p.known_open:
        lines.append('- Still failing (open issue): ' + ', '.join(
            f"#{n} ({len(s.failures)})" for s, n in p.known_open))
    if p.seen_again_closed:
        lines.append('- **Seen again after the issue was closed:** ' + ', '.join(
            f"#{n} ({len(s.failures)})" for s, n in p.seen_again_closed))
    return '\n'.join(lines) or '- No failures.'


# ---------------------------------------------------------------------------
# gh
# ---------------------------------------------------------------------------

def _gh(*args: str) -> str:
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True).stdout


def list_issues(repo: str, label: str) -> List[dict]:
    return json.loads(_gh('issue', 'list', '--repo', repo, '--label', label, '--state', 'all',
                          '--limit', '1000', '--json', 'number,title,state,body'))


def ensure_label(repo: str, label: str, description: str) -> None:
    try:
        _gh('label', 'create', label, '--repo', repo, '--color', 'C5DEF5', '--description', description)
    except subprocess.CalledProcessError:
        pass  # the label exists


def file_issue(repo: str, label: str, title: str, body: str) -> str:
    return _gh('issue', 'create', '--repo', repo, '--label', label, '--title', title, '--body', body).strip()


def scorecard_issue(issues: Iterable[dict], job: str) -> Optional[int]:
    """The open rolling scorecard issue for ``job``, if any."""
    for issue in issues:
        if str(issue.get('state', '')).upper() != 'OPEN':
            continue
        if job in SCORECARD_RE.findall(issue.get('body') or ''):
            return issue['number']
    return None


def post_scorecard(repo: str, label: str, job: str, title: str, comment: str, issues: Iterable[dict]) -> str:
    """Comment on the job's rolling scorecard issue, creating it on the first run."""
    comment = comment[:MAX_BODY]
    number = scorecard_issue(issues, job)
    if number is None:
        body = (f"Rolling scorecard for the scheduled **{job} sweep**. Each run adds a comment. "
                f"Failures are filed as separate issues with the `{label}` label.\n\n"
                f"<!-- sweep-scorecard: {job} -->")
        url = file_issue(repo, label, title, body)
        number = int(url.rstrip('/').rsplit('/', 1)[-1])
    return _gh('issue', 'comment', str(number), '--repo', repo, '--body', comment).strip()


def publish(repo: Optional[str], *, job: str, label: str, label_description: str, scorecard_title: str,
            scorecard_md: str, signatures: Sequence[Signature], run_label: str, dry_run: bool) -> Plan:
    """File new signatures and post the scorecard. With ``dry_run`` only print what would happen."""
    issues = [] if dry_run and not repo else list_issues(repo, label)
    p = plan(signatures, issues, job)
    comment = f"{scorecard_md}\n\n### Failures\n\n{plan_summary(p)}"
    if dry_run:
        for s in p.to_file:
            print(f"would file: {s.title} ({len(s.failures)} filing(s))")
        print(f"would comment on the {job} scorecard issue:\n{comment[:2000]}")
        return p
    ensure_label(repo, label, label_description)
    for s in p.to_file:
        print('filed', file_issue(repo, label, s.title, failure_issue_body(s, run_label)))
    print('scorecard', post_scorecard(repo, label, job, scorecard_title, comment, issues))
    return p
