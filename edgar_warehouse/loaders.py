"""
Sub-loaders for parsing SEC submissions JSON into staged row lists.

Each loader is a pure function: it takes the raw SEC payload dict plus
metadata (cik, sync_run_id, raw_object_id, load_mode) and returns a list
of staged row dicts. No database calls are made here.

Silver merge is handled by SilverDatabase.merge_* methods.

Spec reference: specification.md - Company Submissions Loader Contract
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

_DAILY_IDX_FULL_PATTERN = re.compile(
    r"^(?P<form>\S[\S ]*?)\s{2,}(?P<company>.+?)\s{2,}(?P<cik>\d{4,10})\s+(?P<date>\d{8}|\d{4}-\d{2}-\d{2})\s+(?P<filename>edgar/data/\S+)"
)
_ACCESSION_PATTERN = re.compile(r"edgar/data/\d+/([0-9-]+)-index\.")


def stage_company_loader(
    payload: dict[str, Any],
    cik: int,
    sync_run_id: str,
    raw_object_id: str,
    load_mode: str,
) -> list[dict[str, Any]]:
    """Parse the top-level company fields from a CIK##########.json payload.

    Returns a list with exactly one row.
    """
    return [
        {
            "cik": cik,
            "entity_name": payload.get("name"),
            "entity_type": payload.get("entityType"),
            "sic": payload.get("sic"),
            "sic_description": payload.get("sicDescription"),
            "state_of_incorporation": payload.get("stateOfIncorporation"),
            "state_of_incorporation_desc": payload.get("stateOfIncorporationDescription"),
            "fiscal_year_end": payload.get("fiscalYearEnd"),
            "ein": payload.get("ein"),
            "description": payload.get("description"),
            "category": payload.get("category"),
            "sync_run_id": sync_run_id,
            "raw_object_id": raw_object_id,
            "load_mode": load_mode,
        }
    ]


def stage_address_loader(
    payload: dict[str, Any],
    cik: int,
    sync_run_id: str,
    raw_object_id: str,
    load_mode: str,
) -> list[dict[str, Any]]:
    """Parse mailing and business address fields from a CIK##########.json payload.

    Returns one row per address type present (up to 2: mailing, business).
    """
    addresses = payload.get("addresses", {})
    rows: list[dict[str, Any]] = []
    for address_type, addr in addresses.items():
        if not isinstance(addr, dict):
            continue
        rows.append(
            {
                "cik": cik,
                "address_type": address_type,
                "street1": addr.get("street1"),
                "street2": addr.get("street2"),
                "city": addr.get("city"),
                "state_or_country": addr.get("stateOrCountry"),
                "zip_code": addr.get("zipCode"),
                "country": addr.get("stateOrCountryDescription"),
                "sync_run_id": sync_run_id,
                "raw_object_id": raw_object_id,
                "load_mode": load_mode,
            }
        )
    return rows


def stage_former_name_loader(
    payload: dict[str, Any],
    cik: int,
    sync_run_id: str,
    raw_object_id: str,
    load_mode: str,
) -> list[dict[str, Any]]:
    """Parse formerNames from a CIK##########.json payload.

    Returns one row per former name with a 1-based ordinal.
    """
    former_names = payload.get("formerNames", [])
    if not isinstance(former_names, list):
        return []
    rows: list[dict[str, Any]] = []
    for idx, entry in enumerate(former_names, start=1):
        if not isinstance(entry, dict):
            continue
        date_changed = _parse_date(entry.get("date"))
        rows.append(
            {
                "cik": cik,
                "former_name": entry.get("name"),
                "date_changed": date_changed,
                "ordinal": idx,
                "sync_run_id": sync_run_id,
                "raw_object_id": raw_object_id,
                "load_mode": load_mode,
            }
        )
    return rows


def stage_manifest_loader(
    payload: dict[str, Any],
    cik: int,
    sync_run_id: str,
    raw_object_id: str,
    load_mode: str,
) -> list[dict[str, Any]]:
    """Parse filings.files pagination file manifest from a CIK##########.json payload.

    Returns one row per pagination file listed under filings.files.
    """
    filings = payload.get("filings", {})
    if not isinstance(filings, dict):
        return []
    files = filings.get("files", [])
    if not isinstance(files, list):
        return []
    rows: list[dict[str, Any]] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        file_name = entry.get("name", "")
        if not file_name:
            continue
        rows.append(
            {
                "cik": cik,
                "file_name": file_name,
                "filing_count": entry.get("filingCount"),
                "filing_from": _parse_date(entry.get("filingFrom")),
                "filing_to": _parse_date(entry.get("filingTo")),
                "sync_run_id": sync_run_id,
                "raw_object_id": raw_object_id,
                "load_mode": load_mode,
            }
        )
    return rows


def stage_recent_filing_loader(
    payload: dict[str, Any],
    cik: int,
    sync_run_id: str,
    raw_object_id: str,
    load_mode: str,
    recent_limit: int | None = None,
) -> list[dict[str, Any]]:
    """Parse filings.recent arrays from a CIK##########.json payload.

    Returns one row per filing. If recent_limit is given, only the first
    recent_limit rows are returned (rows are already ordered newest-first
    as returned by the SEC API).
    """
    filings = payload.get("filings", {})
    if not isinstance(filings, dict):
        return []
    recent = filings.get("recent", {})
    if not isinstance(recent, dict):
        return []

    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    acceptance_datetimes = recent.get("acceptanceDateTime", [])
    acts = recent.get("act", [])
    forms = recent.get("form", [])
    file_numbers = recent.get("fileNumber", [])
    film_numbers = recent.get("filmNumber", [])
    items = recent.get("items", [])
    sizes = recent.get("size", [])
    is_xbrl_list = recent.get("isXBRL", [])
    is_inline_xbrl_list = recent.get("isInlineXBRL", [])
    primary_documents = recent.get("primaryDocument", [])
    primary_doc_descs = recent.get("primaryDocDescription", [])

    count = len(accession_numbers)
    if recent_limit is not None:
        count = min(count, recent_limit)

    rows: list[dict[str, Any]] = []
    for i in range(count):
        rows.append(
            {
                "accession_number": _safe_str(accession_numbers, i),
                "cik": cik,
                "form": _safe_str(forms, i),
                "filing_date": _parse_date(_safe_str(filing_dates, i)),
                "report_date": _parse_date(_safe_str(report_dates, i)),
                "acceptance_datetime": _safe_str(acceptance_datetimes, i),
                "act": _safe_str(acts, i),
                "file_number": _safe_str(file_numbers, i),
                "film_number": _safe_str(film_numbers, i),
                "items": _safe_str(items, i),
                "size": _safe_int(sizes, i),
                "is_xbrl": bool(_safe_int(is_xbrl_list, i)),
                "is_inline_xbrl": bool(_safe_int(is_inline_xbrl_list, i)),
                "primary_document": _safe_str(primary_documents, i),
                "primary_doc_desc": _safe_str(primary_doc_descs, i),
                "sync_run_id": sync_run_id,
                "raw_object_id": raw_object_id,
                "load_mode": load_mode,
            }
        )
    return rows


def stage_pagination_filing_loader(
    payload: dict[str, Any],
    cik: int,
    sync_run_id: str,
    raw_object_id: str,
    load_mode: str,
) -> list[dict[str, Any]]:
    """Parse filings from a CIK##########-submissions-###.json pagination file.

    Pagination files have the filing arrays at the top level under "filings"
    (not nested under "filings.recent" as in the main submissions file).

    Returns one row per filing.
    """
    filings = payload.get("filings", {})
    if not isinstance(filings, dict):
        return []

    accession_numbers = filings.get("accessionNumber", [])
    filing_dates = filings.get("filingDate", [])
    report_dates = filings.get("reportDate", [])
    acceptance_datetimes = filings.get("acceptanceDateTime", [])
    acts = filings.get("act", [])
    forms = filings.get("form", [])
    file_numbers = filings.get("fileNumber", [])
    film_numbers = filings.get("filmNumber", [])
    items = filings.get("items", [])
    sizes = filings.get("size", [])
    is_xbrl_list = filings.get("isXBRL", [])
    is_inline_xbrl_list = filings.get("isInlineXBRL", [])
    primary_documents = filings.get("primaryDocument", [])
    primary_doc_descs = filings.get("primaryDocDescription", [])

    count = len(accession_numbers)
    rows: list[dict[str, Any]] = []
    for i in range(count):
        rows.append(
            {
                "accession_number": _safe_str(accession_numbers, i),
                "cik": cik,
                "form": _safe_str(forms, i),
                "filing_date": _parse_date(_safe_str(filing_dates, i)),
                "report_date": _parse_date(_safe_str(report_dates, i)),
                "acceptance_datetime": _safe_str(acceptance_datetimes, i),
                "act": _safe_str(acts, i),
                "file_number": _safe_str(file_numbers, i),
                "film_number": _safe_str(film_numbers, i),
                "items": _safe_str(items, i),
                "size": _safe_int(sizes, i),
                "is_xbrl": bool(_safe_int(is_xbrl_list, i)),
                "is_inline_xbrl": bool(_safe_int(is_inline_xbrl_list, i)),
                "primary_document": _safe_str(primary_documents, i),
                "primary_doc_desc": _safe_str(primary_doc_descs, i),
                "sync_run_id": sync_run_id,
                "raw_object_id": raw_object_id,
                "load_mode": load_mode,
            }
        )
    return rows


def stage_daily_index_filing_loader(
    payload: bytes,
    business_date: date,
    sync_run_id: str,
    raw_object_id: str,
    source_url: str,
) -> list[dict[str, Any]]:
    """Parse a form.YYYYMMDD.idx file into staged row dicts.

    Returns one dict per data line (lines containing 'edgar/data/').
    row_ordinal is 1-based, counting only data lines (headers skipped).
    """
    source_year = business_date.year
    source_quarter = ((business_date.month - 1) // 3) + 1
    text = payload.decode("utf-8", errors="replace")
    rows: list[dict[str, Any]] = []
    ordinal = 0
    for line in text.splitlines():
        if "edgar/data/" not in line:
            continue
        m = _DAILY_IDX_FULL_PATTERN.match(line)
        if not m:
            continue
        ordinal += 1
        form_val = m.group("form").strip()
        company_val = m.group("company").strip()
        cik_val = int(m.group("cik"))
        date_str = m.group("date")
        try:
            if len(date_str) == 8:
                filing_date_val = date.fromisoformat(
                    date_str[:4] + "-" + date_str[4:6] + "-" + date_str[6:]
                )
            else:
                filing_date_val = date.fromisoformat(date_str)
        except ValueError:
            continue  # skip malformed line
        file_name_val = m.group("filename")
        acc_match = _ACCESSION_PATTERN.search(file_name_val)
        accession_number_val = acc_match.group(1) if acc_match else file_name_val
        filing_txt_url_val = "https://www.sec.gov/Archives/" + file_name_val
        record_hash_val = hashlib.sha256(
            f"{form_val}|{company_val}|{cik_val}|{filing_date_val}|{file_name_val}".encode()
        ).hexdigest()
        rows.append(
            {
                "sync_run_id": sync_run_id,
                "raw_object_id": raw_object_id,
                "source_name": "daily_form_index",
                "source_url": source_url,
                "business_date": business_date,
                "source_year": source_year,
                "source_quarter": source_quarter,
                "row_ordinal": ordinal,
                "form": form_val,
                "company_name": company_val,
                "cik": cik_val,
                "filing_date": filing_date_val,
                "file_name": file_name_val,
                "accession_number": accession_number_val,
                "filing_txt_url": filing_txt_url_val,
                "record_hash": record_hash_val,
            }
        )
    return rows


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _parse_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _safe_str(lst: list, idx: int) -> str | None:
    if idx < len(lst):
        v = lst[idx]
        return str(v) if v is not None and v != "" else None
    return None


def _safe_int(lst: list, idx: int) -> int | None:
    if idx < len(lst):
        v = lst[idx]
        try:
            return int(v) if v is not None else None
        except (ValueError, TypeError):
            return None
    return None
