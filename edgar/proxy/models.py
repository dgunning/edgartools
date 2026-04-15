"""
Data models for DEF 14A (Proxy Statement) filings.

Contains dataclasses for executive compensation, pay vs performance metrics,
and related governance data extracted from XBRL.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

__all__ = [
    'ExecutiveCompensation',
    'PayVsPerformance',
    'NamedExecutive',
    'SeasonFiling',
    'classify_proxy_tier',
    'PROXY_FORMS',
    'ANCHOR_FORMS',
    'CONTEST_INDICATOR_FORMS',
    'DISSIDENT_ONLY_FORMS',
    'SUPPLEMENTAL_FORMS',
    'EXEMPT_SOLICITATION_FORMS',
    'PRELIMINARY_FORMS',
]

# Forms that map to ProxyStatement data object
PROXY_FORMS = [
    # Management definitive
    'DEF 14A', 'DEF 14A/A', 'DEFA14A', 'DEFA14A/A', 'DEFM14A', 'DEFM14A/A', 'DEFR14A', 'DEFR14A/A',
    # Contested solicitation (either party)
    'DEFC14A', 'DEFC14A/A',
    # Non-management / dissident
    'DEFN14A', 'DEFN14A/A', 'DFAN14A', 'DFAN14A/A', 'DFRN14A', 'DFRN14A/A',
    # Preliminary
    'PRE 14A', 'PRE 14A/A', 'PREC14A', 'PREC14A/A', 'PREM14A', 'PREM14A/A',
    'PREN14A', 'PREN14A/A', 'PRER14A', 'PRER14A/A', 'PRRN14A', 'PRRN14A/A',
    # Exempt solicitations
    'PX14A6G', 'PX14A6N',
]

# Season anchor — management's definitive proxy (DEF 14A in normal years, DEFC14A in contest years)
ANCHOR_FORMS = {'DEF 14A', 'DEFC14A'}

# Contest indicator — presence of any of these signals a proxy contest
CONTEST_INDICATOR_FORMS = {
    'DEFC14A', 'DEFC14C', 'PREC14A', 'PREC14C',
    'DFAN14A', 'DEFN14A', 'PREN14A', 'DFRN14A', 'PRRN14A',
}

# N-suffix forms are always filed by the dissident (non-management)
DISSIDENT_ONLY_FORMS = {
    'DFAN14A', 'DEFN14A', 'PREN14A', 'DFRN14A', 'PRRN14A',
}

# Supplemental campaign materials — no structured proxy disclosures
SUPPLEMENTAL_FORMS = {'DEFA14A', 'DFAN14A', 'DFRN14A'}

# Preliminary proxy filings — draft versions subject to SEC revision
PRELIMINARY_FORMS = {'PRE 14A', 'PREC14A', 'PREM14A', 'PREN14A', 'PRER14A', 'PRRN14A'}

# Third-party exempt solicitations (ISS, Glass Lewis, activist orgs)
EXEMPT_SOLICITATION_FORMS = {'PX14A6G', 'PX14A6N'}


@dataclass(frozen=True)
class SeasonFiling:
    """A proxy filing with metadata for season/contest analysis.

    Carries best-effort party identification and tier classification
    so consumers can filter and sort without re-parsing headers.
    """
    filing: 'Filing'
    form: str
    filing_date: str
    accession_no: str
    file_number: Optional[str] = None
    party_type: str = 'management'      # management / dissident / third_party / unknown
    party_name: Optional[str] = None    # best-effort filer name from header
    filer_cik: Optional[str] = None
    tier: int = 1                        # 1=full, 2=contested, 3=preliminary, 4=supplemental, 5=exempt


def classify_proxy_tier(form: str) -> int:
    """Classify a proxy form type into a tier (1-5).

    Tier 1: Full proxy (DEF 14A, DEFR14A)
    Tier 2: Contested definitive (DEFC14A, DEFN14A)
    Tier 3: Preliminary (PRE 14A, PREC14A, etc.)
    Tier 4: Supplemental (DEFA14A, DFAN14A, DFRN14A)
    Tier 5: Exempt solicitation (PX14A6G, PX14A6N)
    """
    base = form.replace('/A', '').strip()
    if base in EXEMPT_SOLICITATION_FORMS:
        return 5
    if base in SUPPLEMENTAL_FORMS:
        return 4
    if base in PRELIMINARY_FORMS:
        return 3
    if base in {'DEFC14A', 'DEFN14A'}:
        return 2
    # DEF 14A, DEFM14A, DEFR14A and anything else
    return 1


@dataclass(frozen=True)
class ExecutiveCompensation:
    """Single year of executive compensation data from Pay vs Performance table."""
    fiscal_year_end: str
    peo_total_comp: Optional[Decimal] = None
    peo_actually_paid_comp: Optional[Decimal] = None
    neo_avg_total_comp: Optional[Decimal] = None
    neo_avg_actually_paid_comp: Optional[Decimal] = None


@dataclass(frozen=True)
class PayVsPerformance:
    """Single year of pay vs performance metrics."""
    fiscal_year_end: str
    peo_actually_paid_comp: Optional[Decimal] = None
    neo_avg_actually_paid_comp: Optional[Decimal] = None
    total_shareholder_return: Optional[Decimal] = None
    peer_group_tsr: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    company_selected_measure_value: Optional[Decimal] = None


@dataclass(frozen=True)
class NamedExecutive:
    """Individual named executive officer data (when dimensionally tagged)."""
    name: str
    member_id: Optional[str] = None
    role: Optional[str] = None  # PEO, NEO, etc.
    total_comp: Optional[Decimal] = None
    actually_paid_comp: Optional[Decimal] = None
    fiscal_year_end: Optional[str] = None
