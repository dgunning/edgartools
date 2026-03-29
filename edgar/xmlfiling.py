"""
Generic data object for SEC filings with XML primary documents and XSLT rendering.

Many SEC form types use a structured XML primary document (primary_doc.xml)
with no HTML. The SEC renders these via server-side XSLT at a predictable URL.
This module provides a generic wrapper that:
  - Parses the XML into a nested dict for programmatic access
  - Fetches the SEC's XSLT-rendered HTML for display

Supported forms: X-17A-5, TA-1, TA-2, TA-W, CFPORTAL,
SBSE, SBSE-A, SBSE-W, ATS-N-C, and their /A amendments.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import Any, Optional, TYPE_CHECKING

from lxml import etree
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing

__all__ = ['XmlFiling']

# ---------------------------------------------------------------------------
# XSLT prefix map — form type -> SEC server-side XSLT path component
# ---------------------------------------------------------------------------

_XSLT_PREFIXES: dict[str, str] = {
    'X-17A-5':  'xslX-17A-5_X01',
    'TA-1':     'xslFTA1X01',
    'TA-2':     'xslFTA2X01',
    'TA-W':     'xslFTAWX01',
    'MA':       'xslFormMA_X01',
    'MA-W':     'xslFormMA-W_X01',
    'CFPORTAL': 'xslCFPORTAL_X01',
    'SBSE':     'xslSBSE_X01',
    'SBSE-A':   'xslSBSE-A_X01',
    'SBSE-W':   'xslSBSE-W_X01',
    'ATS-N-C':  'xslATS-N-C_X01',
}

# All form types (including /A amendments) handled by this class
XML_FILING_FORMS: list[str] = []
for _form in _XSLT_PREFIXES:
    XML_FILING_FORMS.append(_form)
    XML_FILING_FORMS.append(f'{_form}/A')

# Form descriptions for display
_FORM_DESCRIPTIONS: dict[str, str] = {
    'X-17A-5':  'Broker-Dealer Financial Report',
    'TA-1':     'Transfer Agent Registration',
    'TA-2':     'Transfer Agent Annual Report',
    'TA-W':     'Transfer Agent Withdrawal',
    'MA':       'Municipal Advisor Firm Registration',
    'MA-W':     'Municipal Advisor Withdrawal',
    'CFPORTAL': 'Crowdfunding Portal Registration',
    'SBSE':     'Security-Based Swap Entity Registration',
    'SBSE-A':   'Security-Based Swap Entity Registration (Annual)',
    'SBSE-W':   'Security-Based Swap Entity Withdrawal',
    'ATS-N-C':  'ATS Cessation of Operations',
}


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _strip_namespaces(root):
    """Remove namespace prefixes from all element tags and attributes."""
    for el in root.iter():
        tag = el.tag
        if isinstance(tag, str) and '}' in tag:
            el.tag = tag.split('}', 1)[1]
        attrib = el.attrib
        keys_to_fix = [k for k in attrib if '}' in k]
        for k in keys_to_fix:
            new_key = k.split('}', 1)[1]
            attrib[new_key] = attrib.pop(k)


def _element_to_dict(element) -> Any:
    """Recursively convert an lxml element to a nested dict.

    Leaf elements become strings. Elements with children become dicts.
    Repeated sibling tags become lists.
    """
    children = list(element)
    if not children:
        return element.text.strip() if element.text else None

    result: dict[str, Any] = {}
    for child in children:
        tag = child.tag
        value = _element_to_dict(child)
        if tag in result:
            existing = result[tag]
            if not isinstance(existing, list):
                result[tag] = [existing]
            result[tag].append(value)
        else:
            result[tag] = value
    return result


def _deep_get(data: dict, key: str) -> Any:
    """Search recursively for a key in a nested dict. Returns first match."""
    if key in data:
        return data[key]
    for v in data.values():
        if isinstance(v, dict):
            found = _deep_get(v, key)
            if found is not None:
                return found
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    found = _deep_get(item, key)
                    if found is not None:
                        return found
    return None


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class XmlFiling:
    """
    Generic data object for SEC XML filings with XSLT rendering.

    Provides dict-based access to the structured XML data and
    SEC-rendered HTML for display.

    Construction via from_filing() or filing.obj():
        filing = find("X-17A-5 accession number")
        xf = filing.obj()  # Returns XmlFiling
        xf = XmlFiling.from_filing(filing)

    Key properties:
        xf.form_data        -> dict (the formData XML tree)
        xf.header_data      -> dict (the headerData XML tree)
        xf['fieldName']     -> deep key lookup into form_data
        xf.description      -> str (human-readable form description)

    Methods:
        xf.to_html()        -> str (SEC XSLT-rendered HTML)
    """

    def __init__(self, filing: 'Filing', form_data: dict, header_data: dict):
        self._filing = filing
        self._form_data = form_data
        self._header_data = header_data

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing: 'Filing') -> Optional['XmlFiling']:
        """Parse the filing's XML into a generic data object."""
        xml_str = filing.xml()
        if not xml_str:
            return None

        try:
            root = etree.fromstring(xml_str.encode() if isinstance(xml_str, str) else xml_str)
            _strip_namespaces(root)

            form_data_el = root.find('formData')
            header_data_el = root.find('headerData')

            form_data = _element_to_dict(form_data_el) if form_data_el is not None else {}
            header_data = _element_to_dict(header_data_el) if header_data_el is not None else {}

            return cls(filing=filing, form_data=form_data, header_data=header_data)
        except Exception:
            log.debug("Failed to parse XML for %s %s", filing.form, filing.accession_no)
            return None

    # ------------------------------------------------------------------
    # Core properties
    # ------------------------------------------------------------------

    @property
    def filing(self) -> 'Filing':
        return self._filing

    @property
    def form(self) -> str:
        return self._filing.form

    @property
    def base_form(self) -> str:
        """Form without /A suffix."""
        return self._filing.form.replace('/A', '')

    @property
    def company(self) -> str:
        return self._filing.company

    @property
    def filing_date(self):
        return self._filing.filing_date

    @property
    def accession_number(self) -> str:
        return self._filing.accession_no

    @property
    def is_amendment(self) -> bool:
        return '/A' in self._filing.form

    @property
    def form_data(self) -> dict:
        """The formData XML tree as a nested dict."""
        return self._form_data

    @property
    def header_data(self) -> dict:
        """The headerData XML tree as a nested dict."""
        return self._header_data

    @property
    def description(self) -> str:
        """Human-readable description of this form type."""
        return _FORM_DESCRIPTIONS.get(self.base_form, self.form)

    def __getitem__(self, key: str) -> Any:
        """Deep key lookup into form_data."""
        return _deep_get(self._form_data, key)

    def get(self, key: str, default: Any = None) -> Any:
        """Deep key lookup with default."""
        result = _deep_get(self._form_data, key)
        return result if result is not None else default

    # ------------------------------------------------------------------
    # HTML rendering via SEC XSLT
    # ------------------------------------------------------------------

    @cached_property
    def _xslt_prefix(self) -> Optional[str]:
        """XSLT prefix for this form type."""
        return _XSLT_PREFIXES.get(self.base_form)

    def to_html(self) -> Optional[str]:
        """Fetch the SEC's XSLT-rendered HTML for this filing.

        Makes a network request to the SEC's XSLT rendering endpoint.
        Returns None if the form type has no known XSLT prefix or
        the request fails.
        """
        prefix = self._xslt_prefix
        if not prefix:
            return None

        try:
            import httpx
            acc = self._filing.accession_no.replace('-', '')
            cik = self._filing.cik
            url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{prefix}/primary_doc.xml'
            resp = httpx.get(
                url,
                headers={'User-Agent': 'EdgarTools support@edgartools.io'},
                follow_redirects=True,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.text
        except Exception:
            log.debug("Failed to fetch XSLT HTML for %s %s", self.form, self._filing.accession_no)
        return None

    # ------------------------------------------------------------------
    # AI context
    # ------------------------------------------------------------------

    def to_context(self, detail: str = 'standard') -> str:
        """AI-optimized context string for language models."""
        lines = [
            f"XML FILING: {self.company} ({self.form})",
            f"Type: {self.description}",
            "",
            f"Filed: {self.filing_date}",
        ]

        if self.is_amendment:
            lines.append("Status: AMENDMENT")

        if detail == 'minimal':
            return "\n".join(lines)

        # Show top-level form data keys
        if self._form_data:
            lines.append("")
            lines.append("FORM DATA FIELDS:")
            for key in list(self._form_data.keys())[:20]:
                val = self._form_data[key]
                if isinstance(val, str):
                    lines.append(f"  {key}: {val[:80]}")
                elif isinstance(val, dict):
                    lines.append(f"  {key}: {{...}}")
                elif isinstance(val, list):
                    lines.append(f"  {key}: [{len(val)} items]")

        if detail == 'full':
            lines.append("")
            lines.append("AVAILABLE ACTIONS:")
            lines.append("  .form_data -> dict (full XML data tree)")
            lines.append("  .header_data -> dict (submission header)")
            lines.append("  ['key'] -> deep lookup into form_data")
            lines.append("  .to_html() -> SEC XSLT-rendered HTML")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Rich display
    # ------------------------------------------------------------------

    def __rich__(self):
        title = f"{self.company}  {self.filing_date}"
        subtitle = f"{self.form}  {self.description}"

        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        t.add_column("field", style="bold deep_sky_blue1", min_width=22)
        t.add_column("value")

        t.add_row("Form", self.form)
        t.add_row("Type", self.description)
        if self.is_amendment:
            t.add_row("Amendment", "[yellow]Yes[/yellow]")

        renderables = [t]

        # Show top-level form data as a summary table
        if self._form_data:
            renderables.append(Text(""))
            dt = Table(box=box.SIMPLE, show_header=True, padding=(0, 1),
                       title="Form Data")
            dt.add_column("Field", style="bold")
            dt.add_column("Value", max_width=60)

            shown = 0
            for key, val in self._form_data.items():
                if shown >= 12:
                    dt.add_row("...", f"({len(self._form_data) - 12} more fields)")
                    break
                if isinstance(val, str):
                    dt.add_row(key, val[:60])
                elif isinstance(val, dict):
                    # Show first string value in the dict as a preview
                    preview = next(
                        (f"{k}: {v}" for k, v in val.items() if isinstance(v, str)),
                        "{...}"
                    )
                    dt.add_row(key, preview[:60])
                elif isinstance(val, list):
                    dt.add_row(key, f"[{len(val)} items]")
                else:
                    dt.add_row(key, str(val)[:60] if val else "")
                shown += 1

            renderables.append(dt)

        return Panel(
            Group(*renderables),
            title=f"[bold]{title}[/bold]",
            subtitle=subtitle,
            box=box.ROUNDED,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return (
            f"XmlFiling("
            f"form={self.form!r}, "
            f"company={self.company!r}, "
            f"date={self.filing_date!r})"
        )
