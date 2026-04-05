"""Auditor information extracted from XBRL DEI facts in annual filings."""
from dataclasses import dataclass
from typing import Optional

from rich.panel import Panel
from rich.text import Text

from edgar.richtools import repr_rich

__all__ = ['AuditorInfo', 'extract_auditor_info']


@dataclass
class AuditorInfo:
    """Auditor information from DEI (Document and Entity Information) XBRL facts."""
    name: str
    location: str
    firm_id: int
    icfr_attestation: bool

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):
        lines = Text()
        lines.append(self.name, style="bold")
        lines.append(f"\n{self.location}")
        lines.append(f"\nPCAOB Firm ID: {self.firm_id}")
        lines.append(f"\nICFR Attestation: {'Yes' if self.icfr_attestation else 'No'}")
        return Panel(lines, title="Auditor", expand=False)


def _get_first_fact_value(xbrl, element_name: str) -> Optional[str]:
    """Get the value of the first fact found for an element."""
    facts = xbrl._find_facts_for_element(element_name)
    if not facts:
        return None
    # facts is {context_id: {'fact': Fact, 'dimension_info': ..., 'dimension_key': ...}}
    wrapped = next(iter(facts.values()))
    fact = wrapped.get('fact') if isinstance(wrapped, dict) else None
    if fact is None:
        return None
    return fact.value


def extract_auditor_info(xbrl) -> Optional['AuditorInfo']:
    """
    Extract auditor information from XBRL DEI facts.

    Args:
        xbrl: An XBRL instance with parsed filing data

    Returns:
        AuditorInfo if auditor name is found, None otherwise
    """
    name = _get_first_fact_value(xbrl, 'dei_AuditorName')
    if not name:
        return None

    location = _get_first_fact_value(xbrl, 'dei_AuditorLocation') or ''
    firm_id_str = _get_first_fact_value(xbrl, 'dei_AuditorFirmId')
    icfr_str = _get_first_fact_value(xbrl, 'dei_IcfrAuditorAttestationFlag')

    try:
        firm_id = int(firm_id_str) if firm_id_str else 0
    except (ValueError, TypeError):
        firm_id = 0

    icfr_attestation = icfr_str.lower() == 'true' if icfr_str else False

    return AuditorInfo(
        name=name,
        location=location,
        firm_id=firm_id,
        icfr_attestation=icfr_attestation,
    )
