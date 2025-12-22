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
    'PROXY_FORMS',
]

# Forms that map to ProxyStatement data object
PROXY_FORMS = ['DEF 14A', 'DEF 14A/A', 'DEFA14A', 'DEFM14A']


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
