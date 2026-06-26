from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import List, Optional, Union

import pyarrow.compute as pc
from lxml import etree

from edgar._party import Address

__all__ = [
    'FilingManager',
    'OtherManager',
    'CoverPage',
    'AmendmentInfo',
    'SummaryPage',
    'Signature',
    'PrimaryDocument13F',
    'ThirteenF',
    'HoldingsView',
    'HoldingsComparison',
    'HoldingsHistory',
    'THIRTEENF_FORMS',
    'format_date',
]

THIRTEENF_FORMS = ['13F-HR', "13F-HR/A", "13F-NT", "13F-NT/A", "13F-CTR", "13F-CTR/A"]

# SEC Release 34-96734 switched Form 13F <value> reporting from *thousands* to *whole
# dollars* for periods ending on/after 2022-12-31. However, the reporting unit is a
# property of the individual filing (which schema/software the filer used), NOT of the
# report period: during and after the transition, filings for the same report period
# arrive in BOTH units (late/amended filings keep both alive in every period). A single
# date threshold therefore mis-scales a meaningful, non-shrinking fraction of filings in
# both directions (see issue edgartools-mun2). The unit is now detected per-filing from
# the holdings themselves (see `_detect_value_in_thousands`); this date cutoff survives
# only as a last-resort fallback when a filing has no priceable equity rows.
_13F_VALUE_IN_THOUSANDS_CUTOFF = datetime(2022, 9, 30)

# An implied equity price (Value / SharesPrnAmount under the "as-reported = dollars"
# hypothesis) below this is dollar-implausible: real equities almost never trade under $1,
# so such a holding is evidence the filing actually reports in thousands (the two unit
# hypotheses sit exactly 1000x apart).
_13F_IMPLIED_PRICE_THOUSANDS_THRESHOLD = 1.0

# Fraction of priceable equity holdings whose implied price is sub-$1 at/above which the
# filing is unambiguously in thousands. Empirically (sampled across the 2020-2024
# transition) this fraction is sharply bimodal: genuine whole-dollar filings sit near 0.0
# (almost no sub-$1 equities) and thousands filings near 1.0 (every normal stock looks
# sub-$1 once divided by 1000). A high fraction can ONLY be a thousands filing, so it is
# decided from price alone. A LOW fraction is NOT decisive the other way: a filing with no
# sub-$1 holdings is genuinely ambiguous between normal whole-dollar pricing and a
# thousands filing concentrated in >$1000 shares (BRK.A ~$680k, pre-split AMZN/GOOGL). Per
# the field evidence in edgartools-mun2, magnitude must NEVER decide the high side (no upper
# price cap); those filings defer to the schema-version / date prior instead.
_13F_FRAC_THOUSANDS = 0.5   # >= this share of holdings sub-$1 => unambiguously thousands

# Form 13F primary-document <schemaVersion> at/after which the SEC's whole-dollar value
# convention shipped. Used only as a prior for ambiguous / unpriceable filings.
_13F_DOLLARS_SCHEMA_VERSION = 'X0202'


def _schema_implies_dollars(schema_version: Optional[str]) -> Optional[bool]:
    """
    Prior on the reporting unit from the primary-document ``<schemaVersion>``.

    Returns True if the schema version indicates the whole-dollar era, False if it
    indicates the older thousands era, or None when there is no usable version (caller
    then falls back to the report-period date cutoff).

    This is only a *prior*: real filers demonstrably submit the new schema while still
    reporting in thousands (e.g. Bull Street, Abeille, GSA), so it is consulted only to
    break ties in the ambiguous band and for filings with no priceable equity rows.
    """
    if not schema_version:
        return None
    return schema_version.strip().upper() >= _13F_DOLLARS_SCHEMA_VERSION


def _resolve_unit_fallback(schema_version: Optional[str],
                           report_period_dt: Optional[datetime]) -> bool:
    """Schema-version prior, then the legacy report-period date cutoff. Returns
    True if the filing should be treated as reporting in thousands."""
    dollars = _schema_implies_dollars(schema_version)
    if dollars is not None:
        return not dollars
    return report_period_dt is not None and report_period_dt <= _13F_VALUE_IN_THOUSANDS_CUTOFF


def _detect_value_in_thousands(df,
                               schema_version: Optional[str] = None,
                               report_period_dt: Optional[datetime] = None) -> bool:
    """
    Determine whether a 13F information table reports ``<value>`` in thousands (vs. whole
    dollars) per-filing, from the holdings themselves.

    A single 13F reports *all* holdings in *one* unit. Under the "as-reported = dollars"
    interpretation the implied price of an equity holding is ``Value / SharesPrnAmount``;
    if the filing is actually in thousands, every implied price is ~1000x too low. The
    decision is asymmetric:

    - **High side (decisive):** if a large *fraction* of share holdings imply a sub-$1
      price, the filing can only be in thousands (a real whole-dollar portfolio almost
      never holds majority sub-$1 equities). This is decided from price alone, and it is
      what lets a filing using the new whole-dollar schema yet still reporting in thousands
      be caught (the real Bull Street / Abeille / GSA case).
    - **Low side (NOT decisive):** few or no sub-$1 holdings is genuinely ambiguous —
      it is either normal whole-dollar pricing or a thousands filing concentrated in
      >$1000 shares (BRK.A ~$680k, pre-split AMZN/GOOGL). Price magnitude must never be
      used to decide here (no upper cap); such filings defer to the schema-version prior,
      then the report-period date cutoff. This is reliable because genuine whole-dollar
      filings essentially always carry the new schema (the old-schema/pre-cutover era was
      uniformly thousands).

    Only ``Type == 'Shares'`` non-option rows are priced: bonds (``Principal``) trade near
    par so the ratio hovers around 1.0 — useless for discrimination — and option ``Value``
    is notional.

    Args:
        df: Raw, *unscaled* holdings DataFrame as produced by the infotable parsers.
        schema_version: Primary-document ``<schemaVersion>`` (e.g. 'X0202'); the prior for
            every non-thousands-confident filing.
        report_period_dt: Report period end date, used as the final fallback.

    Returns:
        True if the filing's values are in thousands and must be multiplied by 1000.
    """
    import pandas as pd

    try:
        sh = df[(df['Type'] == 'Shares') & (df['SharesPrnAmount'] > 0)]
        if 'PutCall' in sh.columns:
            put_call = sh['PutCall'].fillna('')
            sh = sh[put_call == '']
        values = pd.to_numeric(sh['Value'], errors='coerce')
        shares = pd.to_numeric(sh['SharesPrnAmount'], errors='coerce')
        implied = (values / shares).replace([float('inf'), float('-inf')], pd.NA).dropna()
        implied = implied[implied > 0]
        if len(implied) > 0:
            frac_sub_dollar = float((implied < _13F_IMPLIED_PRICE_THOUSANDS_THRESHOLD).mean())
            if frac_sub_dollar >= _13F_FRAC_THOUSANDS:
                return True  # decisive: majority sub-$1 can only be thousands
            # Low side is ambiguous (normal dollars vs. thousands-of->$1000-shares). Never
            # decide from magnitude; defer to the schema-version / date prior.
            return _resolve_unit_fallback(schema_version, report_period_dt)
    except (KeyError, TypeError, ValueError):
        pass

    # No priceable equity rows (e.g. bond-only or PRN-only filings).
    return _resolve_unit_fallback(schema_version, report_period_dt)


def format_date(date: Union[str, datetime]) -> str:
    if isinstance(date, str):
        return date
    return date.strftime("%Y-%m-%d")


@dataclass(frozen=True)
class FilingManager:
    name: str
    address: Address


@dataclass(frozen=True)
class OtherManager:
    cik: str
    name: str
    file_number: str
    sequence_number: int = None


@dataclass(frozen=True)
class AmendmentInfo:
    """Amendment metadata from a 13F cover page (<amendmentInfo>).

    ``amendment_type`` is the load-bearing field (GH #872):

    - ``"RESTATEMENT"`` — a full re-filing of the entire holdings report; it
      *replaces* the original filing.
    - ``"NEW HOLDINGS"`` — adds only positions previously omitted under
      confidential treatment and now being disclosed; it must be *combined with*
      (unioned with) the original and does **not** replace it. Usually paired
      with ``conf_denied_expired=True``.
    """
    amendment_type: Optional[str] = None
    conf_denied_expired: Optional[bool] = None
    date_denied_expired: Optional[str] = None
    date_reported: Optional[str] = None
    reason_for_non_confidentiality: Optional[str] = None


@dataclass(frozen=True)
class CoverPage:
    report_calendar_or_quarter: str
    report_type: str
    filing_manager: FilingManager
    other_managers: List[OtherManager]
    is_amendment: bool = False
    amendment_number: Optional[int] = None
    amendment_info: Optional[AmendmentInfo] = None


@dataclass(frozen=True)
class SummaryPage:
    other_included_managers_count: int
    total_value: Decimal
    total_holdings: int
    other_managers: List['OtherManager'] = None


@dataclass(frozen=True)
class Signature:
    name: str
    title: str
    phone: str
    signature: str
    city: str
    state_or_country: str
    date: str


@dataclass(frozen=True)
class PrimaryDocument13F:
    report_period: datetime
    cover_page: CoverPage
    summary_page: SummaryPage
    signature: Signature
    additional_information: str


class HoldingsView:
    """View of 13F holdings as a Rich-renderable, iterable object."""

    def __init__(self, data, thirteen_f, display_limit: int = 200):
        self.data = data              # The summary DataFrame
        self._thirteen_f = thirteen_f  # For title/metadata in rendering
        self.display_limit = display_limit

    def __rich__(self):
        from edgar.thirteenf.rendering import render_holdings_view
        return render_holdings_view(self, display_limit=self.display_limit)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        """Iterate over rows as dicts."""
        columns = self.data.columns.tolist()
        for row in self.data.itertuples(index=False, name=None):
            yield dict(zip(columns, row))

    def __getitem__(self, index):
        """Slice the underlying DataFrame."""
        if isinstance(index, int):
            return self.data.iloc[index].to_dict()
        return self.data.iloc[index]


class HoldingsComparison:
    """Comparison of 13F holdings between two consecutive quarters."""

    def __init__(self, data, current_period: str, previous_period: str, manager_name: str,
                 display_limit: int = 200):
        self.data = data
        self.current_period = current_period
        self.previous_period = previous_period
        self.manager_name = manager_name
        self.display_limit = display_limit

    def __rich__(self):
        from edgar.thirteenf.rendering import render_holdings_comparison
        return render_holdings_comparison(self, display_limit=self.display_limit)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        """Iterate over rows as dicts."""
        columns = self.data.columns.tolist()
        for row in self.data.itertuples(index=False, name=None):
            yield dict(zip(columns, row))

    def __getitem__(self, index):
        """Slice the underlying DataFrame."""
        if isinstance(index, int):
            return self.data.iloc[index].to_dict()
        return self.data.iloc[index]


class HoldingsHistory:
    """Multi-quarter share history for 13F holdings with sparkline trends."""

    def __init__(self, data, periods: list, manager_name: str,
                 display_limit: int = 100):
        self.data = data
        self.periods = periods
        self.manager_name = manager_name
        self.display_limit = display_limit

    def __rich__(self):
        from edgar.thirteenf.rendering import render_holdings_history
        return render_holdings_history(self, display_limit=self.display_limit)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        """Iterate over rows as dicts."""
        columns = self.data.columns.tolist()
        for row in self.data.itertuples(index=False, name=None):
            yield dict(zip(columns, row))

    def __getitem__(self, index):
        """Slice the underlying DataFrame."""
        if isinstance(index, int):
            return self.data.iloc[index].to_dict()
        return self.data.iloc[index]


class ThirteenF:
    """
    A 13F-HR is a quarterly report filed by institutional investment managers that have over $100 million in qualifying
    assets under management. The report is filed with the Securities & Exchange Commission (SEC) and discloses all
    the firm's equity holdings that it held at the end of the quarter. The report is due within 45 days of the end
    of the quarter. The 13F-HR is a public document that is available on the SEC's website.
    """

    # Class-level cache provider (can be set to integrate with Redis/external cache)
    # Override this in your application to provide cached holdings
    _cache_provider = None

    @classmethod
    def set_cache_provider(cls, provider):
        """
        Set a cache provider for holdings data.

        The provider should be a callable that takes an accession number and returns
        a pandas DataFrame of holdings, or None if not cached.

        Example:
            def redis_cache_provider(accession_no):
                # Check Redis
                cached = redis.get(f"thirteenf:holdings:{accession_no}")
                if cached:
                    return pd.read_json(cached)
                return None

            ThirteenF.set_cache_provider(redis_cache_provider)
        """
        cls._cache_provider = provider

    def __init__(self, filing, use_latest_period_of_report=False):
        from edgar.thirteenf.parsers.primary_xml import parse_primary_document_xml

        assert filing.form in THIRTEENF_FORMS, f"Form {filing.form} is not a valid 13F form"
        self._actual_filing = filing  # The filing passed in
        self.__related_filings = None  # Lazy-loaded: all related filings
        self.__same_day_filings = None  # Lazy-loaded: same-date + same-form subset
        self._previous_holding_report_cache = None  # Cached result for previous_holding_report()
        self._previous_holding_report_cached = False  # Separate flag since result can be None
        # Per-filing thousands/dollars unit, detected lazily when the infotable is built.
        # None = not yet determined. See `_detect_value_in_thousands`.
        self._value_in_thousands_flag = None

        if use_latest_period_of_report:
            # Use the last related filing filed on the same date.
            # It should also be the one that has the CONFORMED_PERIOD_OF_REPORT closest to filing_date
            self.filing = self._same_day_filings[-1]
        else:
            # Use the exact filing that was passed in
            self.filing = self._actual_filing

        # Parse primary document if XML is available (2013+ filings)
        # For older TXT-only filings (2012 and earlier), primary_form_information will be None
        primary_xml = self.filing.xml()
        self.primary_form_information = parse_primary_document_xml(primary_xml) if primary_xml else None

    @property
    def _related_filings(self):
        """Lazy-load related 13F filings (used by previous_holding_report)."""
        if self.__related_filings is None:
            self.__related_filings = self._actual_filing.related_filings().filter(
                form=self._actual_filing.form
            )
        return self.__related_filings

    @property
    def _same_day_filings(self):
        """Lazy-load related filings filed on the same date with the same form."""
        if self.__same_day_filings is None:
            self.__same_day_filings = self._related_filings.filter(
                filing_date=self._actual_filing.filing_date,
                form=self._actual_filing.form
            )
        return self.__same_day_filings

    def has_infotable(self):
        return self.filing.form in ['13F-HR', "13F-HR/A"]

    @property
    def form(self):
        return self.filing.form

    @property
    def is_amendment(self) -> bool:
        """True if this filing is a 13F amendment (e.g. ``13F-HR/A``).

        Reads ``<isAmendment>`` from the cover page when the primary XML is
        available (2013+); for older TXT-only filings it falls back to the form
        suffix.
        """
        if self.primary_form_information is not None:
            return self.primary_form_information.cover_page.is_amendment
        return self.form.endswith("/A")

    @property
    def amendment_type(self) -> Optional[str]:
        """The amendment type for a 13F amendment, or ``None``.

        Returns ``"RESTATEMENT"`` or ``"NEW HOLDINGS"`` (GH #872). The
        distinction is load-bearing for correctness:

        - ``RESTATEMENT`` re-files the entire report and *replaces* the original.
        - ``NEW HOLDINGS`` adds only previously-confidential positions and must
          be combined (unioned) with the original — it does **not** replace it.
          Superseding the original with a ``NEW HOLDINGS`` amendment silently
          drops the real portfolio.

        Returns ``None`` when this is not an amendment, or when the amendment
        type is absent (e.g. older TXT-only filings).
        """
        info = self.primary_form_information
        if info is None or info.cover_page.amendment_info is None:
            return None
        return info.cover_page.amendment_info.amendment_type

    @property
    def amendment_number(self) -> Optional[int]:
        """The amendment sequence number (``<amendmentNo>``), or ``None``."""
        info = self.primary_form_information
        if info is None:
            return None
        return info.cover_page.amendment_number

    @property
    def amendment_info(self) -> Optional['AmendmentInfo']:
        """Full amendment metadata (type, confidential-treatment fields), or ``None``."""
        info = self.primary_form_information
        if info is None:
            return None
        return info.cover_page.amendment_info

    @cached_property
    def infotable_xml(self):
        """Returns XML content if available (2013+ filings)"""
        if self.has_infotable():
            result = self._get_infotable_from_attachment()
            if result and result[0] and result[1] == 'xml' and "informationTable" in result[0]:
                return result[0]
        return None

    def _get_infotable_from_attachment(self):
        """
        Use the filing homepage to get the infotable file.
        Returns a tuple of (content, format) where format is 'xml' or 'txt'.
        """
        if self.has_infotable():
            # Try XML format first (2013+)
            query = "document_type=='INFORMATION TABLE' and document.lower().endswith('.xml')"
            attachments = self.filing.attachments.query(query)
            if len(attachments) > 0:
                return (attachments.get_by_index(0).download(), 'xml')

            # Fall back to TXT format (2012 and earlier)
            # The primary document itself contains the table in TXT format
            # Try various description patterns first
            query = "description=='FORM 13F' or description=='INFORMATION TABLE'"
            attachments = self.filing.attachments.query(query)
            if len(attachments) > 0:
                # Filter for .txt files only
                txt_attachments = [att for att in attachments if att.document.lower().endswith('.txt')]
                if txt_attachments:
                    return (txt_attachments[0].download(), 'txt')

            # Final fallback: For older filings, descriptions may be unreliable
            # Look for sequence number 1 with .txt extension
            try:
                att = self.filing.attachments.get_by_sequence(1)
                if att and att.document.lower().endswith('.txt'):
                    return (att.download(), 'txt')
            except (KeyError, AttributeError):
                pass

            return (None, None)

    @cached_property
    def infotable_txt(self):
        """Returns TXT content if available (pre-2013 filings)"""
        if self.has_infotable():
            result = self._get_infotable_from_attachment()
            if result and result[0] and result[1] == 'txt':
                return result[0]

            # Fallback: Some filings have the information table embedded in the main HTML
            # instead of as a separate attachment. Try to extract it from the main HTML.
            if not result or not result[0]:
                html = self.filing.html()
                if html and "Form 13F Information Table" in html:
                    return html
        return None

    @cached_property
    def infotable_html(self):
        if self.has_infotable():
            query = "document_type=='INFORMATION TABLE' and document.lower().endswith('.html')"
            attachments = self.filing.attachments.query(query)
            return attachments[0].download()

    @cached_property
    def infotable(self):
        """
        Returns the information table as a pandas DataFrame (disaggregated by manager).

        For multi-manager filings, this returns separate rows for each manager combination's
        holdings of the same security. Use the `holdings` property for an aggregated view.

        Supports both XML format (2013+) and TXT format (2012 and earlier).

        Returns:
            pd.DataFrame: Holdings disaggregated by manager, with OtherManager column

        See Also:
            holdings: Aggregated view (recommended for most users)
        """
        from edgar.thirteenf.parsers.infotable_txt import parse_infotable_txt
        from edgar.thirteenf.parsers.infotable_xml import parse_infotable_xml

        if self.has_infotable():
            # Try XML format first
            if self.infotable_xml:
                df = parse_infotable_xml(self.infotable_xml)
            # Fall back to TXT format
            elif self.infotable_txt:
                df = parse_infotable_txt(self.infotable_txt)
            else:
                return None
            # Detect this filing's reporting unit from the raw holdings (per-filing, not a
            # report-period date rule) and normalize thousands -> dollars. Detection must
            # run on the unscaled values, so it happens here rather than reading back the
            # already-scaled column. The result is cached for `total_value` to reuse.
            if df is not None and len(df) > 0:
                in_thousands = _detect_value_in_thousands(
                    df, self._schema_version, self._report_period_dt
                )
                self._value_in_thousands_flag = in_thousands
                if in_thousands:
                    df['Value'] = df['Value'] * 1000
            return df
        return None

    @cached_property
    def holdings(self):
        """
        Returns aggregated holdings by security (user-friendly view).

        For multi-manager filings, this aggregates holdings across all manager combinations,
        providing a single row per unique security. This is the recommended view for most users
        as it matches industry-standard presentation (CNBC, Bloomberg, etc.).

        Aggregation logic:
        - Group by CUSIP (unique security identifier)
        - Sum: SharesPrnAmount, Value, SoleVoting, SharedVoting, NonVoting
        - Keep: Issuer, Class, Cusip, Ticker, Type, PutCall (when consistent)
        - Drop: OtherManager, InvestmentDiscretion (manager-specific fields)

        Returns:
            pd.DataFrame: Holdings aggregated by security, sorted by value descending

        Example:
            >>> thirteen_f.holdings  # Aggregated view (e.g., 40 rows for Berkshire)
            >>> thirteen_f.infotable  # Disaggregated by manager (e.g., 121 rows)

        See Also:
            infotable: Disaggregated view showing manager-specific holdings
        """
        import pandas as pd

        # Check external cache first (e.g., Redis) - avoids loading infotable (saves 1500ms + 15 MB)
        if self.__class__._cache_provider is not None:
            try:
                cached = self.__class__._cache_provider(self.accession_number)
                if cached is not None:
                    return cached
            except Exception:
                # Cache provider failed - fall through to normal computation
                pass

        # Cache miss or no provider - load from infotable
        infotable = self.infotable
        if infotable is None or len(infotable) == 0:
            return None

        # Columns to keep as-is (first value when grouping)
        id_cols = ['Issuer', 'Class', 'Cusip', 'Ticker']

        # Columns to sum across managers
        sum_cols = ['SharesPrnAmount', 'Value', 'SoleVoting', 'SharedVoting', 'NonVoting']

        # Check if numeric columns need conversion (handle potential object/string dtypes)
        # Use pd.api.types for pandas 2.x/3.x compatibility
        # Note: We only copy if we need to modify dtypes, otherwise aggregate directly
        cols_to_convert = [
            col for col in sum_cols
            if col in infotable.columns and (pd.api.types.is_object_dtype(infotable[col]) or pd.api.types.is_string_dtype(infotable[col]))
        ]

        if cols_to_convert:
            # Only copy if we need to convert dtypes
            df = infotable.copy()
            df[cols_to_convert] = df[cols_to_convert].apply(pd.to_numeric, errors='coerce').fillna(0).astype('int64')
        else:
            # No conversion needed - aggregate directly (saves 15 MB copy + 30ms)
            df = infotable

        # Group by CUSIP + PutCall so option positions stay distinct from equity (GH #824).
        group_keys = ['Cusip']
        if 'PutCall' in df.columns:
            group_keys.append('PutCall')

        agg_dict = {}

        # Keep first value for ID columns
        for col in id_cols:
            if col in df.columns:
                agg_dict[col] = 'first'

        # Sum numeric columns
        for col in sum_cols:
            if col in df.columns:
                agg_dict[col] = 'sum'

        # Type keeps first; PutCall is now a grouping key so it's excluded from agg_dict.
        if 'Type' in df.columns:
            agg_dict['Type'] = 'first'

        holdings = df.groupby(group_keys, as_index=False).agg(agg_dict)

        # Restore PutCall column position. pandas groupby() with PutCall as a key
        # places it as the second column (right after Cusip), silently shifting
        # the column layout. This breaks positional column access, table
        # rendering order, and notebook code with hardcoded indices. Re-insert
        # PutCall after Ticker to preserve the pre-aggregation column contract.
        if 'PutCall' in holdings.columns:
            cols = [c for c in holdings.columns if c != 'PutCall']
            insert_after = 'Ticker' if 'Ticker' in cols else (id_cols[-1] if id_cols[-1] in cols else cols[-1])
            idx = cols.index(insert_after) + 1
            cols.insert(idx, 'PutCall')
            holdings = holdings[cols]

        # Optimize dtypes for low-cardinality columns (saves ~1-2 MB)
        # Include potential fillna values in categories for rendering compatibility
        if 'Type' in holdings.columns:
            holdings['Type'] = pd.Categorical(
                holdings['Type'],
                categories=['Shares', 'Principal', '-']
            )
        if 'PutCall' in holdings.columns:
            # SEC XML emits title-case ('Put', 'Call'); uppercase categories silently dropped values.
            holdings['PutCall'] = pd.Categorical(
                holdings['PutCall'],
                categories=['', 'Put', 'Call']
            )

        # Sort by value descending
        if 'Value' in holdings.columns:
            holdings = holdings.sort_values('Value', ascending=False).reset_index(drop=True)

        return holdings

    @property
    def accession_number(self):
        return self.filing.accession_no

    @property
    def total_value(self):
        """Total value of holdings in dollars"""
        if self.primary_form_information:
            value = self.primary_form_information.summary_page.total_value
            if value and self._value_in_thousands:
                return value * 1000
            return value
        # For TXT-only filings, calculate from infotable (already normalized)
        infotable = self.infotable
        if infotable is not None and len(infotable) > 0:
            return Decimal(int(infotable['Value'].sum()))
        return None

    @property
    def total_holdings(self):
        """Total number of holdings"""
        if self.primary_form_information:
            return self.primary_form_information.summary_page.total_holdings
        # For TXT-only filings, count from infotable
        infotable = self.infotable
        if infotable is not None:
            return len(infotable)
        return None

    @property
    def other_managers(self) -> list:
        """
        List of other included managers in this consolidated 13F filing.

        For multi-manager institutional filings (e.g., State Street, Bank of America),
        this returns the affiliated entities whose holdings are reported together.
        Each manager includes CIK, name, file number, and sequence number.

        Returns:
            list[OtherManager]: List of other managers, or empty list if none

        Example:
            >>> thirteenf.other_managers
            [OtherManager(cik='0001102113', name='BANK OF AMERICA NA', ...)]
        """
        if self.primary_form_information:
            summary_page = self.primary_form_information.summary_page
            if summary_page and summary_page.other_managers:
                return summary_page.other_managers
        return []

    @property
    def _report_period_dt(self) -> Optional[datetime]:
        """Report period as a datetime (for internal comparisons)."""
        if self.primary_form_information:
            return self.primary_form_information.report_period
        if hasattr(self.filing, 'period_of_report') and self.filing.period_of_report:
            por = self.filing.period_of_report
            return datetime.strptime(por, "%Y-%m-%d") if isinstance(por, str) else por
        return None

    @cached_property
    def _schema_version(self) -> Optional[str]:
        """
        The Form 13F primary-document ``<schemaVersion>`` (e.g. 'X0202'), or None for older
        filings that omit it. Used as a prior for the reporting-unit detection.
        """
        try:
            primary_xml = self.filing.xml()
            if not primary_xml:
                return None
            root = etree.fromstring(
                primary_xml.strip().encode('utf-8'),
                parser=etree.XMLParser(recover=True),
            )
            for el in root.iter():
                tag = el.tag.rsplit('}', 1)[-1] if isinstance(el.tag, str) else ''
                if tag == 'schemaVersion':
                    return (el.text or '').strip() or None
        except (etree.XMLSyntaxError, ValueError, TypeError):
            return None
        return None

    @property
    def _value_in_thousands(self) -> bool:
        """
        True if this filing's values are in thousands and must be scaled to dollars.

        Detected per-filing from the holdings themselves (see `_detect_value_in_thousands`),
        not from the report period. Building the infotable runs and caches the detection;
        if there is no infotable (e.g. 13F-NT), fall back to the schema-version prior and
        then the report-period date cutoff.
        """
        if self._value_in_thousands_flag is None and self.has_infotable():
            # Trigger infotable build, which performs and caches detection.
            _ = self.infotable
        if self._value_in_thousands_flag is not None:
            return self._value_in_thousands_flag
        return _resolve_unit_fallback(self._schema_version, self._report_period_dt)

    @property
    def report_period(self):
        """Report period end date"""
        if self.primary_form_information:
            return format_date(self.primary_form_information.report_period)
        # For TXT-only filings, use CONFORMED_PERIOD_OF_REPORT from filing header
        if hasattr(self.filing, 'period_of_report') and self.filing.period_of_report:
            return format_date(self.filing.period_of_report)
        return None

    @property
    def filing_date(self):
        return format_date(self.filing.filing_date)

    @property
    def investment_manager(self):
        # This is really the firm e.g. Spark Growth Management Partners II, LLC
        if self.primary_form_information:
            return self.primary_form_information.cover_page.filing_manager
        return None

    @property
    def signer(self):
        # This is the person who signed the filing. Could be the Reporting Manager but could be someone else
        # like the CFO
        if self.primary_form_information:
            return self.primary_form_information.signature.name
        return None

    # Enhanced manager name properties for better clarity
    @property
    def management_company_name(self) -> str:
        """
        The legal name of the investment management company that filed the 13F.

        This is the institutional entity (e.g., "Berkshire Hathaway Inc", "Vanguard Group Inc")
        that is legally responsible for managing the assets, not an individual person's name.

        Returns:
            str: The legal name of the management company, or company name from filing if not available

        Example:
            >>> thirteen_f.management_company_name
            'Berkshire Hathaway Inc'
        """
        if self.investment_manager:
            return self.investment_manager.name
        # For TXT-only filings, use company name from filing
        return self.filing.company

    @property
    def filing_signer_name(self) -> str:
        """
        The name of the individual who signed the 13F filing.

        This is typically an administrative officer (CFO, CCO, Compliance Officer, etc.)
        rather than the famous portfolio manager. For example, Berkshire Hathaway's 13F
        is signed by "Marc D. Hamburg" (SVP), not Warren Buffett.

        Returns:
            str: The name of the person who signed the filing

        Example:
            >>> thirteen_f.filing_signer_name
            'Marc D. Hamburg'
        """
        return self.signer

    @property
    def filing_signer_title(self) -> Optional[str]:
        """
        The business title of the individual who signed the 13F filing.

        Common titles include: CFO, CCO, Senior Vice President, Chief Compliance Officer,
        Secretary, Treasurer, etc. This helps distinguish administrative signers from
        portfolio managers.

        Returns:
            str: The business title of the filing signer, or None if not available

        Example:
            >>> thirteen_f.filing_signer_title
            'Senior Vice President'
        """
        if self.primary_form_information:
            return self.primary_form_information.signature.title
        return None

    @property
    def manager_name(self) -> str:
        """
        DEPRECATED: Use management_company_name instead.

        Returns the management company name for backwards compatibility.
        This property name was misleading as it suggested an individual manager's name.

        Returns:
            str: The management company name

        Warning:
            This property is deprecated and may be removed in future versions.
            Use management_company_name for the company name, or see get_portfolio_managers()
            if you need information about individual portfolio managers.
        """
        import warnings
        warnings.warn(
            "manager_name is deprecated and misleading. Use management_company_name for the "
            "company name, or get_portfolio_managers() for individual manager information.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.management_company_name

    def get_portfolio_managers(self, include_approximate: bool = False) -> list[dict]:
        """
        Get information about the actual portfolio managers for this fund.

        Note: 13F filings do not contain individual portfolio manager names.
        This method provides a curated mapping for well-known funds based on
        public information. Results may not be current or complete.

        Args:
            include_approximate (bool): If True, includes approximate/historical
                                      manager information even if not current

        Returns:
            list[dict]: List of portfolio manager information with keys:
                       'name', 'title', 'status', 'source', 'last_updated'

        Example:
            >>> thirteen_f.get_portfolio_managers()
            [
                {
                    'name': 'Warren Buffett',
                    'title': 'Chairman & CEO',
                    'status': 'active',
                    'source': 'public_records',
                    'last_updated': '2024-01-01'
                }
            ]
        """
        from edgar.thirteenf.manager_lookup import lookup_portfolio_managers
        return lookup_portfolio_managers(
            self.management_company_name,
            getattr(self.filing, 'cik', None),
            include_approximate=include_approximate
        )

    def _lookup_portfolio_managers(self, company_name: str, include_approximate: bool = False) -> list[dict]:
        """
        Private method for testing - looks up portfolio managers by company name.

        Args:
            company_name: Name of the management company
            include_approximate: Whether to include approximate/historical data

        Returns:
            list[dict]: List of portfolio manager information
        """
        from edgar.thirteenf.manager_lookup import lookup_portfolio_managers
        return lookup_portfolio_managers(company_name, cik=None, include_approximate=include_approximate)

    def get_manager_info_summary(self) -> dict:
        """
        Get a comprehensive summary of all available manager information.

        This provides a clear breakdown of what information is available from the 13F
        filing versus external sources, helping users understand the data limitations.

        Returns:
            dict: Summary with keys 'from_13f_filing', 'external_sources', 'limitations'

        Example:
            >>> thirteen_f.get_manager_info_summary()
            {
                'from_13f_filing': {
                    'management_company': 'Berkshire Hathaway Inc',
                    'filing_signer': 'Marc D. Hamburg',
                    'signer_title': 'Senior Vice President'
                },
                'external_sources': {
                    'portfolio_managers': [
                        {'name': 'Warren Buffett', 'title': 'Chairman & CEO', 'status': 'active'}
                    ]
                },
                'limitations': [
                    '13F filings do not contain individual portfolio manager names',
                    'External manager data may not be current or complete',
                    'Filing signer is typically an administrative officer, not the portfolio manager'
                ]
            }
        """
        portfolio_managers = self.get_portfolio_managers()

        return {
            'from_13f_filing': {
                'management_company': self.management_company_name,
                'filing_signer': self.filing_signer_name,
                'signer_title': self.filing_signer_title,
                'form': self.form,
                'period_of_report': str(self.report_period)
            },
            'external_sources': {
                'portfolio_managers': portfolio_managers,
                'manager_count': len(portfolio_managers)
            },
            'limitations': [
                '13F filings do not contain individual portfolio manager names',
                'External manager data may not be current or complete',
                'Filing signer is typically an administrative officer, not the portfolio manager',
                'Portfolio manager information is sourced from public records and may be outdated'
            ]
        }

    def is_filing_signer_likely_portfolio_manager(self) -> bool:
        """
        Determine if the filing signer is likely to be a portfolio manager.

        This uses heuristics based on the signer's title to assess whether they
        might be involved in investment decisions rather than just administrative functions.

        Returns:
            bool: True if signer appears to be investment-focused, False if administrative

        Example:
            >>> thirteen_f.is_filing_signer_likely_portfolio_manager()
            False  # For administrative titles like CFO, CCO, etc.
        """
        from edgar.thirteenf.manager_lookup import is_filing_signer_likely_portfolio_manager
        return is_filing_signer_likely_portfolio_manager(self.filing_signer_title)

    def previous_holding_report(self):
        """
        Get the previous quarter's 13F filing.

        Optimized to fetch only the previous filing without loading all related filings.
        This avoids the 733ms overhead of loading all historical filings when only
        the previous quarter is needed.

        Finds the previous filing by report_period (not filing_date) to handle edge cases
        where companies file multiple historical 13F reports on the same day.

        Uses filings.data['reportDate'] to avoid network calls when comparing periods.
        """
        if self._previous_holding_report_cached:
            return self._previous_holding_report_cache

        result = self._find_previous_holding_report()
        self._previous_holding_report_cache = result
        self._previous_holding_report_cached = True
        return result

    def _find_previous_holding_report(self):
        """Internal implementation of previous_holding_report (uncached)."""
        if not self.report_period:
            return None

        # Helper function to find previous filing from sorted data
        def find_previous_from_sorted_data(sorted_data, sort_indices, filings_container):
            """
            Find the previous filing from sorted data.

            Args:
                sorted_data: PyArrow table sorted by reportDate descending
                sort_indices: Original indices for accessing filings_container
                filings_container: Filings object to get_filing_at from

            Returns:
                ThirteenF object or None
            """
            current_period = self.report_period
            if not current_period:
                return None

            try:
                current_date = datetime.strptime(current_period, '%Y-%m-%d')
            except ValueError:
                # Invalid date format in current period
                return None

            found_current = False
            fallback_candidate = None  # Store first earlier filing as fallback

            for i in range(len(sorted_data)):
                accession_no = sorted_data['accession_number'][i].as_py()
                report_date = sorted_data['reportDate'][i].as_py()

                if not report_date:
                    continue

                # Check if this is the current filing
                if accession_no == self.accession_number:
                    found_current = True
                    continue

                # If we've found current, look for the first earlier period
                if found_current:
                    try:
                        filing_date = datetime.strptime(report_date, '%Y-%m-%d')
                    except (ValueError, TypeError):
                        # Invalid date format, skip this filing
                        continue

                    # Verify it's earlier than current period
                    if filing_date < current_date:
                        days_diff = (current_date - filing_date).days

                        # Store as fallback if we haven't found one yet
                        if fallback_candidate is None:
                            fallback_candidate = (i, days_diff)

                        # Prefer filings within reasonable quarterly range (30-200 days)
                        if 30 <= days_diff <= 200:
                            original_index = sort_indices[i].as_py()
                            # Note: Not all Filings subclasses support enrich parameter
                            try:
                                previous_filing = filings_container.get_filing_at(original_index, enrich=False)
                            except TypeError:
                                previous_filing = filings_container.get_filing_at(original_index)
                            return ThirteenF(previous_filing, use_latest_period_of_report=False)

            # If no filing found in ideal range, use fallback (first earlier filing)
            if fallback_candidate is not None:
                i, days_diff = fallback_candidate
                original_index = sort_indices[i].as_py()
                # Note: Not all Filings subclasses support enrich parameter
                try:
                    previous_filing = filings_container.get_filing_at(original_index, enrich=False)
                except TypeError:
                    previous_filing = filings_container.get_filing_at(original_index)
                return ThirteenF(previous_filing, use_latest_period_of_report=False)

            return None

        # Optimized path: Use reportDate from filings.data (no network calls!)
        try:
            from edgar import Company

            # Get company and fetch recent 13F filings
            company = Company(self.filing.cik)
            recent_filings = company.get_filings(
                form=self.form,
                amendments=False  # Exclude amendments for cleaner history
            ).latest(40)  # Fetch more to handle batch filing scenarios (e.g., MetLife filed 8+ on same day)

            # Access the PyArrow table directly for efficient sorting
            data = recent_filings.data

            # Sort by reportDate (descending, so latest first)
            sort_indices = pc.sort_indices(data, sort_keys=[('reportDate', 'descending')])
            sorted_data = pc.take(data, sort_indices)

            result = find_previous_from_sorted_data(sorted_data, sort_indices, recent_filings)
            if result is not None:
                return result

        except (KeyError, AttributeError, ImportError) as e:
            # Specific exceptions: missing columns, Company import failed, etc.
            # Fall through to fallback path
            pass

        # Fallback path: Use related_filings with period-based sorting
        try:
            data = self._related_filings.data

            # Sort by reportDate
            sort_indices = pc.sort_indices(data, sort_keys=[('reportDate', 'descending')])
            sorted_data = pc.take(data, sort_indices)

            result = find_previous_from_sorted_data(sorted_data, sort_indices, self._related_filings)
            if result is not None:
                return result

        except (KeyError, AttributeError) as e:
            # Missing reportDate column or other data structure issues
            pass

        return None

    def holdings_view(self, display_limit: int = 200) -> Optional['HoldingsView']:
        """Return a view of current holdings as a renderable, iterable object.

        Unlike .holdings (a raw DataFrame), this returns a HoldingsView with
        __rich__(), __iter__(), and __getitem__() for display and downstream use.
        """
        from edgar.thirteenf.rendering import infotable_summary
        summary = infotable_summary(self)
        if summary is None:
            return None
        return HoldingsView(data=summary, thirteen_f=self, display_limit=display_limit)

    def compare_holdings(self, display_limit: int = 200) -> Optional['HoldingsComparison']:
        """Compare current holdings with the previous quarter.

        Returns a HoldingsComparison with per-security changes including
        share and value deltas, percentage changes, and status labels
        (NEW, CLOSED, INCREASED, DECREASED, UNCHANGED).

        Args:
            display_limit: Max rows to show in Rich display (default 200).
                           The .data DataFrame always contains all rows.

        Returns:
            HoldingsComparison or None if previous holdings are unavailable
        """
        import numpy as np
        import pandas as pd

        current = self.holdings
        if current is None or len(current) == 0:
            return None

        prev_report = self.previous_holding_report()
        if prev_report is None:
            return None
        previous = prev_report.holdings
        if previous is None or len(previous) == 0:
            return None

        cur = current[['Cusip', 'Ticker', 'Issuer', 'SharesPrnAmount', 'Value']].rename(
            columns={'SharesPrnAmount': 'Shares'}
        )

        prev = previous[['Cusip', 'Ticker', 'Issuer', 'SharesPrnAmount', 'Value']].rename(
            columns={
                'Ticker': 'Ticker_prev',
                'Issuer': 'Issuer_prev',
                'SharesPrnAmount': 'PrevShares',
                'Value': 'PrevValue'
            }
        )

        merged = cur.merge(prev, on='Cusip', how='outer')

        # Coalesce Ticker / Issuer
        merged['Ticker'] = merged['Ticker'].fillna(merged['Ticker_prev'])
        merged['Issuer'] = merged['Issuer'].fillna(merged['Issuer_prev'])
        merged.drop(columns=['Ticker_prev', 'Issuer_prev'], inplace=True)

        # Fill missing numeric values with NaN (they stay NaN for NEW/CLOSED)
        for col in ['Shares', 'PrevShares', 'Value', 'PrevValue']:
            merged[col] = pd.to_numeric(merged[col], errors='coerce')

        merged['ShareChange'] = merged['Shares'] - merged['PrevShares']
        merged['ShareChangePct'] = np.where(
            merged['PrevShares'].notna() & (merged['PrevShares'] != 0),
            (merged['ShareChange'] / merged['PrevShares']) * 100,
            np.nan,
        )
        merged['ValueChange'] = merged['Value'] - merged['PrevValue']
        merged['ValueChangePct'] = np.where(
            merged['PrevValue'].notna() & (merged['PrevValue'] != 0),
            (merged['ValueChange'] / merged['PrevValue']) * 100,
            np.nan,
        )

        # Vectorized status assignment (50x faster than apply)
        conditions = [
            merged['PrevShares'].isna(),
            merged['Shares'].isna(),
            merged['ShareChange'] > 0,
            merged['ShareChange'] < 0,
        ]
        choices = ['NEW', 'CLOSED', 'INCREASED', 'DECREASED']
        merged['Status'] = np.select(conditions, choices, default='UNCHANGED')
        merged.sort_values('ValueChange', key=lambda s: s.abs(), ascending=False, inplace=True, na_position='last')
        merged.reset_index(drop=True, inplace=True)

        return HoldingsComparison(
            data=merged,
            current_period=self.report_period,
            previous_period=prev_report.report_period,
            manager_name=self.management_company_name,
            display_limit=display_limit,
        )

    def holding_history(self, periods: int = 3, display_limit: int = 100) -> Optional['HoldingsHistory']:
        """Track share counts across multiple quarters.

        Walks backward through previous holding reports and builds a
        DataFrame with one column per quarter (oldest→newest, left→right)
        plus a Unicode sparkline trend.

        Args:
            periods: Number of quarters to include (default 3, reduced from 4 for performance)
            display_limit: Max rows to show in Rich display (default 200).
                           The .data DataFrame always contains all rows.

        Returns:
            HoldingsHistory or None if current holdings are unavailable
        """
        import pandas as pd

        # Collect all report objects first (fast - uses cached previous_holding_report)
        reports = [self]
        current = self
        for _ in range(periods - 1):
            prev = current.previous_holding_report()
            if prev is None:
                break
            reports.append(prev)
            current = prev

        if not reports:
            return None

        # Reverse so oldest is first
        reports = list(reversed(reports))

        # Deduplicate by report_period — keep the latest filing for each period
        seen = {}
        for r in reports:
            seen[r.report_period] = r  # later entry (newer filing) overwrites
        reports = [seen[k] for k in dict.fromkeys(r.report_period for r in reports)]
        period_labels = [r.report_period for r in reports]

        # Build merged DataFrame by iterating through periods
        # Original implementation - already optimized by pandas team
        merged = None
        for report in reports:
            h = report.holdings
            if h is None or len(h) == 0:
                continue
            col_name = report.report_period
            subset = h[['Cusip', 'Ticker', 'Issuer', 'SharesPrnAmount']].copy()
            subset.rename(columns={'SharesPrnAmount': col_name}, inplace=True)

            if merged is None:
                merged = subset
            else:
                # Merge on Cusip; coalesce Ticker/Issuer from newer data
                merged = merged.merge(
                    subset[['Cusip', col_name]],
                    on='Cusip',
                    how='outer',
                )
                # Update Ticker/Issuer from this (newer) report where missing
                # Use merge instead of map (2-3x faster than apply)
                new_ids = subset[['Cusip', 'Ticker', 'Issuer']].drop_duplicates('Cusip')
                new_ids = new_ids.rename(columns={'Ticker': 'Ticker_new', 'Issuer': 'Issuer_new'})
                merged = merged.merge(new_ids, on='Cusip', how='left')
                merged['Ticker'] = merged['Ticker'].fillna(merged['Ticker_new'])
                merged['Issuer'] = merged['Issuer'].fillna(merged['Issuer_new'])
                merged.drop(columns=['Ticker_new', 'Issuer_new'], inplace=True)

        if merged is None:
            return None

        # Sort by most recent period's shares descending
        most_recent = period_labels[-1]
        if most_recent in merged.columns:
            merged.sort_values(most_recent, ascending=False, na_position='last', inplace=True)
        merged.reset_index(drop=True, inplace=True)

        return HoldingsHistory(
            data=merged,
            periods=period_labels,
            manager_name=self.management_company_name,
            display_limit=display_limit,
        )

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~300 tokens), 'full' (~500+ tokens)
        """
        from edgar.display.formatting import format_currency_short

        lines = []

        # === IDENTITY ===
        lines.append(f"THIRTEENF: {self.management_company_name}")
        lines.append("")

        # === CORE METADATA ===
        lines.append(f"Report Date: {self.report_period}")

        if detail == 'minimal':
            try:
                total_val = self.total_value
                if total_val is not None:
                    lines.append(f"Holdings: {self.total_holdings}")
                    lines.append(f"Total Value: {format_currency_short(float(total_val))}")
            except Exception:
                pass
            return "\n".join(lines)

        # === STANDARD ===
        lines.append(f"CIK: {str(self.filing.cik).zfill(10)}")
        lines.append(f"Filed: {self.filing_date}")
        lines.append(f"Form: {self.form}")

        # Amendment signal (GH #872) — load-bearing for correctness.
        if self.is_amendment:
            atype = self.amendment_type
            if atype == "NEW HOLDINGS":
                lines.append(
                    "Amendment: NEW HOLDINGS — adds only previously-confidential positions; "
                    "UNION with the original filing (does not replace it)."
                )
            elif atype == "RESTATEMENT":
                lines.append("Amendment: RESTATEMENT — full re-file; replaces the original filing.")
            else:
                lines.append(f"Amendment: {atype or 'type unknown'}")

        # Summary section
        lines.append("")
        lines.append("SUMMARY:")
        try:
            lines.append(f"  Holdings: {self.total_holdings}")
            total_val = self.total_value
            if total_val is not None:
                lines.append(f"  Total Value: {format_currency_short(float(total_val))}")
        except Exception:
            pass

        # Top holdings
        top_n = 5
        try:
            holdings_df = self.holdings
            if holdings_df is not None and len(holdings_df) > 0:
                total_val_f = float(self.total_value) if self.total_value else None
                lines.append("")
                lines.append("TOP HOLDINGS:")
                for _, row in holdings_df.head(top_n).iterrows():
                    issuer = row.get('Issuer', '?')
                    val = float(row.get('Value', 0))
                    h_line = f"  {issuer}: {format_currency_short(val)}"
                    if total_val_f and total_val_f > 0:
                        pct = val / total_val_f * 100
                        h_line += f" ({pct:.1f}%)"
                    lines.append(h_line)
                remaining = len(holdings_df) - top_n
                if remaining > 0:
                    lines.append(f"  ... ({remaining} more)")
        except Exception:
            pass

        # Available actions
        lines.append("")
        lines.append("AVAILABLE ACTIONS:")
        lines.append("  .holdings                    All holdings as DataFrame")
        lines.append("  .holdings_view()             Formatted holdings table")
        lines.append("  .compare_holdings()          Quarter-over-quarter changes")
        lines.append("  .holding_history()           Multi-quarter history")
        lines.append("  .investment_manager          Manager name and address")
        lines.append("  .previous_holding_report()   Prior quarter filing")

        if detail == 'standard':
            return "\n".join(lines)

        # === FULL: top 10 instead of 5, manager details, signer ===
        try:
            holdings_df = self.holdings
            if holdings_df is not None and len(holdings_df) > top_n:
                extra = holdings_df.iloc[top_n:10]
                if len(extra) > 0:
                    # Find the overflow line and replace with additional holdings
                    insert_idx = None
                    for i, l in enumerate(lines):
                        if l.startswith("  ... ("):
                            insert_idx = i
                            break
                    if insert_idx is not None:
                        extra_lines = []
                        total_val_f = float(self.total_value) if self.total_value else None
                        for _, row in extra.iterrows():
                            issuer = row.get('Issuer', '?')
                            val = float(row.get('Value', 0))
                            h_line = f"  {issuer}: {format_currency_short(val)}"
                            if total_val_f and total_val_f > 0:
                                pct = val / total_val_f * 100
                                h_line += f" ({pct:.1f}%)"
                            extra_lines.append(h_line)
                        remaining_full = len(holdings_df) - 10
                        overflow = f"  ... ({remaining_full} more)" if remaining_full > 0 else None
                        lines[insert_idx:insert_idx + 1] = extra_lines + ([overflow] if overflow else [])
        except Exception:
            pass

        # Manager details
        try:
            mgr = self.investment_manager
            if mgr and mgr.address:
                addr = mgr.address
                addr_parts = []
                if hasattr(addr, 'city') and addr.city:
                    addr_parts.append(addr.city)
                if hasattr(addr, 'state') and addr.state:
                    addr_parts.append(addr.state)
                if addr_parts:
                    lines.append("")
                    lines.append(f"MANAGER: {mgr.name}")
                    lines.append(f"  Location: {', '.join(addr_parts)}")
        except Exception:
            pass

        # Signer
        try:
            if self.primary_form_information and self.primary_form_information.signature:
                sig = self.primary_form_information.signature
                if sig.name:
                    lines.append("")
                    lines.append("SIGNER:")
                    lines.append(f"  Name: {sig.name}")
                    if sig.title:
                        lines.append(f"  Title: {sig.title}")
        except Exception:
            pass

        # Other managers
        try:
            others = self.other_managers
            if others:
                lines.append("")
                lines.append(f"OTHER MANAGERS: {len(others)}")
                for om in others[:5]:
                    lines.append(f"  {om.name} (CIK: {om.cik})")
        except Exception:
            pass

        return "\n".join(lines)

    def __rich__(self):
        from edgar.thirteenf.rendering import render_rich
        return render_rich(self)

    def __repr__(self):
        from edgar.richtools import repr_rich
        return repr_rich(self.__rich__())


# For backward compatibility, expose parse methods as static methods
ThirteenF.parse_primary_document_xml = staticmethod(lambda xml: __import__('edgar.thirteenf.parsers.primary_xml', fromlist=['parse_primary_document_xml']).parse_primary_document_xml(xml))
ThirteenF.parse_infotable_xml = staticmethod(lambda xml: __import__('edgar.thirteenf.parsers.infotable_xml', fromlist=['parse_infotable_xml']).parse_infotable_xml(xml))
ThirteenF.parse_infotable_txt = staticmethod(lambda txt: __import__('edgar.thirteenf.parsers.infotable_txt', fromlist=['parse_infotable_txt']).parse_infotable_txt(txt))
