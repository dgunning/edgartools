#!/usr/bin/env python3
"""
Item 1A Risk Factors -> LangExtract (Gemini) -> structured JSON.

Features:
- "Anti-Boilerplate" prompting to ignore generic risks.
- Robust text cleaning and HTML artifact removal.
- Soft schema validation (saves data even if slightly imperfect).
- Fixes 'Attachment' object attribute errors from edgartools.

Usage:
  export GEMINI_API_KEY="your_key"
  python risk_extract.py --ticker SNAP --model gemini-1.5-pro
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import re
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------
# Imports
# ----------------------------
try:
    from edgar import Company, set_identity
except ImportError:
    sys.exit("Missing dependency: pip install -U edgartools")

try:
    import langextract as lx
except ImportError:
    sys.exit("Missing dependency: pip install -U langextract")

try:
    from jsonschema import validate, ValidationError
except ImportError:
    sys.exit("Missing dependency: pip install -U jsonschema")

# Optional: Rich for better console output
try:
    from rich.console import Console
    console = Console()
    print_info = console.print
except ImportError:
    def print_info(*args, **kwargs):
        # Fallback if rich is not installed
        print(*args, **kwargs)

# ----------------------------
# JSON Schema (Enhanced)
# ----------------------------
RISK_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["company", "filing", "risks"],
    "properties": {
        "company": {
            "type": "object",
            "required": ["ticker"],
            "properties": {
                "ticker": {"type": "string"},
                "cik": {"type": ["string", "null", "integer"]},
                "name": {"type": ["string", "null"]},
            },
        },
        "filing": {
            "type": "object",
            "required": ["form", "filing_date"],
            "properties": {
                "form": {"type": "string"},
                "filing_date": {"type": "string"},
                "accession_no": {"type": ["string", "null"]},
                "sec_url": {"type": ["string", "null"]},
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "risk_title",
                    "risk_summary",
                    "category",
                    "specificity_rating"
                ],
                "properties": {
                    "risk_id": {"type": ["string", "null"]},
                    "risk_title": {"type": "string"},
                    "risk_summary": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["Operational", "Financial", "Legal/Regulatory", "Tech/Cyber", "Market", "Strategic", "Other"]
                    },
                    "subcategory": {"type": ["string", "null"]},
                    "specificity_rating": {
                        "type": "string",
                        "enum": ["High", "Medium", "Low"],
                        "description": "High=Company specific, Low=Generic boilerplate"
                    },
                    "impact": {
                        "type": "string",
                        "enum": ["Critical", "Significant", "Moderate", "Minor", "Unknown"]
                    },
                    "likelihood": {
                         "type": "string",
                         "enum": ["High", "Medium", "Low", "Unknown"]
                    },
                    "time_horizon": {
                        "type": "string",
                        "enum": ["Near (0-12m)", "Mid (1-3y)", "Long (3y+)", "Unknown"]
                    },
                    "drivers": {"type": "array", "items": {"type": "string"}},
                    "mitigations": {"type": "array", "items": {"type": "string"}},
                    "source_grounding": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start_char": {"type": "integer"},
                                "end_char": {"type": "integer"},
                                "snippet": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}

# ----------------------------
# Prompt & Examples
# ----------------------------
PROMPT = textwrap.dedent(
    """\
    Role: Senior Financial Analyst.
    Task: Extract **Idiosyncratic (Company-Specific)** Risk Factors from the 10-K text.

    **CRITICAL FILTERING RULES (Do NOT extract these):**
    1. **NO Generic Legal Risks:** Ignore standard warnings about "changes in tax laws," "GDPR compliance," or "environmental regulations" UNLESS the company cites a *specific* ongoing investigation, lawsuit, or new bill targeting them directly.
    2. **NO Macro-Economic Boilerplate:** Ignore "inflation," "interest rates," or "recession" risks unless they mention specific impact on the company's unique debt structure or supply chain.
    3. **NO Stock Volatility:** Ignore "stock price may fluctuate" or "no dividends" warnings.

    **INCLUSION CRITERIA (Only extract if):**
    - The risk names specific products, competitors, technologies, or key personnel.
    - The risk discusses specific pending litigation or regulatory enforcement actions.
    - The risk mentions specific operational failures (e.g., "failure of our new Ohio facility").

    Output Attributes:
    - risk_title: specific and descriptive (e.g., NOT "Regulatory Risk", BUT "FDA Delay for Drug X").
    - risk_summary: 1 sentence focus on the *consequence*.
    - specificity_rating: "High" (unique to this company), "Medium" (industry specific), "Low" (generic).
    - category: Select best fit from enum.
    """
)

EXAMPLES = [
    # Negative Example (Boilerplate)
    lx.data.ExampleData(
        text=(
            "RISKS RELATED TO OUR STOCK\n"
            "Our stock price may be volatile. The trading price of our common stock has been and is likely to continue to be volatile. "
            "In addition, we do not anticipate paying any cash dividends in the foreseeable future."
        ),
        extractions=[]
    ),
    # Positive Example (Specific)
    lx.data.ExampleData(
        text=(
            "LEGAL PROCEEDINGS\n"
            "We are currently subject to an antitrust investigation by the EU Commission regarding our bundling of "
            "App Store services. An adverse ruling could result in fines up to 10% of global turnover."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="risk_factor",
                extraction_text="We are currently subject to an antitrust investigation by the EU Commission regarding our bundling of App Store services.",
                attributes={
                    "risk_title": "EU Antitrust Investigation",
                    "risk_summary": "Potential fines up to 10% of turnover due to App Store bundling investigation.",
                    "category": "Legal/Regulatory",
                    "specificity_rating": "High",
                    "impact": "Critical",
                    "drivers": ["EU Commission probe", "App Store bundling practices"],
                    "likelihood": "Medium",
                    "time_horizon": "Mid (1-3y)"
                }
            )
        ]
    )
]

# ----------------------------
# Helpers
# ----------------------------
def clean_text(text: str) -> str:
    """Normalize whitespace and remove common artifacts."""
    if not text:
        return ""
    # Replace multiple newlines/tabs with single space/newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove extremely short lines that look like page numbers
    lines = [line for line in text.split('\n') if len(line.strip()) > 2]
    return '\n'.join(lines)

def _as_text(section_obj: Any) -> str:
    if section_obj is None:
        return ""
    if isinstance(section_obj, str):
        return section_obj
    if hasattr(section_obj, "text"):
        try:
            return section_obj.text or ""
        except Exception:
            pass
    return str(section_obj)

def fetch_item_1a_meta(ticker: str) -> Dict[str, Any]:
    print_info(f"[blue]Fetching 10-K for {ticker}...[/blue]")
    company = Company(ticker)
    
    filings = company.get_filings(form="10-K")
    if not filings:
         print_info(f"[red]No 10-K found for {ticker}[/red]")
         return {}
         
    latest = filings.latest()
    tenk = latest.obj()

    risk_text = ""
    
    # 1. Try modern edgartools chunk accessor
    if hasattr(tenk, "items") and "1A" in tenk.items:
        risk_text = tenk.items["1A"]
    
    # 2. Try section text extraction
    if not risk_text and hasattr(tenk, "get_section_text"):
        try:
            risk_text = _as_text(tenk.get_section_text("Risk Factors"))
        except Exception:
            pass

    # 3. Fallback to dictionary access
    if not risk_text:
        for key in ["Item 1A", "Risk Factors", "ITEM 1A", "ITEM 1A. RISK FACTORS"]:
            try:
                val = tenk[key]
                risk_text = _as_text(val)
                if risk_text: break
            except (KeyError, IndexError, TypeError):
                continue

    risk_text = clean_text(risk_text)
    
    # Check for "Incorporated by Reference" (Proxy Statement check)
    if len(risk_text) < 1000 and "proxy statement" in risk_text.lower():
        print_info(f"[yellow]WARNING: Risk factors appear to be incorporated by reference (Length: {len(risk_text)}).[/yellow]")

    # --- FIX FOR ATTRIBUTE ERROR ---
    sec_url = None
    doc_obj = getattr(latest, "document", None)
    if doc_obj:
        # Check attribute first (correct for newer edgartools)
        sec_url = getattr(doc_obj, "url", None)
        # Fallback to dictionary if it happens to be one
        if not sec_url and isinstance(doc_obj, dict):
             sec_url = doc_obj.get("url")

    return {
        "ticker": ticker,
        "company_name": getattr(company, "name", None),
        "cik": getattr(company, "cik", None),
        "filing_date": str(getattr(latest, "filing_date", "")),
        "accession_no": getattr(latest, "accession_no", None),
        "sec_url": sec_url,
        "risk_text": risk_text or "",
    }

def get_api_key() -> str:
    key = (
        os.getenv("LANGEXTRACT_API_KEY") 
        or os.getenv("GEMINI_API_KEY") 
        or os.getenv("GOOGLE_API_KEY")
    )
    if not key:
        sys.exit("Error: No API key found. Set GEMINI_API_KEY or LANGEXTRACT_API_KEY.")
    return key

# ----------------------------
# Output Converters
# ----------------------------
def _interval_to_int_pair(interval: Any) -> Optional[Tuple[int, int]]:
    if interval is None:
        return None
    if isinstance(interval, (tuple, list)) and len(interval) == 2:
        try:
            return int(interval[0]), int(interval[1])
        except Exception:
            return None
    if hasattr(interval, "start") and hasattr(interval, "end"):
        try:
            return int(interval.start), int(interval.end)
        except Exception:
            return None
    return None

def to_risk_json(doc: "lx.data.AnnotatedDocument", meta: Dict[str, Any]) -> Dict[str, Any]:
    text = meta.get("risk_text", "") or ""
    risks: List[Dict[str, Any]] = []

    for ex in getattr(doc, "extractions", []) or []:
        if getattr(ex, "extraction_class", None) != "risk_factor":
            continue

        attrs = dict(getattr(ex, "attributes", None) or {})
        extraction_text = getattr(ex, "extraction_text", "") or ""

        risk_obj: Dict[str, Any] = {
            "risk_id": attrs.get("risk_id"),
            "risk_title": attrs.get("risk_title") or extraction_text[:100],
            "risk_summary": attrs.get("risk_summary") or "",
            "category": attrs.get("category") or "Other",
            "subcategory": attrs.get("subcategory"),
            "specificity_rating": attrs.get("specificity_rating") or "Low",
            "likelihood": attrs.get("likelihood") or "Unknown",
            "impact": attrs.get("impact") or "Unknown",
            "time_horizon": attrs.get("time_horizon") or "Unknown",
            "drivers": attrs.get("drivers") or [],
            "mitigations": attrs.get("mitigations") or [],
            "source_grounding": [],
        }

        # Source grounding (character indices)
        interval = _interval_to_int_pair(getattr(ex, "char_interval", None))
        if interval:
            start, end = interval
            start = max(0, min(start, len(text)))
            end = max(0, min(end, len(text)))
            if end > start:
                risk_obj["source_grounding"].append(
                    {"start_char": start, "end_char": end, "snippet": text[start:end]}
                )

        risks.append(risk_obj)

    out = {
        "company": {
            "ticker": meta.get("ticker"),
            "cik": meta.get("cik"),
            "name": meta.get("company_name"),
        },
        "filing": {
            "form": "10-K",
            "filing_date": meta.get("filing_date", ""),
            "accession_no": meta.get("accession_no"),
            "sec_url": meta.get("sec_url"),
        },
        "risks": risks,
    }
    return out

# ----------------------------
# Main Logic
# ----------------------------
def main() -> int:
    p = argparse.ArgumentParser(description="Extract Risk Factors from 10-K")
    p.add_argument("--ticker", required=True)
    p.add_argument("--out", default=None)
    # Defaulting to a safe, stable model
    p.add_argument("--model", default="models/gemini-3-flash-preview", help="gemini-1.5-pro, gemini-2.0-flash-exp")
    p.add_argument("--workers", type=int, default=4, help="Concurrent requests")
    p.add_argument("--identity", default="Analyst analysis@example.com", help="SEC Identity")
    args = p.parse_args()

    set_identity(args.identity)

    # 1. Fetch Data
    meta = fetch_item_1a_meta(args.ticker)
    if not meta or not meta.get("risk_text"):
        print_info("[red]Failed to extract Item 1A text.[/red]")
        return 1

    text_len = len(meta["risk_text"])
    print_info(f"Extracted {text_len} characters of Risk Factors text.")
    
    # Cost/Safety Check
    if text_len < 500:
        print_info("[red]Text too short. Aborting extraction.[/red]")
        return 1

    print_info(f"Starting extraction with [bold]{args.model}[/bold]...")

    # 2. Run Extraction
    try:
        doc = lx.extract(
            text_or_documents=meta["risk_text"],
            prompt_description=PROMPT,
            examples=EXAMPLES,
            model_id=args.model,
            api_key=get_api_key(),
            extraction_passes=1,
            max_workers=args.workers,
            max_char_buffer=2000,
            batch_length=max(10, args.workers),
        )
        if isinstance(doc, list):
            doc = doc[0]

    except Exception as e:
        print_info(f"[red]Extraction failed: {e}[/red]")
        return 2

    # 3. Process & Validate
    out = to_risk_json(doc, meta)

    try:
        validate(instance=out, schema=RISK_JSON_SCHEMA)
        print_info("[green]Schema validation passed.[/green]")
    except ValidationError as e:
        print_info(f"[yellow]Schema validation failed: {e.message}. Saving anyway.[/yellow]")
        out["_validation_warning"] = str(e.message)

    # 4. Save
    out_path = args.out or f"{args.ticker.lower()}_risks.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Summary
    count_high = sum(1 for r in out["risks"] if r.get("specificity_rating") == "High")
    print_info(f"[bold green]Success![/bold green] Wrote {len(out['risks'])} risks to {out_path}")
    print_info(f"High Specificity Risks: {count_high}")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())