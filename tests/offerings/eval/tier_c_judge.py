"""
Offerings extraction eval — Tier C (LLM-judge semantic audit).

Tier A/B (run_eval.py) are deterministic: coverage/validity buckets and
internal-redundancy oracles (fee cross-check, lifecycle date arithmetic). They
catch garbage and inconsistency, but they cannot tell whether a *clean, internally
consistent* value is the semantically right one — e.g. whether the extracted
``lead_bookrunner`` is actually the lead agent named on the cover, or merely a
plausible firm name pulled from the wrong sentence.

Tier C closes that gap with an LLM judge that reads the filing's own evidence and
rules on the extracted value. It mirrors ``edgar/ai/evaluation/judge.py``: this
module only *builds prompts* and *parses verdicts* — it never calls a model. The
judging is done by Claude Code subagents (the cc_runner.py pattern), driven
interactively or from a workflow, so there is no API key, no per-run cost, and
nothing non-deterministic in the pytest gate.

    Tier C is an AUDIT, not a gate. Its output is a list of disagreements to
    investigate. A confirmed disagreement becomes a new deterministic Tier B
    oracle or a hand-verified ground-truth anchor in corpus.json — those are what
    guard CI. Tier C finds the work; Tier A/B locks it in.

Workflow (mirrors code-gen → judge):
    1. get_judge_tasks(corpus)        -> [{facet, accession, extracted, evidence, prompt}]
    2. (Claude Code spawns one subagent per task with task["prompt"])
    3. parse_offering_judge_verdict() -> OfferingVerdict per response
    4. summarize_verdicts()           -> the disagreement catalog

Example:
    >>> import json
    >>> from pathlib import Path
    >>> from tier_c_judge import get_judge_tasks, parse_offering_judge_verdict, summarize_verdicts
    >>> corpus = json.loads(Path("corpus.json").read_text())
    >>> tasks = get_judge_tasks(corpus, facet="lead_bookrunner")
    >>> # ... spawn a subagent per task, collect response_text ...
    >>> verdicts = [parse_offering_judge_verdict(text, t["facet"], t["accession"], t["extracted"])
    ...             for text, t in zip(responses, tasks)]
    >>> print(summarize_verdicts(verdicts))
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, List, Optional

# Verdict vocabulary. "uncertain" is first-class: a judge that lacks the evidence
# to rule must say so rather than guess, exactly as the Tier B oracles return None.
VERDICTS = ("correct", "incorrect", "uncertain")
CONFIDENCE = ("high", "medium", "low")


@dataclass
class OfferingVerdict:
    """One judge ruling on one extracted facet value."""

    facet: str
    accession: str
    extracted_value: Any
    verdict: str                      # correct | incorrect | uncertain
    judged_value: Optional[str] = None  # what the judge believes the value should be
    confidence: str = "low"           # high | medium | low
    rationale: str = ""

    @property
    def disagrees(self) -> bool:
        """A confirmed disagreement worth investigating (incorrect + not low-confidence)."""
        return self.verdict == "incorrect" and self.confidence in ("high", "medium")


# =============================================================================
# Prompt building (pure — evidence is passed in, no network here)
# =============================================================================

# Per-facet framing: what the value means and what "right" looks like. Kept tight
# so the judge rules on the evidence, not on priors.
_FACET_SPEC = {
    "lead_bookrunner": {
        "label": "lead bookrunner / lead agent",
        "question": (
            "Is the extracted value the lead underwriter, lead bookrunner, or "
            "(for a best-efforts/ATM/registered-direct deal) the placement or "
            "sales agent that this prospectus names as running the offering? The "
            "lead is the first/most senior agent — not a co-manager, not the "
            "calculation agent, not the trustee, and not a firm named only in "
            "boilerplate or a legend."
        ),
    },
    "fee_capacity": {
        "label": "total registered offering amount (shelf capacity)",
        "question": (
            "Is the extracted dollar amount the maximum aggregate offering price "
            "registered by this filing (or, for an amendment, by the registration "
            "it belongs to)? It should match the 'Maximum Aggregate Offering "
            "Price' the fee table totals to — not a per-security line, not a "
            "carry-forward subtotal, and not the fee itself."
        ),
    },
    "shelf_status": {
        "label": "shelf lifecycle status",
        "question": (
            "Given the timeline of related filings, is the extracted status "
            "right? registered = filed, not yet effective; effective = declared "
            "effective (EFFECT) or an automatic ASR, and not past expiry; "
            "expired = effective but past its Rule 415(a)(5) three-year window; "
            "withdrawn = an RW that was not later rescinded. The three-year clock "
            "runs from the *current* effectiveness, which a re-registration resets."
        ),
    },
}

_JUDGE_PROMPT_TEMPLATE = """\
You are an expert securities analyst auditing one field extracted from an SEC \
offering document. Rule on whether the extracted value is correct, using ONLY \
the evidence below — do not rely on outside knowledge of the issuer.

## Field
{label} (facet: {facet})

## Filing
Accession {accession}

## Extracted value
{extracted}

## What "correct" means
{question}

## Evidence from the filing
{evidence}

## Your ruling
Decide one of:
  - "correct": the evidence supports the extracted value as the {label}.
  - "incorrect": the evidence shows a different value is the {label} (give it in judged_value).
  - "uncertain": the evidence is insufficient to rule. Prefer this over guessing.

Set confidence to "high" only when the evidence is explicit and unambiguous.

Respond with ONLY a JSON object, no other text:
{{"verdict": "correct|incorrect|uncertain", "judged_value": "the right value, \
or null if you can't determine it / it agrees", "confidence": "high|medium|low", \
"rationale": "one or two sentences grounded in the evidence"}}"""


def build_offering_judge_prompt(
    facet: str,
    accession: str,
    extracted_value: Any,
    evidence: str,
) -> str:
    """Create a judge prompt for one extracted facet value.

    Pure: ``evidence`` is supplied by the caller (gather_evidence does the
    network work). Raises KeyError for an unknown facet so a typo fails loudly
    rather than producing an unscoped prompt.
    """
    spec = _FACET_SPEC[facet]
    shown = "(no value extracted — None)" if extracted_value is None else repr(extracted_value)
    return _JUDGE_PROMPT_TEMPLATE.format(
        label=spec["label"],
        facet=facet,
        accession=accession,
        extracted=shown,
        question=spec["question"],
        evidence=evidence.strip() or "(no evidence gathered)",
    )


# =============================================================================
# Verdict parsing (pure — mirrors judge.py's tolerant JSON extraction)
# =============================================================================

def parse_offering_judge_verdict(
    response_text: str,
    facet: str,
    accession: str,
    extracted_value: Any,
) -> OfferingVerdict:
    """Extract a verdict from a judge subagent response.

    Tolerates raw JSON and markdown-fenced JSON. On any parse failure the verdict
    is "uncertain" (never a false "incorrect") so a malformed response can't
    manufacture a disagreement.
    """
    json_str = _extract_json(response_text)
    if json_str is None:
        return _uncertain(facet, accession, extracted_value,
                          f"[parse error] no JSON in response: {response_text[:160]}")
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return _uncertain(facet, accession, extracted_value,
                          f"[parse error] invalid JSON: {json_str[:160]}")
    if not isinstance(data, dict):
        return _uncertain(facet, accession, extracted_value,
                          f"[parse error] expected JSON object, got {type(data).__name__}")

    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS:
        return _uncertain(facet, accession, extracted_value,
                          f"[parse error] unknown verdict {verdict!r}")

    confidence = str(data.get("confidence", "low")).strip().lower()
    if confidence not in CONFIDENCE:
        confidence = "low"

    judged = data.get("judged_value")
    judged = None if judged is None else str(judged)

    return OfferingVerdict(
        facet=facet,
        accession=accession,
        extracted_value=extracted_value,
        verdict=verdict,
        judged_value=judged,
        confidence=confidence,
        rationale=str(data.get("rationale", "")),
    )


def _extract_json(text: str) -> Optional[str]:
    """Extract a JSON object from text, handling markdown code fences."""
    text = text.strip()
    md = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if md:
        return md.group(1).strip()
    # Greedy outer-brace match so a nested-quote rationale isn't truncated.
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    return brace.group(0) if brace else None


def _uncertain(facet: str, accession: str, extracted: Any, msg: str) -> OfferingVerdict:
    return OfferingVerdict(
        facet=facet,
        accession=accession,
        extracted_value=extracted,
        verdict="uncertain",
        confidence="low",
        rationale=msg,
    )


# =============================================================================
# Evidence gathering (network — pulls the grounding text from the real filing)
# =============================================================================

# Cover-page signals that surround the lead agent across deal types.
_AGENT_KEYWORDS = (
    "book-running", "bookrunning", "book running", "underwriter", "underwriting",
    "placement agent", "sales agent", "selling agent", "sales agreement",
    "we have engaged", "acting as", "representative",
)


def _keyword_windows(text: str, keywords, radius: int = 320, limit: int = 6) -> str:
    """Concatenated ±radius windows around the first occurrences of keywords."""
    lowered = text.lower()
    spans: List[tuple] = []
    for kw in keywords:
        i = lowered.find(kw.lower())
        if i >= 0:
            spans.append((max(0, i - radius), min(len(text), i + radius)))
    if not spans:
        return ""
    spans.sort()
    merged = [spans[0]]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    chunks = [re.sub(r"\s+", " ", text[s:e]).strip() for s, e in merged[:limit]]
    return "\n---\n".join(chunks)


def gather_evidence(facet: str, filing, max_chars: int = 4000) -> str:
    """Pull the grounding text a judge needs to rule on ``facet`` for ``filing``.

    Network: fetches and parses the filing. Returns a compact, human-readable
    snippet — cover windows for the agent, the fee-table region for capacity, the
    related-filing timeline for status. Best-effort: returns "" on any failure so
    the judge simply rules "uncertain" rather than the harness crashing.
    """
    try:
        if facet == "lead_bookrunner":
            return _evidence_lead(filing, max_chars)
        if facet == "fee_capacity":
            return _evidence_fee(filing, max_chars)
        if facet == "shelf_status":
            return _evidence_shelf(filing, max_chars)
    except Exception as ex:  # noqa: BLE001 — evidence is best-effort
        return f"(evidence unavailable: {type(ex).__name__}: {ex})"
    return ""


def _evidence_lead(filing, max_chars: int) -> str:
    text = filing.parse().text()
    cover = text[:8000]
    # Defined terms and the labeled field go FIRST — they're the load-bearing
    # evidence for structured notes, and must survive max_chars truncation.
    header: List[str] = []
    # Labeled "Selling Agent:  <name>" field (full text — the summary box can sit
    # past the cover head; the colon distinguishes it from the note-title banner).
    field = re.search(r"Selling\s+Agents?:\s*\S[^\n]{0,60}", text)
    if field:
        header.append(re.sub(r"\s+", " ", field.group(0)).strip())
    # Abbreviation definitions '<Full Name> ("ABBR")' so the judge can resolve a
    # tag like "BofAS" to the firm name the extractor reported.
    defs = re.findall(r"[A-Z][A-Za-z0-9 ,.&'\-]{3,45}?\(\s*[\"“][A-Za-z&.']{2,10}[\"”]\s*\)", text)
    header += [re.sub(r"\s+", " ", d).strip() for d in defs[:5]]

    windows = _keyword_windows(cover, _AGENT_KEYWORDS)
    body = windows or re.sub(r"\s+", " ", cover[:2000]).strip()
    parts = []
    if header:
        parts.append("Defined terms / labeled fields:\n" + "\n".join(dict.fromkeys(header)))
    parts.append("Cover-page excerpts (agent context):\n" + body)
    return "\n\n".join(parts)[:max_chars]


def _evidence_fee(filing, max_chars: int) -> str:
    from edgar.offerings._fee_table import _get_filing_fees_attachment, _resolve_fee_source
    att = _get_filing_fees_attachment(filing)
    source_note = ""
    if att is None:
        source = _resolve_fee_source(filing)
        if source is None:
            return "(no EX-FILING-FEES exhibit and no fee-bearing registration in the filing family)"
        att = _get_filing_fees_attachment(source)
        source_note = (f"[fee exhibit recovered from related registration "
                       f"{source.form} {source.accession_no} dated {source.filing_date}]\n")
        if att is None:
            return source_note + "(related registration has no parseable fee exhibit)"
    import html
    raw = att.download()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    # Strip tags, then decode entities (&nbsp;, &amp;, &#8220; …) so the judge
    # reads clean prose rather than markup noise.
    plain = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    plain = re.sub(r"\s+", " ", plain.replace("\xa0", " ")).strip()
    # Center the window on the aggregate-offering region when present.
    anchor = plain.lower().find("maximum aggregate offering price")
    if anchor < 0:
        anchor = plain.lower().find("amount registered")
    window = plain[max(0, anchor - 200): anchor + 1400] if anchor >= 0 else plain[:1600]
    return (source_note + "Registration fee table (text):\n" + window)[:max_chars]


def _evidence_shelf(filing, max_chars: int) -> str:
    related = filing.related_filings()
    rows = sorted(((str(f.filing_date), f.form, f.accession_no) for f in related),
                  key=lambda r: r[0])
    lines = [f"  {d}  {form:10} {acc}" for d, form, acc in rows]
    return ("Related-filing timeline (file-number family), oldest first:\n"
            + "\n".join(lines)
            + "\n\n(registered=filed only; EFFECT or ASR = effective; "
              "RW=withdrawal request, RW WD=rescinds it; 424B*=takedown. "
              "Expiry = current effectiveness + 3 years.)")[:max_chars]


# =============================================================================
# Orchestration — build the task list Claude Code drives with subagents
# =============================================================================

def get_judge_tasks(corpus: List[dict], facet: Optional[str] = None,
                    only_buckets=("ok", "deferred")) -> List[dict]:
    """Build judge tasks for the corpus: run each facet, gather evidence, build a prompt.

    One task per corpus entry whose extraction landed in ``only_buckets`` — by
    default the covered values (``ok``/``deferred``), since judging garbage Tier A
    already flags adds no signal. Each task carries the prompt to hand a subagent
    plus the context needed to parse its reply.

    Network: runs the real extractors and fetches each filing. Returns
        [{facet, accession, note, extracted, bucket, prompt}, ...]
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from run_eval import FACETS
    from edgar import find

    tasks = []
    for entry in corpus:
        f = entry["facet"]
        if facet and f != facet:
            continue
        fn = FACETS.get(f)
        if fn is None:
            continue
        filing = find(entry["accession"])
        bucket, value, _reason, _ctx = fn(filing)
        if bucket not in only_buckets:
            continue
        tasks.append({
            "facet": f,
            "accession": entry["accession"],
            "note": entry.get("note", ""),
            "extracted": value,
            "bucket": bucket,
            "prompt": build_offering_judge_prompt(
                f, entry["accession"], value, gather_evidence(f, filing)
            ),
        })
    return tasks


# =============================================================================
# Reporting
# =============================================================================

def summarize_verdicts(verdicts: List[OfferingVerdict]) -> str:
    """Format the audit: per-facet tallies and a catalog of confirmed disagreements."""
    from collections import defaultdict
    by_facet = defaultdict(lambda: defaultdict(int))
    for v in verdicts:
        by_facet[v.facet][v.verdict] += 1
        by_facet[v.facet]["n"] += 1

    lines = ["", "=== Offerings Tier C — LLM-judge semantic audit ===", ""]
    hdr = f"{'facet':18}{'n':>4}{'correct':>9}{'incorrect':>11}{'uncertain':>11}"
    lines += [hdr, "-" * len(hdr)]
    for facet, c in sorted(by_facet.items()):
        lines.append(f"{facet:18}{c['n']:>4}{c['correct']:>9}"
                     f"{c['incorrect']:>11}{c['uncertain']:>11}")

    disagreements = [v for v in verdicts if v.disagrees]
    if disagreements:
        lines += ["", "--- Confirmed disagreements (investigate → new oracle/anchor) ---"]
        for v in disagreements:
            lines.append(f"  [{v.facet}] {v.accession} ({v.confidence})")
            lines.append(f"      extracted: {v.extracted_value!r}")
            lines.append(f"      judge:     {v.judged_value!r} — {v.rationale}")
    else:
        lines += ["", "No confirmed disagreements."]
    return "\n".join(lines)
