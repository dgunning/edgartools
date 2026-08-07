"""Prospectus424B — parser/data object for 424B* prospectus filings."""

from __future__ import annotations

import logging
from functools import cached_property
from typing import List, Optional, TYPE_CHECKING

from edgar.offerings.prospectus._render import ProspectusRenderMixin
from edgar.offerings.prospectus._sections import ProspectusSectionsMixin
from edgar.offerings.prospectus.deal import Deal, _extract_amendment_number
from edgar.offerings.prospectus.lifecycle import ShelfLifecycle
from edgar.offerings.prospectus.models import (
    CoverPageData,
    OfferingType,
    UnderwriterEntry,
    UnderwritingInfo,
    _build_filing_fees_data,
)

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edgar._filings import Filing
    from edgar.offerings.prospectus.models import (
        CapitalizationData,
        DilutionData,
        FilingFeesData,
        OfferingTerms,
        PricingData,
        SellingStockholdersData,
        StructuredNoteTerms,
    )


class Prospectus424B(ProspectusSectionsMixin, ProspectusRenderMixin):
    """
    Parser for 424B* prospectus filings.

    Handles all 424B variants:
      - 424B1: Exchange offers, initial public offerings
      - 424B2: Structured notes, debt (large banks)
      - 424B3: Resale prospectuses (PIPE resales, rights offerings)
      - 424B4: Final priced prospectuses (IPOs, shelf takedowns)
      - 424B5: Shelf takedowns (ATM, firm commitment, PIPE, debt)
      - 424B7: WKSI selling stockholder updates
      - 424B8: Prospectus supplements

    Construction via from_filing() or filing.obj():
        filing = find("0001493152-25-029712")
        prospectus = filing.obj()  # Returns Prospectus424B
        prospectus = Prospectus424B.from_filing(filing)

    Key properties:
        prospectus.cover_page       -> CoverPageData (always available)
        prospectus.offering_type    -> OfferingType enum
        prospectus.ticker           -> str | None
        prospectus.offering_price   -> str | None
        prospectus.offering_amount  -> str | None
    """

    def __init__(self, filing: 'Filing', cover_page: CoverPageData,
                 offering_type: OfferingType, confidence: str,
                 document=None, filing_fees: Optional['FilingFeesData'] = None,
                 signals: Optional[List[str]] = None, sub_type: Optional[str] = None):
        self._filing = filing
        self._cover_page = cover_page
        self._offering_type = offering_type
        self._confidence = confidence
        # Classifier provenance — lets consumers tier values by how the type was
        # determined (e.g. exclude low-confidence firm_commitment rows carrying
        # the 'xbrl_security_type:equity' signal, which can be unlabelled resales).
        self._signals = signals or []
        self._sub_type = sub_type
        self._document = document
        # Optionally seeded by from_filing when the fee exhibit was already
        # fetched during classification — avoids a second download.
        self._eager_filing_fees = filing_fees

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing: 'Filing') -> 'Prospectus424B':
        """
        Primary entry point. Eagerly extracts cover page and offering type.

        Args:
            filing: An EdgarTools Filing object with a 424B* form type.

        Returns:
            Prospectus424B instance.
        """
        from edgar.offerings.prospectus._424b_cover import extract_cover_page_fields
        from edgar.offerings.prospectus._424b_classifier import classify_offering_type

        # Parse once, reuse everywhere
        try:
            document = filing.parse()
        except Exception:
            document = None

        cover_fields = extract_cover_page_fields(filing, document=document)
        cover_page = CoverPageData(**cover_fields)

        # First pass: text only (filing_fees=None suppresses the fee-exhibit
        # fetch). Only if the text is inconclusive do we fetch the exhibit once
        # and reuse it for both the classifier's structural fallback and the
        # filing_fees cache below — avoiding a redundant download.
        classification = classify_offering_type(filing, document=document, filing_fees=None)
        eager_filing_fees = None
        if classification.get('type') == 'unknown':
            from edgar.offerings.prospectus._424b_xbrl import extract_filing_fees_xbrl
            try:
                fees_dict = extract_filing_fees_xbrl(filing)
            except Exception:
                fees_dict = {'has_exhibit': False}
            classification = classify_offering_type(
                filing, document=document, filing_fees=fees_dict)
            eager_filing_fees = _build_filing_fees_data(fees_dict)

        offering_type = OfferingType(classification.get('type', 'unknown'))
        confidence = classification.get('confidence', 'low')

        return cls(
            filing=filing,
            cover_page=cover_page,
            offering_type=offering_type,
            confidence=confidence,
            document=document,
            filing_fees=eager_filing_fees,
            signals=classification.get('signals') or [],
            sub_type=classification.get('sub_type'),
        )

    # ------------------------------------------------------------------
    # Core properties (from filing metadata / eager extraction)
    # ------------------------------------------------------------------

    @property
    def filing(self) -> 'Filing':
        return self._filing

    @property
    def cover_page(self) -> CoverPageData:
        return self._cover_page

    @property
    def offering_type(self) -> OfferingType:
        return self._offering_type

    @property
    def offering_type_confidence(self) -> str:
        """Classifier confidence in offering_type: 'high' | 'medium' | 'low'."""
        return self._confidence

    @property
    def offering_type_signals(self) -> List[str]:
        """Signals behind the offering_type classification.

        Includes structural-fallback markers such as 'xbrl_security_type:equity'
        / ':debt' / ':rights'. Use with offering_type_confidence to tier values
        (e.g. exclude low-confidence firm_commitment rows sourced from the equity
        prior before summing gross_proceeds — they can be unlabelled resales)."""
        return list(self._signals)

    @property
    def offering_type_sub_type(self) -> Optional[str]:
        """Classifier sub-type (e.g. 'equity_resale' for a PIPE resale), if any."""
        return self._sub_type

    @property
    def form(self) -> str:
        return self._filing.form

    @property
    def variant(self) -> str:
        return self._filing.form.replace('/A', '')

    @property
    def company(self) -> str:
        return self._filing.company

    @property
    def filing_date(self) -> str:
        return self._filing.filing_date

    @property
    def accession_number(self) -> str:
        return self._filing.accession_no

    @property
    def is_amendment(self) -> bool:
        return '/A' in self._filing.form

    @property
    def amendment_number(self) -> Optional[int]:
        return _extract_amendment_number(self._filing.form)

    @property
    def registration_number(self) -> Optional[str]:
        return self._cover_page.registration_number

    @property
    def is_preliminary(self) -> bool:
        return self._cover_page.is_preliminary

    @property
    def is_atm(self) -> bool:
        return self._cover_page.is_atm

    @property
    def is_supplement(self) -> bool:
        return self._cover_page.is_supplement

    @property
    def ticker(self) -> Optional[str]:
        return self._cover_page.exchange_ticker

    @property
    def offering_amount(self) -> Optional[str]:
        return self._cover_page.offering_amount

    @property
    def offering_price(self) -> Optional[str]:
        return self._cover_page.offering_price

    # ------------------------------------------------------------------
    # Section-level text access — see ProspectusSectionsMixin (.sections / .section())
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Lazy table-extracted data (Phase 2+)
    # ------------------------------------------------------------------

    @cached_property
    def _classified_tables(self) -> dict:
        """Dict mapping table type -> list of matching TableNode objects."""
        from edgar.offerings.prospectus._424b_tables import classify_tables_in_document
        doc = self._document
        if not doc:
            return {}
        return classify_tables_in_document(doc)

    @cached_property
    def pricing(self) -> Optional['PricingData']:
        """Pricing table data (offering price, fee, proceeds).
        Returns None for ATM offerings and resale filings."""
        from edgar.offerings.prospectus._424b_tables import extract_pricing_data
        tables = self._classified_tables.get('pricing_table', [])
        if not tables:
            return None
        return extract_pricing_data(tables[0])

    @cached_property
    def offering_terms(self) -> Optional['OfferingTerms']:
        """Key-value offering terms from 'The Offering' section."""
        from edgar.offerings.prospectus._424b_tables import extract_offering_terms
        tables = self._classified_tables.get('offering_summary', [])
        if not tables:
            return None
        return extract_offering_terms(tables[0])

    @cached_property
    def selling_stockholders(self) -> Optional['SellingStockholdersData']:
        """Selling stockholders table data.
        Merges all selling stockholder tables found in the filing.
        Returns None if no selling stockholders table is found."""
        from edgar.offerings.prospectus._424b_tables import extract_selling_stockholders_data
        tables = self._classified_tables.get('selling_stockholders', [])
        if not tables:
            return None
        # Extract from first table
        result = extract_selling_stockholders_data(tables[0])
        # Merge additional tables (e.g. warrants table separate from common shares)
        for extra_table in tables[1:]:
            extra = extract_selling_stockholders_data(extra_table)
            if extra.is_populated:
                result.stockholders.extend(extra.stockholders)
                if extra.total_shares_offered and not result.total_shares_offered:
                    result.total_shares_offered = extra.total_shares_offered
        return result if result.is_populated else None

    @cached_property
    def structured_note_terms(self) -> Optional['StructuredNoteTerms']:
        """Structured note key terms (CUSIP, maturity, underlying, etc.).
        Returns None if no key terms table is found."""
        from edgar.offerings.prospectus._424b_tables import extract_structured_note_terms
        tables = self._classified_tables.get('key_terms', [])
        if not tables:
            return None
        # Merge terms from all key_terms tables (some filings split across multiple)
        merged = extract_structured_note_terms(tables[0])
        for extra_table in tables[1:]:
            extra = extract_structured_note_terms(extra_table)
            for field in merged.model_fields:
                if field == 'additional_terms':
                    continue
                if getattr(merged, field) is None and getattr(extra, field) is not None:
                    setattr(merged, field, getattr(extra, field))
            for k, v in extra.additional_terms.items():
                if k not in merged.additional_terms:
                    merged.additional_terms[k] = v
        return merged

    @cached_property
    def dilution(self) -> Optional['DilutionData']:
        """Per-share dilution impact table."""
        from edgar.offerings.prospectus._424b_tables import extract_dilution_data
        tables = self._classified_tables.get('dilution', [])
        if not tables:
            return None
        return extract_dilution_data(tables[0])

    @cached_property
    def capitalization(self) -> Optional['CapitalizationData']:
        """Actual vs. as-adjusted capitalization table."""
        from edgar.offerings.prospectus._424b_tables import extract_capitalization_data
        tables = self._classified_tables.get('capitalization', [])
        if not tables:
            return None
        return extract_capitalization_data(tables[0])

    @cached_property
    def underwriting(self) -> Optional['UnderwritingInfo']:
        """Underwriting syndicate or placement agent info.
        Uses table extraction first, falls back to cover page text."""
        from edgar.offerings.prospectus._424b_tables import (
            extract_underwriting_from_tables,
            is_plausible_underwriter_name,
        )
        from edgar.offerings.prospectus._424b_cover import extract_underwriting_from_text

        doc = self._document
        if not doc:
            return None

        # Try table-based extraction first (most reliable)
        table_results = extract_underwriting_from_tables(doc)

        entries: list[UnderwriterEntry] = []
        fee_type = 'underwriting_discount'

        # Prefer allocation tables (have full legal names). Guard every name:
        # 424B2 structured-note/debt covers leak legalese paragraphs and lone
        # bullets into the name slot (edgartools-2h4c).
        alloc = [r for r in table_results if r['type'] == 'allocation' and r['names']]
        if alloc:
            for name, amt in zip(alloc[0]['names'], alloc[0].get('allocations', [])):
                if is_plausible_underwriter_name(name):
                    entries.append(UnderwriterEntry(name=name, shares_allocated=amt))
        else:
            # Use cover grid or role listing names
            for tr in table_results:
                for name in tr['names']:
                    if is_plausible_underwriter_name(name) \
                            and not any(e.name == name for e in entries):
                        entries.append(UnderwriterEntry(name=name))

        # Fall back to text-based extraction if no tables found
        if not entries:
            text_results = extract_underwriting_from_text(self._filing, document=doc)
            for tx in text_results:
                for name in tx['names']:
                    if is_plausible_underwriter_name(name) \
                            and not any(e.name == name for e in entries):
                        entries.append(UnderwriterEntry(name=name))
                if tx['role'] in ('sole_placement_agent', 'placement_agent'):
                    fee_type = 'placement_agent_fees'

        if not entries:
            return None

        # Detect fee type from pricing table if available
        if self.pricing and self.pricing.fee_type:
            fee_type = self.pricing.fee_type

        return UnderwritingInfo(
            underwriters=entries,
            fee_type=fee_type,
        )

    @cached_property
    def filing_fees(self) -> 'FilingFeesData':
        """Filing fees from EX-FILING FEES XBRL exhibit.
        Available for ~43% of 424B2, ~23% of 424B5. Returns empty if no exhibit."""
        # Reuse the exhibit already fetched during classification, if any.
        if self._eager_filing_fees is not None:
            return self._eager_filing_fees
        from edgar.offerings.prospectus._424b_xbrl import extract_filing_fees_xbrl
        return _build_filing_fees_data(extract_filing_fees_xbrl(self._filing))

    # ------------------------------------------------------------------
    # Lifecycle navigation
    # ------------------------------------------------------------------

    @cached_property
    def lifecycle(self) -> Optional[ShelfLifecycle]:
        """Shelf lifecycle position and insights.

        Returns a ShelfLifecycle object with takedown position, shelf expiry,
        review period, cadence analysis, and a Rich timeline display.
        Returns None if related filings cannot be determined.
        """
        try:
            # Use file_number from cover page (already extracted from SGML header)
            # to skip the redundant accession_number lookup in related_filings().
            # Use trigger_full_load=False to avoid paginating through the entire
            # filing history — shelf registrations expire after 3 years so the
            # relevant filings are almost always in the most recent ~1000.
            file_number = self._cover_page.registration_number
            if file_number:
                from edgar.entity import Company
                company = Company(self._filing.cik)
                related = company.get_filings(
                    file_number=file_number,
                    sort_by=[("filing_date", "ascending"), ("accession_number", "ascending")],
                    trigger_full_load=False,
                )
                if related is not None and not related.empty:
                    return ShelfLifecycle(self._filing, related)
            # Fallback to generic related_filings if no file number on cover page
            related = self._filing.related_filings()
            if related is None or related.empty:
                return None
            return ShelfLifecycle(self._filing, related)
        except Exception as e:
            log.debug("ShelfLifecycle construction failed for %s: %s", self._filing.accession_no, e)
            return None

    @cached_property
    def shelf_registration(self) -> Optional['Filing']:
        """The shelf registration filing (S-3, F-3, S-1). Delegates to lifecycle."""
        lc = self.lifecycle
        return lc.shelf_registration if lc else None

    @cached_property
    def related_filings(self):
        """All filings under the same shelf file number. Delegates to lifecycle."""
        lc = self.lifecycle
        return lc.filings if lc else None

    @cached_property
    def related_8k(self) -> Optional['Filing']:
        """8-K filed on the same day. Delegates to lifecycle."""
        lc = self.lifecycle
        return lc.related_8k if lc else None

    # ------------------------------------------------------------------
    # Deal summary
    # ------------------------------------------------------------------

    @cached_property
    def deal(self) -> 'Deal':
        """Normalized deal summary with computed metrics.

        Always returns a Deal object (never None). Individual fields
        within it are None when data is unavailable.
        """
        return Deal(self)
